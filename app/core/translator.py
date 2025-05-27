import os
import time
import logging
import re
import aiohttp
from typing import Dict, Any, List, Tuple, Optional

from app.config import get_settings
from app.core.embedding import get_embedding
from app.core.vector_search import find_similar_queries, check_exact_match, store_query
from app.core.llm_service import LLMService
from app.utils.schema_loader import load_schema
from app.utils.sql_validator import SQLValidator
from app.utils.cache import cached, REDIS_TTL
from app.utils.simple_framework_check import validate_framework_compliance, add_missing_framework_elements

# NOUVELLES IMPORTS - Exceptions centralisées
from app.core.exceptions import (
    LLMError, LLMNetworkError, LLMAuthError, LLMQuotaError,
    ValidationError, FrameworkError, EmbeddingError, 
    VectorSearchError, SchemaError
)

# Configuration du logger
logger = logging.getLogger(__name__)

# Récupérer les paramètres de configuration
settings = get_settings()


def format_similar_queries_for_response(similar_queries: List[Dict[str, Any]], include_details: bool = False) -> Optional[List[Dict[str, Any]]]:
    """
    Formate les requêtes similaires pour l'inclusion dans la réponse API.
    
    Args:
        similar_queries: Liste des requêtes similaires de Pinecone
        include_details: Si True, inclut les détails complets (texte_complet, requete, score, id)
        
    Returns:
        Liste formatée des requêtes similaires ou None si vide
        
    Raises:
        VectorSearchError: Si erreur dans le formatage des résultats
    """
    if not similar_queries:
        return None
    
    try:
        if include_details:
            # Retourner les détails complets pour validation/debug
            detailed_queries = []
            for query in similar_queries:
                metadata = query.get('metadata', {})
                detailed_queries.append({
                    "score": round(query.get('score', 0), 4),
                    "texte_complet": metadata.get('texte_complet', ''),
                    "requete": metadata.get('requete', ''),
                    "id": query.get('id', '')
                })
            return detailed_queries
        else:
            # Format simplifié pour rétrocompatibilité
            simplified_queries = []
            for query in similar_queries:
                metadata = query.get('metadata', {})
                simplified_queries.append({
                    "score": round(query.get('score', 0), 4),
                    "query": metadata.get('texte_complet', ''),
                    "sql": metadata.get('requete', '')
                })
            return simplified_queries
    
    except Exception as e:
        logger.error(f"Erreur lors du formatage des requêtes similaires: {e}")
        raise VectorSearchError(f"Impossible de formater les résultats de recherche: {e}")


