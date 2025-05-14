import os
import time
import logging
from typing import Dict, Any, List, Tuple, Optional

from app.config import get_settings
from app.core.embedding import get_embedding
from app.core.vector_search import find_similar_queries, check_exact_match, store_query
from app.core.llm import generate_sql, validate_sql_query, get_sql_explanation
from app.utils.schema_loader import load_schema

# Configuration du logger
logger = logging.getLogger(__name__)

# Récupérer les paramètres de configuration
settings = get_settings()


async def build_prompt(user_query: str, similar_queries: List[Dict[str, Any]], schema: str) -> str:
    """
    Construit le prompt pour le LLM avec un format simplifié et plus direct.
    
    Args:
        user_query: La requête utilisateur en langage naturel
        similar_queries: Liste des requêtes similaires trouvées
        schema: Le schéma de la base de données
        
    Returns:
        Le prompt formaté pour le LLM
    """
    prompt = f"""À partir de la demande suivante en langage naturel, génère une requête SQL optimisée en te basant sur les exemples similaires fournis et sur le schéma de la base de données.

IMPORTANT: Si et seulement si la demande est clairement et totalement impossible à traduire en SQL avec ce schéma (par exemple, si elle demande des données sur un sujet complètement différent comme "recette de cuisine" ou "météo"), réponds "IMPOSSIBLE". N'utilise cette réponse que si tu es absolument certain que la demande n'a AUCUN rapport avec les données de la base.

SCHÉMA DE LA BASE DE DONNÉES:
```sql
{schema}
```

REQUÊTES SIMILAIRES:
"""
    
    for i, query in enumerate(similar_queries, 1):
        metadata = query['metadata']
        prompt += f"""EXEMPLE {i} (score: {query['score']:.4f}):
Description: {metadata.get('texte_complet', metadata.get('description', 'N/A'))}
Requête SQL: {metadata.get('requete', 'N/A')}

"""
    
    prompt += f"""DEMANDE UTILISATEUR: {user_query}

IMPORTANT: Tu dois générer UNIQUEMENT le code SQL sans aucune explication, sans aucun texte supplémentaire, sans bloc de code. 
Fais tout ton possible pour interpréter la demande, même si elle est vague ou incomplète.
Retourne simplement et directement la requête SQL valide et fonctionnelle, rien d'autre.
"""
    
    return prompt


