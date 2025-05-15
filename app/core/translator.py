# app/core/translator.py - Avec vérification de pertinence
import os
import time
import logging
import re
import aiohttp  # Assurez-vous que cette importation existe déjà
from typing import Dict, Any, List, Tuple, Optional

from app.config import get_settings
from app.core.embedding import get_embedding
from app.core.vector_search import find_similar_queries, check_exact_match, store_query
from app.core.llm import generate_sql, validate_sql_query as llm_validate_sql_query, get_sql_explanation, check_query_relevance
from app.utils.schema_loader import load_schema
from app.utils.sql_validator import SQLValidator
from app.utils.cache import cached, REDIS_TTL

# Configuration du logger
logger = logging.getLogger(__name__)

# Récupérer les paramètres de configuration
settings = get_settings()


async def build_prompt(user_query: str, similar_queries: List[Dict[str, Any]], schema: str) -> str:
    """
    Construit un prompt optimisé pour GPT-4o pour la traduction NL2SQL.
    
    Args:
        user_query: La requête utilisateur en langage naturel
        similar_queries: Liste des requêtes similaires trouvées
        schema: Le schéma de la base de données
        
    Returns:
        Le prompt formaté pour le LLM
    """
    # Pas besoin de formater le schéma Markdown - on l'utilise tel quel
    # puisque le SQLValidator simplifié ne fait pas d'analyse du schéma
    formatted_schema = schema
        
    prompt = f"""Tu es un expert SQL chevronné spécialisé dans la traduction de questions en langage naturel en requêtes SQL performantes et optimisées pour le reporting RH.

# CONTEXTE
Tu disposes du schéma complet de la base de données. Cette base contient des données RH et sociales issues de Déclarations Sociales Nominatives (DSN).

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

# CONSIGNES IMPORTANTES
- Cette base de données contient UNIQUEMENT des informations RH et sociales. Elle ne contient PAS d'informations sur le sport, la météo, la politique, ou d'autres sujets non liés aux RH.
- Si la demande ne concerne pas les RH, réponds "IMPOSSIBLE" car la requête est hors sujet.
- Génère UNIQUEMENT des requêtes SELECT (aucune opération d'écriture n'est autorisée)
- Utilise des ALIAS explicites et cohérents (ex: f pour facts, d pour depot, e pour entreprise, r pour referentiel)
- Préfixe chaque colonne par son alias de table (ex: f.NATURE_CONTRAT, d.PERIODE)
- Pour les champs numériques stockés en VARCHAR, utilise CAST(colonne AS SIGNED) ou CAST(colonne AS DECIMAL) pour les calculs et tris
- Utilise toujours des JOINs explicites avec la clause ON (jamais de jointures implicites)
- Pour les jointures avec la table REFERENTIEL, fais attention à bien filtrer sur RUBRIQUE_DSN et CODE
- Utilise des commentaires /* code = libellé */ pour expliquer les codes dans les conditions WHERE
- Lorsqu'une requête concerne des périodes, la colonne PERIODE dans DEPOT est au format 'MMAAAA' (utilise LEFT, RIGHT, SUBSTRING)

# EXEMPLES DE REQUÊTES PERTINENTES
"""
    
    # Ajouter les exemples de requêtes similaires avec un format amélioré
    for i, query in enumerate(similar_queries, 1):
        metadata = query['metadata']
        prompt += f"""EXEMPLE {i} - Pertinence: {query['score']:.2f}
Question: {metadata.get('texte_complet', metadata.get('description', 'N/A'))}
SQL: {metadata.get('requete', 'N/A')}

"""
    
    # Ajouter des exemples de traduction qui aident à comprendre les particularités du schéma
    prompt += f"""# EXEMPLES DE REQUÊTES SPÉCIFIQUES
Question: "Liste des CDI dans l'entreprise"
SQL: 
SELECT 
    f.ID, f.MATRICULE, f.NOM, f.PRENOM, e.DENOMINATION AS nom_entreprise
FROM 
    FACTS f
JOIN 
    DEPOT d ON f.ID_NUMDEPOT = d.ID
LEFT JOIN 
    ENTREPRISE e ON d.SIREN = e.SIREN AND d.nic = e.ETAB_NIC
WHERE 
    f.NATURE_CONTRAT = '01' /* 01 = CDI */

Question: "Nombre d'employés par tranche d'âge"
SQL:
SELECT 
    CASE 
        WHEN CAST(f.AGE AS UNSIGNED) < 30 THEN 'Moins de 30 ans'
        WHEN CAST(f.AGE AS UNSIGNED) BETWEEN 30 AND 50 THEN '30-50 ans'
        ELSE 'Plus de 50 ans'
    END AS tranche_age, 
    COUNT(*) AS nombre_employes 
FROM 
    FACTS f 
GROUP BY 
    tranche_age
ORDER BY 
    CASE tranche_age
        WHEN 'Moins de 30 ans' THEN 1
        WHEN '30-50 ans' THEN 2
        ELSE 3
    END

Question: "Répartition des salariés par type de contrat"
SQL:
SELECT 
    COALESCE(r.LIBELLE, 'Non renseigné') AS type_contrat, 
    COUNT(*) AS nombre 
FROM 
    FACTS f 
LEFT JOIN 
    REFERENTIEL r ON r.CODE = f.NATURE_CONTRAT AND r.RUBRIQUE_DSN LIKE '%NATURE_CONTRAT%'
GROUP BY 
    COALESCE(r.LIBELLE, 'Non renseigné')
ORDER BY 
    nombre DESC

Question: "Masse salariale par établissement pour mai 2023"
SQL:
SELECT 
    d.SIREN,
    d.nic,
    e.DENOMINATION AS nom_entreprise,
    SUM(CAST(f.MNT_BRUT AS DECIMAL(15,2))) AS masse_salariale_brute
FROM 
    FACTS f
JOIN 
    DEPOT d ON f.ID_NUMDEPOT = d.ID
LEFT JOIN 
    ENTREPRISE e ON d.SIREN = e.SIREN AND d.nic = e.ETAB_NIC
WHERE 
    d.PERIODE = '052023' /* Format MMAAAA pour mai 2023 */
GROUP BY 
    d.SIREN, d.nic, e.DENOMINATION
ORDER BY 
    masse_salariale_brute DESC

Question: "Taux d'absentéisme par département"
SQL:
SELECT 
    f.DEPARTEMENT,
    COUNT(DISTINCT f.ID) AS nb_salaries,
    COUNT(DISTINCT fa.id_fact) AS nb_salaries_absents,
    ROUND((COUNT(DISTINCT fa.id_fact) / COUNT(DISTINCT f.ID)) * 100, 2) AS taux_absenteisme
FROM 
    FACTS f
JOIN 
    DEPOT d ON f.ID_NUMDEPOT = d.ID
LEFT JOIN 
    FACTS_ABS_FINAL fa ON f.ID = fa.id_fact
GROUP BY 
    f.DEPARTEMENT
HAVING 
    f.DEPARTEMENT IS NOT NULL AND f.DEPARTEMENT != ''
ORDER BY 
    taux_absenteisme DESC

# EXEMPLES DE REQUÊTES HORS SUJET QUI DOIVENT ÊTRE REJETÉES
Question: "Qui a gagné la Ligue des Champions cette année ?"
SQL: IMPOSSIBLE

Question: "Quelle est la météo à Paris aujourd'hui ?"
SQL: IMPOSSIBLE

Question: "Donnez-moi la recette de la tarte aux pommes"
SQL: IMPOSSIBLE

# DEMANDE À TRADUIRE EN SQL
"{user_query}"

# INSTRUCTIONS
1. Analyse attentivement la demande pour comprendre précisément les besoins
2. Vérifie si la demande concerne bien les RH et cette base de données (sinon réponds IMPOSSIBLE)
3. Identifie les tables et champs pertinents dans le schéma
4. Crée une requête SQL optimisée qui répond exactement à la question
5. Vérifie que toutes les tables et colonnes existent et que tous les alias sont cohérents
6. Assure-toi que les jointures sont correctement définies avec la condition ON
7. Ajoute des commentaires pour expliquer les codes et choix techniques importants
8. Retourne UNIQUEMENT la requête SQL sans aucune explication autour

SQL Query:"""
    
    return prompt