async def build_prompt(user_query: str, similar_queries: List[Dict[str, Any]], schema: str) -> str:
    """
    Construit un prompt optimisé pour la traduction NL2SQL avec apprentissage à partir des exemples similaires
    et en mettant l'accent sur l'utilisation de la documentation complète dans datasulting.md.
    
    Args:
        user_query: La requête utilisateur en langage naturel
        similar_queries: Liste des requêtes similaires trouvées
        schema: Le schéma de la base de données (contenu de datasulting.md)
        
    Returns:
        Le prompt formaté pour le LLM
        
    Raises:
        ValidationError: Si les paramètres sont invalides
    """
    if not user_query or not schema:
        raise ValidationError("user_query et schema sont obligatoires", "build_prompt")
    
    try:
        formatted_schema = schema
            
        prompt = f"""Tu es un expert SQL spécialisé dans la traduction de questions RH en langage naturel vers SQL, optimisé pour une base de données de gestion sociale. Tu dois ANALYSER ATTENTIVEMENT la documentation de la base de données fournie et ADAPTER des requêtes existantes similaires.

# MÉTHODE DE TRAVAIL PRIORITAIRE
1. EXAMINE D'ABORD la documentation de la base de données fournie - c'est une ressource exhaustive qui contient le schéma, les bonnes pratiques, et les modèles de requêtes recommandés
2. CONSULTE ENSUITE les requêtes similaires fournies et priorise celles avec le meilleur score de correspondance
3. ADAPTE la requête la plus pertinente en la modifiant pour répondre à la question, en t'appuyant sur la documentation
4. NE CONSTRUIS PAS de nouvelles requêtes à partir de zéro quand une adaptation est possible

# CONSIGNES STRICTES
- RESPECTE TOUJOURS le framework de sécurité obligatoire décrit dans la documentation (filtre ID_USER, table DEPOT, hashtags)
- UTILISE les conventions d'aliasing recommandées dans la documentation (DEPOT → a, FACTS → b, etc.)
- RÉFÈRE-TOI aux modèles de requêtes et filtres décrits dans la documentation pour les cas d'usage courants
- COPIE la structure, les jointures et l'organisation des requêtes similaires appropriées
- VÉRIFIE que les colonnes utilisées existent bien dans le schéma fourni
- CONSERVE la même structure de filtrage et de regroupement que les exemples similaires
- RESPEC LE FRAMEWORK DE JOINTURE OBLIGATOIRE avec la table DEPOT
- N'INVENTE PAS de nouvelles jointures ou tables non présentes dans le schéma ou les exemples

# DOCUMENTATION COMPLÈTE DE LA BASE DE DONNÉES
```
{formatted_schema}
```

# REQUÊTES SIMILAIRES (PRIORITÉ PAR SCORE)
"""
        
        # Tri des requêtes par score de similarité (du plus élevé au plus bas)
        sorted_queries = sorted(similar_queries, key=lambda q: q.get('score', 0), reverse=True)
        
        # Ajouter les exemples avec le framework obligatoire appliqué
        for i, query in enumerate(sorted_queries, 1):
            metadata = query.get('metadata', {})
            query_text = metadata.get('nom', metadata.get('texte_complet', 'N/A'))
            sql_query = metadata.get('requete', 'N/A')
            score = query.get('score', 0)
            
            # Mettre en évidence les requêtes avec des scores élevés
            emphasis = "⭐⭐⭐" if score > 0.85 else "⭐⭐" if score > 0.75 else "⭐"
            
            prompt += f"""
EXEMPLE {i} [{emphasis} Score: {score:.2f}]
Question: "{query_text}"
SQL: 
```sql
{sql_query}
```
"""
        
        prompt += f"""
# REQUÊTE À TRADUIRE
Question: "{user_query}"

# INSTRUCTIONS FINALES
1. CONSULTE D'ABORD la documentation pour sélectionner le motif de requête le plus approprié pour cette demande
2. IDENTIFIE ENSUITE parmi les exemples la requête similaire avec la structure la plus adaptée
3. ADAPTE cette requête en gardant sa structure, ses jointures et son organisation
4. MODIFIE uniquement les colonnes, filtres et conditions nécessaires pour répondre à la nouvelle question
5. VÉRIFIE que tous les éléments du framework de sécurité sont présents (filtre ID_USER, table DEPOT, hashtags)
6. UTILISE les conventions d'aliasing recommandées dans la documentation
7. VÉRIFIE la cohérence avec le schéma et les exemples de la documentation
8. RETOURNE UNIQUEMENT la requête SQL finale sans aucune explication

SQL:"""
        
        return prompt
    
    except Exception as e:
        logger.error(f"Erreur lors de la construction du prompt: {e}")
        raise ValidationError(f"Impossible de construire le prompt: {e}", "build_prompt")


