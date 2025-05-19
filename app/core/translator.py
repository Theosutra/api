# app/core/translator.py - Version complète avec framework obligatoire
import os
import time
import logging
import re
import aiohttp
from typing import Dict, Any, List, Tuple, Optional

from app.config import get_settings
from app.core.embedding import get_embedding
from app.core.vector_search import find_similar_queries, check_exact_match, store_query
from app.core.llm import generate_sql, validate_sql_query as llm_validate_sql_query, get_sql_explanation, check_query_relevance
from app.utils.schema_loader import load_schema
from app.utils.sql_validator import SQLValidator
from app.utils.cache import cached, REDIS_TTL
from app.utils.simple_framework_check import validate_framework_compliance, add_missing_framework_elements

# Configuration du logger
logger = logging.getLogger(__name__)

# Récupérer les paramètres de configuration
settings = get_settings()


async def build_prompt(user_query: str, similar_queries: List[Dict[str, Any]], schema: str) -> str:
    """
    Construit un prompt optimisé pour GPT-4o pour la traduction NL2SQL avec framework obligatoire.
    
    Args:
        user_query: La requête utilisateur en langage naturel
        similar_queries: Liste des requêtes similaires trouvées
        schema: Le schéma de la base de données
        
    Returns:
        Le prompt formaté pour le LLM
    """
    formatted_schema = schema
        
    prompt = f"""Tu es un expert SQL chevronné spécialisé dans la traduction de questions en langage naturel en requêtes SQL performantes et optimisées pour le reporting RH.

# CONTEXTE
Tu disposes du schéma complet de la base de données. Cette base contient des données RH et sociales issues de Déclarations Sociales Nominatives (DSN).

# RÈGLES OBLIGATOIRES - À RESPECTER ABSOLUMENT DANS CHAQUE REQUÊTE

## 1. FILTRE UTILISATEUR OBLIGATOIRE
- CHAQUE requête SQL DOIT OBLIGATOIREMENT contenir : WHERE [alias_depot].ID_USER = ?
- Ce filtre est OBLIGATOIRE pour la sécurité et les autorisations utilisateur
- Exemple : WHERE d.ID_USER = ? (si l'alias de DEPOT est 'd')

## 2. TABLE DEPOT TOUJOURS REQUISE
- La table DEPOT doit TOUJOURS être présente dans chaque requête
- Elle peut être jointe directement ou indirectement via FACTS
- Utilise un alias court comme 'd' pour DEPOT

## 3. HASHTAGS OBLIGATOIRES EN FIN DE REQUÊTE
- Ajoute #DEPOT_[alias]# où [alias] est l'alias de la table DEPOT
- Ajoute #FACTS_[alias]# si tu utilises la table FACTS  
- Ajoute #PERIODE# pour les requêtes avec des critères temporels
- Place ces hashtags APRÈS le point-virgule final

## STRUCTURE OBLIGATOIRE - MODÈLE À SUIVRE :
```sql
SELECT [colonnes]
FROM [table_principale] [alias1]
JOIN DEPOT [alias_depot] ON [condition_join]
WHERE [alias_depot].ID_USER = ? 
  AND [autres_conditions]
[GROUP BY/ORDER BY si nécessaire]; #DEPOT_[alias_depot]# [#FACTS_[alias]#] [#PERIODE#]
```

## EXEMPLE CONCRET :
```sql
SELECT f.NOM, f.PRENOM, f.MNT_BRUT
FROM FACTS f
JOIN DEPOT d ON f.ID_NUMDEPOT = d.ID  
WHERE d.ID_USER = ? 
  AND f.NATURE_CONTRAT = '01'
ORDER BY f.NOM; #DEPOT_d# #FACTS_f#
```

# STRUCTURE PRINCIPALE DE LA BASE DE DONNÉES
- DEPOT: Table centrale contenant les informations sur les dépôts de DSN par entreprise et par période
- FACTS: Table principale des données salariés (contrats, informations personnelles)
- FACTS_REM: Contient les éléments de rémunération liés aux salariés
- FACTS_ABS_FINAL: Contient les absences des salariés
- ENTREPRISE: Contient les informations sur les entreprises/établissements
- REFERENTIEL: Contient les valeurs de référence pour décoder les codes utilisés dans les autres tables

# RELATIONS ET INFORMATIONS ESSENTIELLES
- Un "DEPOT" correspond à une déclaration sociale pour un SIREN+NIC (SIRET) sur une période (généralement mensuelle)
- Chaque salarié dans "FACTS" est lié à un DEPOT via ID_NUMDEPOT
- Les types de contrats sont codifiés dans NATURE_CONTRAT:
  * '01' = CDI
  * '02' = CDD
  * '03' = Intérim
  * '07' à '08' = Stages/Alternances
- L'âge est stocké dans la colonne "AGE" comme VARCHAR - utiliser CAST pour les tris numériques
- La table "REFERENTIEL" permet de traduire les codes en libellés via les colonnes:
  * RUBRIQUE_DSN: le type de code (ex: pour les types de contrat)
  * CODE: la valeur du code (ex: '01')
  * LIBELLE: la signification du code (ex: 'Contrat à durée indéterminée')

# SCHÉMA DE LA BASE DE DONNÉES
```
{formatted_schema}
```

# CONSIGNES TECHNIQUES
- Génère UNIQUEMENT des requêtes SELECT
- **ATTENTION AUX DATES ET ANNÉES** : Respecte exactement l'année/période demandée
- Utilise des alias courts et cohérents (f pour FACTS, d pour DEPOT, e pour ENTREPRISE, etc.)
- Préfixe toujours les colonnes avec leur alias (ex: f.NOM, d.PERIODE)
- Pour les champs numériques en VARCHAR, utilise CAST(colonne AS SIGNED/DECIMAL)
- Utilise des JOINs explicites avec ON (jamais de jointures implicites)
- Si la demande est hors RH, réponds "IMPOSSIBLE"

# EXEMPLES DE REQUÊTES SIMILAIRES
"""
    
    # Ajouter les exemples avec le framework obligatoire appliqué
    for i, query in enumerate(similar_queries, 1):
        metadata = query['metadata']
        query_text = metadata.get('texte_complet', metadata.get('description', 'N/A'))
        sql_query = metadata.get('requete', 'N/A')
        
        prompt += f"""EXEMPLE {i} - Score: {query['score']:.2f}
Question: {query_text}
SQL: {sql_query}

"""
    
    prompt += f"""
# EXEMPLES AVEC FRAMEWORK OBLIGATOIRE CORRECT

Question: "Liste des CDI"
SQL CORRECT:
SELECT f.NOM, f.PRENOM, f.MATRICULE
FROM FACTS f
JOIN DEPOT d ON f.ID_NUMDEPOT = d.ID
WHERE d.ID_USER = ? 
  AND f.NATURE_CONTRAT = '01'
ORDER BY f.NOM; #DEPOT_d# #FACTS_f#

Question: "Effectif par type de contrat"
SQL CORRECT:
SELECT f.NATURE_CONTRAT, COUNT(*) as effectif
FROM FACTS f
JOIN DEPOT d ON f.ID_NUMDEPOT = d.ID
WHERE d.ID_USER = ?
GROUP BY f.NATURE_CONTRAT; #DEPOT_d# #FACTS_f#

Question: "Masse salariale de mai 2023"
SQL CORRECT:
SELECT SUM(CAST(f.MNT_BRUT AS DECIMAL(15,2))) as masse_salariale
FROM FACTS f
JOIN DEPOT d ON f.ID_NUMDEPOT = d.ID
WHERE d.ID_USER = ? 
  AND d.PERIODE = '052023'
GROUP BY d.PERIODE; #DEPOT_d# #FACTS_f# #PERIODE#

Question: "Salariés absents ce mois"
SQL CORRECT:
SELECT f.NOM, f.PRENOM, fa.DEBUT_ARRET, fa.MOTIF_ARRET
FROM FACTS f
JOIN DEPOT d ON f.ID_NUMDEPOT = d.ID
JOIN FACTS_ABS_FINAL fa ON f.ID = fa.id_fact
WHERE d.ID_USER = ?
  AND fa.DEBUT_ARRET >= CURDATE() - INTERVAL 30 DAY; #DEPOT_d# #FACTS_f#

# EXEMPLES DE REQUÊTES HORS SUJET QUI DOIVENT ÊTRE REJETÉES
Question: "Qui a gagné la Ligue des Champions cette année ?"
SQL: IMPOSSIBLE

Question: "Quelle est la météo à Paris aujourd'hui ?"
SQL: IMPOSSIBLE

Question: "Donnez-moi la recette de la tarte aux pommes"
SQL: IMPOSSIBLE

# REQUÊTE À TRADUIRE
Question: "{user_query}"

# INSTRUCTIONS FINALES
1. Analyse la question pour comprendre les besoins
2. Si la question ne concerne pas la RH, réponds "IMPOSSIBLE"
3. Identifie les tables nécessaires du schéma
4. Construis la requête en respectant OBLIGATOIREMENT :
   - Table DEPOT présente avec alias
   - Filtre WHERE [alias_depot].ID_USER = ?
   - Hashtags en fin : #DEPOT_[alias]# et autres selon contexte
5. Retourne UNIQUEMENT la requête SQL finale

SQL:"""
    
    return prompt