async def translate_nl_to_sql(
    user_query: str, 
    schema_path: Optional[str] = None, 
    validate: bool = True, 
    explain: bool = True,
    store_result: bool = True,
    return_similar_queries: bool = False
) -> Dict[str, Any]:
    """
    Fonction principale asynchrone: traduit une requête en langage naturel en SQL.
    
    Args:
        user_query: La requête en langage naturel à traduire
        schema_path: Chemin vers le fichier de schéma SQL (optionnel)
        validate: Valider la requête SQL générée
        explain: Fournir une explication de la requête SQL
        store_result: Stocker la paire requête-SQL dans Pinecone
        return_similar_queries: Inclure les requêtes similaires dans la réponse
        
    Returns:
        Dictionnaire contenant la requête SQL générée et les métadonnées associées
    """
    # Chronométrer l'exécution
    start_time = time.time()
    
    # Initialiser le résultat
    result = {
        "sql": None,
        "valid": None, 
        "validation_message": None, 
        "explanation": None,
        "is_exact_match": False,
        "status": "error",
        "processing_time": None,
        "similar_queries": None
    }
    
    try:
        # Charger le schéma
        if schema_path is None:
            schema_path = settings.SCHEMA_PATH
        
        logger.info(f"Traduction de requête: '{user_query[:50]}...' (schéma: {schema_path})")
        schema = await load_schema(schema_path)
        
        # Récupérer les paramètres
        exact_match_threshold = settings.EXACT_MATCH_THRESHOLD
        openai_model = settings.OPENAI_MODEL
        openai_temperature = settings.OPENAI_TEMPERATURE
        
        # Vectoriser la requête
        query_vector = await get_embedding(user_query)
        
        # Rechercher les requêtes similaires
        similar_queries = await find_similar_queries(query_vector, settings.TOP_K_RESULTS)
        
        # Si demandé, inclure les requêtes similaires dans la réponse
        if return_similar_queries:
            # Simplifier les requêtes similaires pour l'API
            simplified_queries = []
            for q in similar_queries:
                simplified_queries.append({
                    "score": q["score"],
                    "query": q["metadata"].get("texte_complet", ""),
                    "sql": q["metadata"].get("requete", "")
                })
            result["similar_queries"] = simplified_queries
        
        # Vérifier s'il y a une correspondance exacte
        exact_match = await check_exact_match(similar_queries, exact_match_threshold)
        
        if exact_match:
            logger.info(f"Correspondance exacte trouvée pour la requête")
            result["sql"] = exact_match
            result["valid"] = True
            result["validation_message"] = "Requête trouvée directement dans la base de connaissances."
            result["is_exact_match"] = True
            result["status"] = "success"
        else:
            # Construire le prompt
            prompt = await build_prompt(user_query, similar_queries, schema)
            
            # Générer le SQL
            sql_result = await generate_sql(prompt, openai_model, openai_temperature)
            
            # Vérifier si la génération a échoué ou retourné "IMPOSSIBLE"
            if sql_result is None:
                logger.warning(f"La requête a été jugée impossible à traduire en SQL")
                result["valid"] = False
                result["validation_message"] = "Cette demande ne semble pas concerner une requête SQL sur cette base de données, ou est impossible à traduire en SQL avec le schéma fourni."
                result["status"] = "error"
                return result
                
            result["sql"] = sql_result
            
            # Valider la requête générée si demandé
            if validate:
                valid, validation_message = await validate_sql_query(sql_result, user_query, schema, openai_model)
                result["valid"] = valid
                result["validation_message"] = validation_message
            
            # Si la requête est valide et qu'on doit la stocker, on l'ajoute à Pinecone
            if store_result and result["valid"] and sql_result:
                await store_query(user_query, query_vector, sql_result)
            
            result["status"] = "success"
        
        # Obtenir une explication de la requête si demandé
        if explain and result["sql"] is not None:
            explanation = await get_sql_explanation(result["sql"], user_query, openai_model)
            result["explanation"] = explanation
    
    except Exception as e:
        logger.error(f"Erreur lors de la traduction de la requête: {str(e)}", exc_info=True)
        result["status"] = "error"
        result["validation_message"] = f"Erreur: {str(e)}"
    
    finally:
        # Calculer le temps de traitement
        end_time = time.time()
        processing_time = end_time - start_time
        result["processing_time"] = round(processing_time, 3)
        
        logger.info(f"Traduction terminée en {processing_time:.3f}s (statut: {result['status']})")
    
    return result


async def health_check() -> Dict[str, Any]:
    """
    Vérifie l'état de santé des services dépendants.
    
    Returns:
        Dictionnaire contenant l'état de santé des services
    """
    from app.core.embedding import check_embedding_service
    from app.core.vector_search import check_pinecone_service
    from app.core.llm import check_openai_service
    
    # Vérifier les services
    embedding_status = await check_embedding_service()
    pinecone_status = await check_pinecone_service()
    openai_status = await check_openai_service()
    
    # Déterminer le statut global
    all_ok = (
        embedding_status.get("status") == "ok" and
        pinecone_status.get("status") == "ok" and
        openai_status.get("status") == "ok"
    )
    
    return {
        "status": "ok" if all_ok else "error",
        "version": "1.0.0",  # À mettre à jour avec la version réelle
        "services": {
            "embedding": embedding_status,
            "pinecone": pinecone_status,
            "openai": openai_status
        }
    }