@cached(ttl=REDIS_TTL)  # Utilise la mise en cache Redis
async def translate_nl_to_sql(
    user_query: str, 
    schema_path: Optional[str] = None, 
    validate: bool = True, 
    explain: bool = True,
    store_result: bool = False,
    return_similar_queries: bool = False,
    user_id_placeholder: str = "?",
    use_cache: bool = True,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    include_similar_details: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Fonction principale asynchrone: traduit une requête en langage naturel en SQL 
    avec validation du framework obligatoire et gestion d'erreurs améliorée.
    
    Args:
        user_query: La requête en langage naturel à traduire
        schema_path: Chemin vers le fichier de schéma SQL ou Markdown (optionnel)
        validate: Valider la requête SQL générée
        explain: Fournir une explication de la requête SQL
        store_result: Stocker la paire requête-SQL dans Pinecone
        return_similar_queries: Inclure les requêtes similaires dans la réponse (format simplifié)
        user_id_placeholder: Placeholder pour l'ID utilisateur (par défaut "?")
        use_cache: Utiliser le cache Redis
        provider: Fournisseur LLM à utiliser (openai, anthropic, google)
        model: Modèle spécifique à utiliser
        include_similar_details: Inclure les détails complets des vecteurs similaires
        
    Returns:
        Dictionnaire contenant la requête SQL générée et les métadonnées associées
        
    Raises:
        ValidationError: Si les paramètres d'entrée sont invalides
        LLMError: Si erreur avec le fournisseur LLM
        VectorSearchError: Si erreur avec la recherche vectorielle
        SchemaError: Si erreur avec le chargement du schéma
    """
    # Validation des paramètres d'entrée
    if not user_query or not isinstance(user_query, str):
        raise ValidationError("user_query doit être une chaîne non vide", "user_query", user_query)
    
    if len(user_query.strip()) < 3:
        raise ValidationError("user_query doit contenir au moins 3 caractères", "user_query", user_query)
    
    if len(user_query) > 1000:
        raise ValidationError("user_query ne peut pas dépasser 1000 caractères", "user_query", len(user_query))
    
    # Chronométrer l'exécution
    start_time = time.time()
    
    # Initialiser le résultat avec les nouveaux champs
    result = {
        "sql": None,
        "valid": None, 
        "validation_message": None, 
        "explanation": None,
        "is_exact_match": False,
        "status": "error",
        "processing_time": None,
        "similar_queries": None,
        "similar_queries_details": None,
        "from_cache": False,
        "framework_compliant": False,
        "provider": provider or settings.DEFAULT_PROVIDER,
        "model": model
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
        try:
            is_relevant = await LLMService.check_relevance(user_query, provider=provider, model=model)
        except (LLMAuthError, LLMQuotaError) as e:
            logger.error(f"Erreur LLM lors de la vérification de pertinence: {e}")
            result["status"] = "error"
            result["validation_message"] = f"Service LLM temporairement indisponible: {e.message}"
            result["processing_time"] = time.time() - start_time
            return result
        except LLMNetworkError as e:
            logger.warning(f"Erreur réseau LLM, skip vérification pertinence: {e}")
            is_relevant = True  # Continuer en cas d'erreur réseau
        except LLMError as e:
            logger.error(f"Erreur LLM générique: {e}")
            result["status"] = "error"
            result["validation_message"] = f"Erreur du service LLM: {e.message}"
            result["processing_time"] = time.time() - start_time
            return result
        
        if not is_relevant:
            result["status"] = "error"
            result["validation_message"] = "Cette requête ne semble pas concerner les ressources humaines. Cette base de données contient uniquement des informations RH (employés, contrats, absences, paie, etc.)."
            result["processing_time"] = time.time() - start_time
            return result
        
        # Charger le schéma
        if schema_path is None:
            schema_path = settings.SCHEMA_PATH
        
        logger.info(f"Traduction de requête: '{user_query[:50]}...' (schéma: {schema_path}, provider: {provider or settings.DEFAULT_PROVIDER})")
        
        try:
            schema = await load_schema(schema_path)
        except FileNotFoundError as e:
            logger.error(f"Fichier de schéma introuvable: {e}")
            raise SchemaError(f"Fichier de schéma introuvable: {schema_path}", schema_path)
        except Exception as e:
            logger.error(f"Erreur lors du chargement du schéma: {e}")
            raise SchemaError(f"Impossible de charger le schéma: {e}", schema_path)
        
        # Récupérer les paramètres avec valeurs par défaut
        exact_match_threshold = settings.EXACT_MATCH_THRESHOLD
        
        # Vectoriser la requête
        try:
            query_vector = await get_embedding(user_query)
        except Exception as e:
            logger.error(f"Erreur lors de la vectorisation: {e}")
            raise EmbeddingError(f"Impossible de vectoriser la requête: {e}", settings.EMBEDDING_MODEL)
        
        # Rechercher les requêtes similaires
        try:
            similar_queries = await find_similar_queries(query_vector, settings.TOP_K_RESULTS)
        except Exception as e:
            logger.error(f"Erreur lors de la recherche vectorielle: {e}")
            raise VectorSearchError(f"Erreur lors de la recherche de requêtes similaires: {e}", settings.PINECONE_INDEX_NAME)
        
        # Stocker les détails complets des vecteurs similaires si demandé
        if include_similar_details:
            try:
                result["similar_queries_details"] = format_similar_queries_for_response(similar_queries, include_details=True)
            except VectorSearchError:
                # Erreur déjà loggée dans format_similar_queries_for_response
                result["similar_queries_details"] = None
        
        # Si demandé, inclure les requêtes similaires dans la réponse (format simplifié)
        if return_similar_queries:
            try:
                result["similar_queries"] = format_similar_queries_for_response(similar_queries, include_details=False)
            except VectorSearchError:
                # Erreur déjà loggée dans format_similar_queries_for_response
                result["similar_queries"] = None
        
        # Vérifier s'il y a une correspondance exacte
        try:
            exact_match = await check_exact_match(similar_queries, exact_match_threshold)
        except Exception as e:
            logger.warning(f"Erreur lors de la vérification de correspondance exacte: {e}")
            exact_match = None
        
        if exact_match:
            logger.info(f"Correspondance exacte trouvée pour la requête")
            
            # Validation de cohérence sémantique
            user_years = re.findall(r'\b(20\d{2})\b', user_query)
            sql_years = re.findall(r'\b(20\d{2})\b', exact_match)
            
            # Si des années sont mentionnées, vérifier qu'elles correspondent
            if user_years and sql_years and user_years[0] != sql_years[0]:
                logger.warning(f"Correspondance exacte avec année différente: {user_years[0]} vs {sql_years[0]}")
                exact_match = None
        
        if exact_match:
            # Valider le framework de la correspondance exacte
            try:
                framework_compliant, framework_message = validate_framework_compliance(exact_match)
                
                if not framework_compliant:
                    logger.warning(f"Correspondance exacte non conforme au framework: {framework_message}")
                    corrected_query = add_missing_framework_elements(exact_match)
                    framework_compliant, framework_message = validate_framework_compliance(corrected_query)
                    
                    if framework_compliant:
                        exact_match = corrected_query
                        logger.info(f"Correspondance exacte corrigée avec succès")
                    else:
                        logger.error(f"Impossible de corriger la correspondance exacte: {framework_message}")
                        raise FrameworkError(framework_message, exact_match)
            except Exception as e:
                if isinstance(e, FrameworkError):
                    raise
                logger.error(f"Erreur lors de la validation framework: {e}")
                raise FrameworkError(f"Erreur de validation framework: {e}", exact_match)
            
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
            try:
                prompt = await build_prompt(user_query, similar_queries, schema)
            except ValidationError:
                raise
            except Exception as e:
                logger.error(f"Erreur lors de la construction du prompt: {e}")
                raise ValidationError(f"Impossible de construire le prompt: {e}", "build_prompt")
            
            # Générer SQL avec LLMService
            try:
                sql_result = await LLMService.generate_sql(
                    user_query=user_query,
                    schema=schema,
                    similar_queries=similar_queries,
                    provider=provider,
                    model=model
                )
            except (LLMAuthError, LLMQuotaError) as e:
                logger.error(f"Erreur LLM lors de la génération SQL: {e}")
                result["status"] = "error"
                result["validation_message"] = f"Service LLM temporairement indisponible: {e.message}"
                result["processing_time"] = time.time() - start_time
                return result
            except LLMNetworkError as e:
                logger.error(f"Erreur réseau LLM: {e}")
                result["status"] = "error" 
                result["validation_message"] = f"Erreur de connexion au service LLM: {e.message}"
                result["processing_time"] = time.time() - start_time
                return result
            except LLMError as e:
                logger.error(f"Erreur LLM générique: {e}")
                result["status"] = "error"
                result["validation_message"] = f"Erreur du service LLM: {e.message}"
                result["processing_time"] = time.time() - start_time
                return result
            
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
            
            # Validation du framework obligatoire
            try:
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
                        raise FrameworkError(framework_message, sql_result)
            except Exception as e:
                if isinstance(e, FrameworkError):
                    raise
                logger.error(f"Erreur lors de la validation framework: {e}")
                raise FrameworkError(f"Erreur de validation framework: {e}", sql_result)
            
            result["framework_compliant"] = framework_compliant
            
            # Validation de sécurité (opérations destructives)
            try:
                sql_validator = SQLValidator(schema_content=schema, schema_path=schema_path)
                is_destructive, destructive_message = sql_validator.check_destructive_operations(sql_result)
                
                if is_destructive:
                    logger.warning(f"Requête destructive détectée: {sql_result}")
                    result["valid"] = False
                    result["validation_message"] = destructive_message
                    result["status"] = "error"
                    result["processing_time"] = time.time() - start_time
                    return result
            except Exception as e:
                logger.error(f"Erreur lors de la validation de sécurité: {e}")
                raise ValidationError(f"Erreur lors de la validation de sécurité: {e}", "security_validation")
                
            result["sql"] = sql_result
            
            # Valider la requête générée si demandé (validation de cohérence supplémentaire)
            if validate:
                try:
                    semantic_valid, semantic_message = await LLMService.validate_sql_semantically(
                        sql_result, 
                        user_query, 
                        schema,
                        provider=provider,
                        model=model
                    )
                except (LLMAuthError, LLMQuotaError, LLMNetworkError) as e:
                    logger.warning(f"Erreur LLM lors de la validation sémantique, skip: {e}")
                    semantic_valid = True
                    semantic_message = "Validation sémantique ignorée due à une erreur LLM"
                except LLMError as e:
                    logger.warning(f"Erreur LLM lors de la validation sémantique: {e}")
                    semantic_valid = True
                    semantic_message = "Validation sémantique ignorée due à une erreur LLM"
                
                # Mise à jour des résultats  
                result["valid"] = semantic_valid
                result["validation_message"] = semantic_message
                
                # Ajuster le message pour inclure le respect du framework
                if result["valid"] and framework_compliant:
                    result["validation_message"] = f"{semantic_message} La requête respecte le framework obligatoire."
                elif result["valid"] and not framework_compliant:
                    result["validation_message"] = f"{semantic_message} Attention: {framework_message}"
            else:
                # Si la validation est désactivée, considérer la requête comme valide
                result["valid"] = True
                result["validation_message"] = "Validation désactivée. La requête est considérée comme valide et respecte le framework obligatoire."
            
            # Toujours considérer la requête comme valide tant qu'elle respecte le framework et n'est pas destructive
            result["status"] = "success"
            
            # Si la requête est valide et qu'on doit la stocker, on l'ajoute à Pinecone
            if store_result and result["valid"] and sql_result:
                try:
                    await store_query(user_query, query_vector, sql_result)
                except Exception as e:
                    logger.warning(f"Erreur lors du stockage en base vectorielle: {e}")
                    # Ne pas faire échouer la requête pour ça
        
        # Obtenir une explication de la requête si demandé
        if explain and result["sql"] is not None:
            try:
                explanation = await LLMService.explain_sql(
                    result["sql"], 
                    user_query,
                    provider=provider,
                    model=model
                )
                result["explanation"] = explanation
            except (LLMAuthError, LLMQuotaError, LLMNetworkError, LLMError) as e:
                logger.warning(f"Erreur LLM lors de l'explication, skip: {e}")
                result["explanation"] = "Explication non disponible due à une erreur du service LLM."
            except Exception as e:
                logger.warning(f"Erreur lors de l'explication: {e}")
                result["explanation"] = "Explication non disponible."
    
    except (ValidationError, FrameworkError, LLMError, VectorSearchError, EmbeddingError, SchemaError) as e:
        # Erreurs connues et gérées
        logger.error(f"Erreur lors de la traduction: {e}")
        result["status"] = "error"
        result["validation_message"] = str(e)
    
    except Exception as e:
        # Erreurs inattendues
        logger.error(f"Erreur inattendue lors de la traduction de la requête: {str(e)}", exc_info=True)
        result["status"] = "error"
        result["validation_message"] = f"Erreur interne: {str(e)}"
    
    finally:
        # Calculer le temps de traitement
        end_time = time.time()
        processing_time = end_time - start_time
        result["processing_time"] = round(processing_time, 3)
        
        # Log détaillé avec informations sur le framework
        framework_status = "conforme" if result.get("framework_compliant", False) else "non conforme"
        similar_count = len(result.get("similar_queries_details", [])) if result.get("similar_queries_details") else 0
        logger.info(f"Traduction terminée en {processing_time:.3f}s (statut: {result['status']}, framework: {framework_status}, vecteurs similaires: {similar_count})")
    
    return result


async def health_check() -> Dict[str, Any]:
    """
    Vérifie l'état de santé des services dépendants avec gestion d'erreurs améliorée.
    
    Returns:
        Dictionnaire contenant l'état de santé des services
    """
    from app.core.embedding import check_embedding_service
    from app.core.vector_search import check_pinecone_service
    from app.utils.cache import get_redis_client
    
    # Vérifier les services avec gestion d'erreurs individuelles
    services_status = {}
    
    # Service d'embedding
    try:
        embedding_status = await check_embedding_service()
        services_status["embedding"] = embedding_status
    except EmbeddingError as e:
        logger.error(f"Erreur service embedding: {e}")
        services_status["embedding"] = {"status": "error", "error": str(e)}
    except Exception as e:
        logger.error(f"Erreur inattendue embedding: {e}")
        services_status["embedding"] = {"status": "error", "error": f"Erreur inattendue: {e}"}
    
    # Service Pinecone
    try:
        pinecone_status = await check_pinecone_service()
        services_status["pinecone"] = pinecone_status
    except VectorSearchError as e:
        logger.error(f"Erreur service Pinecone: {e}")
        services_status["pinecone"] = {"status": "error", "error": str(e)}
    except Exception as e:
        logger.error(f"Erreur inattendue Pinecone: {e}")
        services_status["pinecone"] = {"status": "error", "error": f"Erreur inattendue: {e}"}
    
    # Service LLM
    try:
        llm_status = await LLMService.check_services_health()
        services_status["llm"] = llm_status
    except (LLMError, LLMConfigError) as e:
        logger.error(f"Erreur service LLM: {e}")
        services_status["llm"] = {"status": "error", "error": str(e)}
    except Exception as e:
        logger.error(f"Erreur inattendue LLM: {e}")
        services_status["llm"] = {"status": "error", "error": f"Erreur inattendue: {e}"}
    
    # Service Redis
    redis_status = {"status": "disabled"}
    if os.getenv("CACHE_ENABLED", "true").lower() == "true":
        try:
            redis_client = await get_redis_client()
            if redis_client:
                await redis_client.ping()
                redis_status = {
                    "status": "ok",
                    "url": os.getenv("REDIS_URL", "redis://localhost:6379/0").split("@")[-1]
                }
            else:
                redis_status = {"status": "error", "message": "Client Redis non initialisé"}
        except Exception as e:
            logger.warning(f"Erreur Redis (non critique): {e}")
            redis_status = {"status": "error", "message": str(e)}
    
    services_status["redis"] = redis_status
    
    # Déterminer le statut global
    critical_services = ["embedding", "pinecone", "llm"]
    all_critical_ok = all(
        services_status.get(service, {}).get("status") == "ok" 
        for service in critical_services
    )
    
    # Redis n'est pas critique
    redis_ok = services_status.get("redis", {}).get("status") in ["ok", "disabled"]
    
    global_status = "ok" if all_critical_ok and redis_ok else "error"
    
    return {
        "status": global_status,
        "version": "2.0.0",
        "services": services_status
    }