@cached(ttl=REDIS_TTL)  # Utilise la mise en cache Redis
async def translate_nl_to_sql(
    user_query: str, 
    schema_path: Optional[str] = None, 
    validate: bool = True, 
    explain: bool = True,
    store_result: bool = True,
    return_similar_queries: bool = False,
    user_id_placeholder: str = "?",
    use_cache: bool = True,  # Nouveau paramètre pour contrôler le cache
    **kwargs  # Accepter tous les arguments supplémentaires
) -> Dict[str, Any]:
    """
    Fonction principale asynchrone: traduit une requête en langage naturel en SQL 
    avec validation du framework obligatoire.
    
    Args:
        user_query: La requête en langage naturel à traduire
        schema_path: Chemin vers le fichier de schéma SQL ou Markdown (optionnel)
        validate: Valider la requête SQL générée
        explain: Fournir une explication de la requête SQL
        store_result: Stocker la paire requête-SQL dans Pinecone
        return_similar_queries: Inclure les requêtes similaires dans la réponse
        user_id_placeholder: Placeholder pour l'ID utilisateur (par défaut "?")
        
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
        "similar_queries": None,
        "from_cache": False,
        "framework_compliant": False
    }
    
    # Vérification préliminaire pour les opérations interdites dans la requête
    forbidden_operations = ["insert", "update", "delete", "drop", "truncate", "alter", "create"]
    operation_detected = False
    detected_operation = None
    
    for op in forbidden_operations:
        if op in user_query.lower():
            operation_detected = True
            detected_operation = op
            break
    
    if operation_detected:
        result["status"] = "error"
        result["validation_message"] = f"Opération '{detected_operation.upper()}' non autorisée. Seules les requêtes de consultation (SELECT) sont permises. Veuillez reformuler votre demande."
        result["processing_time"] = 0.001
        return result
    
    try:
        # Vérifier si la requête est pertinente pour une base de données RH
        is_relevant = await check_query_relevance(user_query)
        
        if not is_relevant:
            result["status"] = "error"
            result["validation_message"] = "Cette requête ne semble pas concerner les ressources humaines. Cette base de données contient uniquement des informations RH (employés, contrats, absences, paie, etc.)."
            result["processing_time"] = time.time() - start_time
            return result
        
        # Charger le schéma
        if schema_path is None:
            schema_path = settings.SCHEMA_PATH
        
        logger.info(f"Traduction de requête: '{user_query[:50]}...' (schéma: {schema_path})")
        schema = await load_schema(schema_path)
        
        # Récupérer les paramètres avec valeurs par défaut
        exact_match_threshold = settings.EXACT_MATCH_THRESHOLD
        openai_model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o')
        openai_temperature = getattr(settings, 'OPENAI_TEMPERATURE', 0.2)
        
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
            
            # NOUVELLE VALIDATION : Vérifier la cohérence sémantique
            # Extraire les années de la requête utilisateur et de la requête trouvée
            user_years = re.findall(r'\b(20\d{2})\b', user_query)
            sql_years = re.findall(r'\b(20\d{2})\b', exact_match)
            
            # Si des années sont mentionnées, vérifier qu'elles correspondent
            if user_years and sql_years and user_years[0] != sql_years[0]:
                logger.warning(f"Correspondance exacte avec année différente: {user_years[0]} vs {sql_years[0]}")
                # Ne pas utiliser cette correspondance, continuer avec la génération
                exact_match = None
        
        if exact_match:
            # Valider le framework de la correspondance exacte
            framework_compliant, framework_message = validate_framework_compliance(exact_match)
            
            if not framework_compliant:
                # Essayer de corriger automatiquement
                logger.warning(f"Correspondance exacte non conforme au framework: {framework_message}")
                corrected_query = add_missing_framework_elements(exact_match)
                framework_compliant, framework_message = validate_framework_compliance(corrected_query)
                
                if framework_compliant:
                    exact_match = corrected_query
                    logger.info(f"Correspondance exacte corrigée avec succès")
                else:
                    logger.error(f"Impossible de corriger la correspondance exacte: {framework_message}")
                    result["valid"] = False
                    result["validation_message"] = f"Correspondance exacte non conforme: {framework_message}"
                    result["status"] = "error"
                    result["processing_time"] = time.time() - start_time
                    return result
            
            # Valider aussi les correspondances exactes avec le validateur SQL
            sql_validator = SQLValidator(schema_content=schema, schema_path=schema_path)
            
            # Vérifier si la requête contient des opérations destructives
            is_destructive, destructive_message = sql_validator.check_destructive_operations(exact_match)
            if is_destructive:
                logger.warning(f"Correspondance exacte contient une opération destructive: {exact_match}")
                result["valid"] = False
                result["validation_message"] = destructive_message
                result["status"] = "error"
                result["processing_time"] = time.time() - start_time
                return result
            
            result["sql"] = exact_match
            result["valid"] = True
            result["validation_message"] = "Requête trouvée directement dans la base de connaissances et conforme au framework."
            result["is_exact_match"] = True
            result["status"] = "success"
            result["framework_compliant"] = True
        else:
            # Construire le prompt avec framework obligatoire
            prompt = await build_prompt(user_query, similar_queries, schema)
            
            # Générer le SQL
            sql_result = await generate_sql(prompt)
            
            # Vérifier si la génération a retourné "IMPOSSIBLE" (hors sujet)
            if sql_result is None or sql_result.upper() == "IMPOSSIBLE":
                logger.warning(f"La requête a été jugée hors sujet ou impossible à traduire en SQL")
                result["valid"] = False
                result["validation_message"] = "Cette demande ne semble pas concerner les ressources humaines ou est impossible à traduire en SQL avec le schéma fourni."
                result["status"] = "error"
                result["processing_time"] = time.time() - start_time
                return result
            
            # Vérifier les réponses spéciales du LLM
            if sql_result and sql_result.upper() == "READONLY_VIOLATION":
                logger.warning(f"Violation de lecture seule détectée pour la requête: {user_query}")
                result["valid"] = False
                result["sql"] = None
                result["validation_message"] = "Votre demande concerne une opération d'écriture (INSERT, UPDATE, DELETE, etc.) qui n'est pas autorisée. Cette API est en lecture seule et ne peut exécuter que des requêtes de consultation (SELECT)."
                result["status"] = "error"
                result["processing_time"] = time.time() - start_time
                return result
            
            # NOUVELLE VALIDATION : Vérifier le framework obligatoire
            framework_compliant, framework_message = validate_framework_compliance(sql_result)
            
            if not framework_compliant:
                logger.warning(f"Requête non conforme au framework: {framework_message}")
                # Essayer de corriger automatiquement
                corrected_query = add_missing_framework_elements(sql_result)
                framework_compliant, framework_message = validate_framework_compliance(corrected_query)
                
                if framework_compliant:
                    logger.info(f"Requête corrigée avec succès")
                    sql_result = corrected_query
                    result["validation_message"] = f"Requête générée et corrigée automatiquement pour respecter le framework obligatoire."
                else:
                    logger.error(f"Impossible de corriger la requête: {framework_message}")
                    result["valid"] = False
                    result["validation_message"] = f"Requête non conforme au framework obligatoire: {framework_message}"
                    result["status"] = "error"
                    result["processing_time"] = time.time() - start_time
                    return result
            
            result["framework_compliant"] = framework_compliant
            
            # Validation de sécurité (opérations destructives)
            sql_validator = SQLValidator(schema_content=schema, schema_path=schema_path)
            is_destructive, destructive_message = sql_validator.check_destructive_operations(sql_result)
            
            if is_destructive:
                logger.warning(f"Requête destructive détectée: {sql_result}")
                result["valid"] = False
                result["validation_message"] = destructive_message
                result["status"] = "error"
                result["processing_time"] = time.time() - start_time
                return result
                
            result["sql"] = sql_result
            
            # Valider la requête générée si demandé (validation de cohérence supplémentaire)
            if validate:
                # Effectuer la validation simplifiée
                validation_result = await sql_validator.validate_sql_query(sql_result, user_query)
                
                # Mise à jour des résultats  
                result["valid"] = validation_result["valid"]
                result["validation_message"] = validation_result["message"]
                
                # Ajuster le message pour inclure le respect du framework
                if result["valid"] and framework_compliant:
                    result["validation_message"] = f"{validation_result['message']} La requête respecte le framework obligatoire."
                elif result["valid"] and not framework_compliant:
                    result["validation_message"] = f"{validation_result['message']} Attention: {framework_message}"
                
                # Stocker les détails supplémentaires pour le debug si nécessaire
                if settings.DEBUG:
                    result["validation_details"] = validation_result["details"]
            else:
                # Si la validation est désactivée, considérer la requête comme valide
                result["valid"] = True
                result["validation_message"] = "Validation désactivée. La requête est considérée comme valide et respecte le framework obligatoire."
            
            # Toujours considérer la requête comme valide tant qu'elle respecte le framework et n'est pas destructive
            result["status"] = "success"
            
            # Si la requête est valide et qu'on doit la stocker, on l'ajoute à Pinecone
            if store_result and result["valid"] and sql_result:
                await store_query(user_query, query_vector, sql_result)
        
        # Obtenir une explication de la requête si demandé
        if explain and result["sql"] is not None:
            # Toujours régénérer l'explication pour avoir une version client-friendly
            # même si c'est une correspondance exacte
            explanation = await get_sql_explanation(result["sql"], user_query)
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
        
        # Log détaillé avec informations sur le framework
        framework_status = "conforme" if result.get("framework_compliant", False) else "non conforme"
        logger.info(f"Traduction terminée en {processing_time:.3f}s (statut: {result['status']}, framework: {framework_status})")
    
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
    from app.utils.cache import get_redis_client
    
    # Vérifier les services
    embedding_status = await check_embedding_service()
    pinecone_status = await check_pinecone_service()
    openai_status = await check_openai_service()
    
    # Vérifier Redis
    redis_status = {"status": "disabled"}
    if os.getenv("CACHE_ENABLED", "true").lower() == "true":
        try:
            redis_client = await get_redis_client()
            if redis_client:
                await redis_client.ping()
                redis_status = {
                    "status": "ok",
                    "url": os.getenv("REDIS_URL", "redis://localhost:6379/0").split("@")[-1]  # Ne pas exposer les credentials
                }
            else:
                redis_status = {"status": "error", "message": "Client Redis non initialisé"}
        except Exception as e:
            redis_status = {"status": "error", "message": str(e)}
    
    # Déterminer le statut global
    all_ok = (
        embedding_status.get("status") == "ok" and
        pinecone_status.get("status") == "ok" and
        openai_status.get("status") == "ok" and
        (redis_status.get("status") in ["ok", "disabled"])
    )
    
    return {
        "status": "ok" if all_ok else "error",
        "version": "1.0.0",  # À mettre à jour avec la version réelle
        "services": {
            "embedding": embedding_status,
            "pinecone": pinecone_status,
            "openai": openai_status,
            "redis": redis_status
        }
    }