@cached(ttl=REDIS_TTL)  # Utilise la mise en cache Redis
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
    Version adaptée pour fonctionner avec le SQLValidator simplifié et la vérification de pertinence.
    
    Args:
        user_query: La requête en langage naturel à traduire
        schema_path: Chemin vers le fichier de schéma SQL ou Markdown (optionnel)
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
        "similar_queries": None,
        "from_cache": False  # Indicateur pour la mise en cache
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
        # NOUVELLE ÉTAPE: Vérifier si la requête est pertinente pour une base de données RH
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
        
        # Log pour le débogage de la taille du schéma
        logger.debug(f"Longueur du schéma chargé: {len(schema)} caractères")
        
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
            
            # Valider aussi les correspondances exactes avec le validateur simplifié
            sql_validator = SQLValidator(schema_content=schema, schema_path=schema_path)
            
            # Vérifier si la requête contient des opérations destructives
            is_destructive, destructive_message = sql_validator.check_destructive_operations(exact_match)
            if is_destructive:
                logger.warning(f"Correspondance exacte contient une opération destructive: {exact_match}")
                result["valid"] = False
                result["validation_message"] = destructive_message
                result["status"] = "error"
                return result
            
            result["sql"] = exact_match
            result["valid"] = True
            result["validation_message"] = "Requête trouvée directement dans la base de connaissances."
            result["is_exact_match"] = True
            result["status"] = "success"
        else:
            # Construire le prompt
            prompt = await build_prompt(user_query, similar_queries, schema)
            
            # Log pour le débogage du prompt
            logger.debug(f"Longueur du prompt envoyé à OpenAI: {len(prompt)} caractères")
            
            # Générer le SQL
            sql_result = await generate_sql(prompt, openai_model, openai_temperature)
            
            # Vérifier si la génération a retourné "IMPOSSIBLE" (hors sujet)
            if sql_result is None or sql_result.upper() == "IMPOSSIBLE":
                logger.warning(f"La requête a été jugée hors sujet ou impossible à traduire en SQL")
                result["valid"] = False
                result["validation_message"] = "Cette demande ne semble pas concerner les ressources humaines ou est impossible à traduire en SQL avec le schéma fourni."
                result["status"] = "error"
                return result
            
            # Vérifier les réponses spéciales du LLM
            if sql_result and sql_result.upper() == "READONLY_VIOLATION":
                logger.warning(f"Violation de lecture seule détectée pour la requête: {user_query}")
                result["valid"] = False
                result["sql"] = None
                result["validation_message"] = "Votre demande concerne une opération d'écriture (INSERT, UPDATE, DELETE, etc.) qui n'est pas autorisée. Cette API est en lecture seule et ne peut exécuter que des requêtes de consultation (SELECT)."
                result["status"] = "error"
                return result
            
            # Validation simplifiée qui vérifie uniquement la sécurité
            sql_validator = SQLValidator(schema_content=schema, schema_path=schema_path)
            is_destructive, destructive_message = sql_validator.check_destructive_operations(sql_result)
            
            if is_destructive:
                logger.warning(f"Requête destructive détectée: {sql_result}")
                result["valid"] = False
                result["validation_message"] = destructive_message
                result["status"] = "error"
                return result
                
            result["sql"] = sql_result
            
            # Valider la requête générée si demandé
            if validate:
                # Effectuer la validation simplifiée
                validation_result = await sql_validator.validate_sql_query(sql_result, user_query)
                
                # Mise à jour des résultats
                result["valid"] = validation_result["valid"]
                result["validation_message"] = validation_result["message"]
                
                # Stocker les détails supplémentaires pour le debug si nécessaire
                if settings.DEBUG:
                    result["validation_details"] = validation_result["details"]
            else:
                # Si la validation est désactivée, considérer la requête comme valide
                result["valid"] = True
                result["validation_message"] = "Validation désactivée. La requête est considérée comme valide."
            
            # Toujours considérer la requête comme valide tant qu'elle n'est pas destructive
            result["status"] = "success"
            
            # Si la requête est valide et qu'on doit la stocker, on l'ajoute à Pinecone
            if store_result and result["valid"] and sql_result:
                await store_query(user_query, query_vector, sql_result)
        
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