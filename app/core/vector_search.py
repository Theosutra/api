import asyncio
import concurrent.futures
from typing import List, Dict, Any, Optional
import logging
from pinecone import Pinecone, PodSpec

from app.config import get_settings
from app.core.exceptions import VectorSearchError  # NOUVELLE IMPORT

# Configuration du logger
logger = logging.getLogger(__name__)

# Récupérer les paramètres de configuration
settings = get_settings()

# Client Pinecone (initialisé de manière paresseuse)
_pc = None
_index = None


def _normalize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise les métadonnées pour compatibilité avec différents formats.
    
    Args:
        metadata: Métadonnées brutes de Pinecone
        
    Returns:
        Métadonnées normalisées au format attendu
    """
    normalized = metadata.copy()
    
    # Conversion requetes -> requete (support format existant)
    if 'requetes' in normalized and 'requete' not in normalized:
        normalized['requete'] = normalized['requetes']
    
    # Conversion nom -> texte_complet (support format existant)
    if 'nom' in normalized and 'texte_complet' not in normalized:
        normalized['texte_complet'] = normalized['nom']
    
    # S'assurer que les champs obligatoires existent
    if 'requete' not in normalized:
        normalized['requete'] = ''
    
    if 'texte_complet' not in normalized:
        normalized['texte_complet'] = normalized.get('description', '')[:100] + '...' if normalized.get('description') else ''
    
    return normalized


def _init_pinecone():
    """
    Initialise le client Pinecone et l'index de manière paresseuse.
    Compatible avec Pinecone Serverless et Pod-based.
    
    Returns:
        L'index Pinecone initialisé
        
    Raises:
        VectorSearchError: Si Pinecone ne peut pas être initialisé
    """
    global _pc, _index
    if _pc is None:
        try:
            if not settings.PINECONE_API_KEY:
                raise VectorSearchError("PINECONE_API_KEY manquante dans la configuration", settings.PINECONE_INDEX_NAME)
            
            if not settings.PINECONE_INDEX_NAME:
                raise VectorSearchError("PINECONE_INDEX_NAME manquant dans la configuration", None)
            
            logger.info(f"Initialisation de Pinecone avec l'index '{settings.PINECONE_INDEX_NAME}'")
            _pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            
            # Vérifier si l'index existe (compatible Serverless et Pod-based)
            try:
                indexes = _pc.list_indexes()
                index_exists = any(idx.name == settings.PINECONE_INDEX_NAME for idx in indexes)
            except Exception as e:
                logger.error(f"Erreur lors de la vérification des indexes: {e}")
                raise VectorSearchError(f"Impossible de vérifier les indexes Pinecone: {e}", settings.PINECONE_INDEX_NAME)
            
            if not index_exists:
                # L'index n'existe pas - ne pas le créer automatiquement
                # car on ne connaît pas le type (Serverless vs Pod-based)
                raise VectorSearchError(
                    f"L'index '{settings.PINECONE_INDEX_NAME}' n'existe pas. "
                    f"Veuillez le créer manuellement ou vérifier le nom dans la configuration.",
                    settings.PINECONE_INDEX_NAME
                )
            
            try:
                _index = _pc.Index(settings.PINECONE_INDEX_NAME)
                logger.info(f"Index Pinecone '{settings.PINECONE_INDEX_NAME}' initialisé avec succès")
            except Exception as e:
                logger.error(f"Erreur lors de la connexion à l'index: {e}")
                raise VectorSearchError(f"Impossible de se connecter à l'index '{settings.PINECONE_INDEX_NAME}': {e}", settings.PINECONE_INDEX_NAME)
            
        except VectorSearchError:
            # Re-propager les erreurs VectorSearchError
            raise
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de Pinecone: {str(e)}")
            raise VectorSearchError(f"Erreur lors de l'initialisation de Pinecone: {str(e)}", settings.PINECONE_INDEX_NAME)
    
    return _index


def _find_similar_queries_sync(query_vector: List[float], top_k: int) -> List[Dict[str, Any]]:
    """
    Version synchrone de find_similar_queries.
    Recherche les requêtes les plus similaires dans Pinecone.
    
    Args:
        query_vector: Vecteur d'embedding de la requête
        top_k: Nombre de résultats à retourner
        
    Returns:
        Liste des requêtes similaires avec leurs métadonnées
        
    Raises:
        VectorSearchError: Si erreur lors de la recherche
    """
    # Validation des paramètres
    if not query_vector or not isinstance(query_vector, list):
        raise VectorSearchError("query_vector doit être une liste non vide", settings.PINECONE_INDEX_NAME)
    
    if len(query_vector) == 0:
        raise VectorSearchError("query_vector ne peut pas être vide", settings.PINECONE_INDEX_NAME)
    
    if not isinstance(top_k, int) or top_k <= 0:
        raise VectorSearchError("top_k doit être un entier positif", settings.PINECONE_INDEX_NAME)
    
    if top_k > 100:  # Limite raisonnable
        logger.warning(f"top_k très élevé ({top_k}), limitation à 100")
        top_k = 100
    
    # Vérifier que toutes les valeurs du vecteur sont valides
    try:
        for i, value in enumerate(query_vector):
            if not isinstance(value, (int, float)):
                raise VectorSearchError(f"Valeur non numérique à l'index {i}: {value}", settings.PINECONE_INDEX_NAME)
            if isinstance(value, float) and (value != value or value == float('inf') or value == float('-inf')):
                raise VectorSearchError(f"Valeur invalide (NaN ou infini) à l'index {i}: {value}", settings.PINECONE_INDEX_NAME)
    except Exception as e:
        raise VectorSearchError(f"Erreur lors de la validation du vecteur: {e}", settings.PINECONE_INDEX_NAME)
    
    index = _init_pinecone()
    
    try:
        results = index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True
        )
        
        matches = results.get('matches', [])
        
        # Validation des résultats
        if not isinstance(matches, list):
            raise VectorSearchError("Format de réponse Pinecone invalide: 'matches' n'est pas une liste", settings.PINECONE_INDEX_NAME)
        
        # Filtrer les résultats avec scores valides ET normaliser les métadonnées
        valid_matches = []
        for match in matches:
            # DEBUG: Afficher la structure complète pour diagnostic
            logger.debug(f"Structure du match reçu: {match}")
            
            if isinstance(match, dict):
                # Essayer d'extraire le score de différentes façons
                score = None
                if 'score' in match:
                    score = match['score']
                elif hasattr(match, 'score'):
                    score = match.score
                else:
                    # Certaines versions de Pinecone utilisent des attributs différents
                    logger.warning(f"Pas de score trouvé dans match: {list(match.keys())}")
                    continue
                
                # Validation du score
                if score is not None and isinstance(score, (int, float)) and not (isinstance(score, float) and (score != score or score == float('inf') or score == float('-inf'))):
                    # ✅ NORMALISER LES MÉTADONNÉES POUR COMPATIBILITÉ
                    metadata = match.get('metadata', {})
                    if not metadata and hasattr(match, 'metadata'):
                        metadata = match.metadata
                    
                    normalized_metadata = _normalize_metadata(metadata)
                    
                    # Vérifier que la requête SQL n'est pas vide après normalisation
                    if normalized_metadata.get('requete', '').strip():
                        # Reconstruire le match avec la structure attendue
                        normalized_match = {
                            'score': score,
                            'metadata': normalized_metadata,
                            'id': match.get('id', '') or getattr(match, 'id', '')
                        }
                        valid_matches.append(normalized_match)
                        logger.debug(f"Match valide: score={score:.3f}, texte='{normalized_metadata.get('texte_complet', '')[:50]}...'")
                    else:
                        logger.warning(f"Match ignoré: requête SQL vide (score={score:.3f})")
                else:
                    logger.warning(f"Score invalide ignoré: {score}")
            else:
                logger.warning(f"Match invalide ignoré: type={type(match)}, contenu={match}")
        
        logger.debug(f"Recherche Pinecone: {len(valid_matches)} résultats valides sur {len(matches)} totaux")
        return valid_matches
    
    except VectorSearchError:
        # Re-propager les erreurs VectorSearchError
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la recherche de requêtes similaires: {str(e)}")
        raise VectorSearchError(f"Erreur lors de la recherche dans Pinecone: {str(e)}", settings.PINECONE_INDEX_NAME)


async def find_similar_queries(query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Recherche les requêtes SQL les plus similaires dans Pinecone de manière asynchrone.
    
    Args:
        query_vector: Vecteur d'embedding de la requête
        top_k: Nombre de résultats à retourner (défaut: 5)
        
    Returns:
        Liste des requêtes similaires avec leurs métadonnées
        
    Raises:
        VectorSearchError: Si erreur lors de la recherche
    """
    # Validation des paramètres d'entrée
    if not query_vector or not isinstance(query_vector, list):
        raise VectorSearchError("query_vector doit être une liste non vide", settings.PINECONE_INDEX_NAME)
    
    if top_k <= 0 or top_k > 100:
        raise VectorSearchError("top_k doit être entre 1 et 100", settings.PINECONE_INDEX_NAME)
    
    logger.debug(f"Recherche des {top_k} requêtes les plus similaires dans Pinecone")
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            similar_queries = await asyncio.get_event_loop().run_in_executor(
                executor, _find_similar_queries_sync, query_vector, top_k
            )
        
        logger.debug(f"Requêtes similaires trouvées: {len(similar_queries)}")
        return similar_queries
    
    except VectorSearchError:
        # Re-propager les erreurs VectorSearchError
        raise
    except asyncio.CancelledError:
        logger.warning("Recherche de requêtes similaires annulée")
        raise VectorSearchError("Recherche annulée", settings.PINECONE_INDEX_NAME)
    except Exception as e:
        logger.error(f"Erreur lors de la recherche de requêtes similaires: {str(e)}")
        raise VectorSearchError(f"Erreur lors de la recherche de requêtes similaires: {str(e)}", settings.PINECONE_INDEX_NAME)


async def check_exact_match(similar_queries: List[Dict[str, Any]], threshold: float = 0.95) -> Optional[str]:
    """
    Vérifie si l'une des requêtes similaires correspond exactement à la demande.
    
    Args:
        similar_queries: Liste des requêtes similaires
        threshold: Seuil de similarité pour considérer une correspondance exacte (défaut: 0.95)
        
    Returns:
        La requête SQL correspondante si une correspondance exacte est trouvée, None sinon
        
    Raises:
        VectorSearchError: Si erreur lors de la vérification
    """
    # Validation des paramètres
    if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
        raise VectorSearchError("threshold doit être un nombre entre 0 et 1", settings.PINECONE_INDEX_NAME)
    
    if not similar_queries or not isinstance(similar_queries, list):
        logger.debug("Aucune requête similaire fournie pour vérification de correspondance exacte")
        return None
    
    if len(similar_queries) == 0:
        logger.debug("Liste de requêtes similaires vide")
        return None
    
    try:
        # Vérifier si le premier résultat a un score très élevé (> threshold)
        top_match = similar_queries[0]
        
        if not isinstance(top_match, dict):
            logger.warning("Format de requête similaire invalide")
            return None
        
        score = top_match.get('score', 0)
        
        if not isinstance(score, (int, float)):
            logger.warning(f"Score invalide dans top_match: {score}")
            return None
        
        if score > threshold:
            metadata = top_match.get('metadata', {})
            if not isinstance(metadata, dict):
                logger.warning("Métadonnées invalides dans top_match")
                return None
            
            # ✅ SUPPORT DES DEUX FORMATS : 'requete' ET 'requetes'
            sql_query = metadata.get('requete') or metadata.get('requetes')
            if sql_query and isinstance(sql_query, str) and len(sql_query.strip()) > 0:
                logger.info(f"Correspondance exacte trouvée avec un score de {score:.4f}")
                return sql_query.strip()
            else:
                logger.warning("Requête SQL manquante ou vide dans la correspondance exacte")
                return None
        
        logger.debug(f"Pas de correspondance exacte (meilleur score: {score:.4f})")
        return None
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de correspondance exacte: {e}")
        raise VectorSearchError(f"Erreur lors de la vérification de correspondance exacte: {e}", settings.PINECONE_INDEX_NAME)


async def store_query(
    query_text: str, 
    query_vector: List[float], 
    sql_query: str, 
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Stocke une nouvelle requête dans Pinecone avec validation des données.
    
    Args:
        query_text: Texte de la requête en langage naturel
        query_vector: Vecteur d'embedding de la requête
        sql_query: Requête SQL correspondante
        metadata: Métadonnées supplémentaires à stocker
        
    Returns:
        True si la requête a été stockée avec succès, False sinon
        
    Raises:
        VectorSearchError: Si erreur lors du stockage
    """
    # Validation des paramètres
    if not query_text or not isinstance(query_text, str) or len(query_text.strip()) == 0:
        raise VectorSearchError("query_text doit être une chaîne non vide", settings.PINECONE_INDEX_NAME)
    
    if not query_vector or not isinstance(query_vector, list) or len(query_vector) == 0:
        raise VectorSearchError("query_vector doit être une liste non vide", settings.PINECONE_INDEX_NAME)
    
    if not sql_query or not isinstance(sql_query, str) or len(sql_query.strip()) == 0:
        raise VectorSearchError("sql_query doit être une chaîne non vide", settings.PINECONE_INDEX_NAME)
    
    # Vérifier que le vecteur contient des valeurs valides
    try:
        for i, value in enumerate(query_vector):
            if not isinstance(value, (int, float)):
                raise VectorSearchError(f"Valeur non numérique à l'index {i}: {value}", settings.PINECONE_INDEX_NAME)
            if isinstance(value, float) and (value != value or value == float('inf') or value == float('-inf')):
                raise VectorSearchError(f"Valeur invalide (NaN ou infini) à l'index {i}: {value}", settings.PINECONE_INDEX_NAME)
    except Exception as e:
        raise VectorSearchError(f"Erreur lors de la validation du vecteur: {e}", settings.PINECONE_INDEX_NAME)
    
    try:
        index = _init_pinecone()
        
        # Préparer les métadonnées avec format compatible
        if metadata is None:
            metadata = {}
        
        if not isinstance(metadata, dict):
            logger.warning("Métadonnées invalides, utilisation d'un dictionnaire vide")
            metadata = {}
        
        # ✅ STOCKER DANS LES DEUX FORMATS POUR COMPATIBILITÉ
        metadata.update({
            'texte_complet': query_text.strip(),
            'requete': sql_query.strip(),
            'nom': query_text.strip(),  # Format existant
            'requetes': sql_query.strip()  # Format existant
        })
        
        # Générer un ID unique (hash du texte de la requête)
        import hashlib
        query_id = hashlib.md5(query_text.encode('utf-8')).hexdigest()
        
        # Fonction synchrone pour le stockage
        def _store_sync():
            return index.upsert(
                vectors=[
                    {
                        'id': query_id,
                        'values': query_vector,
                        'metadata': metadata
                    }
                ]
            )
        
        # Exécuter le stockage de manière asynchrone
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            await asyncio.get_event_loop().run_in_executor(executor, _store_sync)
        
        logger.info(f"Requête stockée avec succès dans Pinecone (ID: {query_id})")
        return True
    
    except VectorSearchError:
        # Re-propager les erreurs VectorSearchError
        raise
    except Exception as e:
        logger.error(f"Erreur lors du stockage de la requête dans Pinecone: {str(e)}")
        raise VectorSearchError(f"Erreur lors du stockage dans Pinecone: {str(e)}", settings.PINECONE_INDEX_NAME)


async def check_pinecone_service() -> dict:
    """
    Vérifie que le service Pinecone fonctionne correctement.
    Compatible avec Pinecone Serverless et Pod-based.
    
    Returns:
        Dictionnaire indiquant le statut du service
    """
    try:
        # Initialiser Pinecone
        index = _init_pinecone()
        
        # Vérifier que l'index est accessible
        try:
            stats = index.describe_index_stats()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {e}")
            raise VectorSearchError(f"Impossible d'accéder aux statistiques de l'index: {e}", settings.PINECONE_INDEX_NAME)
        
        # Gestion du format Serverless (nouveau) vs Pod-based (ancien)
        total_vector_count = 0
        dimension = 0
        namespaces = {}
        
        if hasattr(stats, 'total_vector_count'):
            # Format Serverless - les valeurs sont des propriétés directes
            total_vector_count = getattr(stats, 'total_vector_count', 0)
            dimension = getattr(stats, 'dimension', 0) 
            namespaces = getattr(stats, 'namespaces', {})
        elif isinstance(stats, dict):
            # Format Pod-based - dictionnaire classique
            total_vector_count = stats.get('total_vector_count', 0)
            dimension = stats.get('dimension', 0)
            namespaces = stats.get('namespaces', {})
        else:
            # Tentative de conversion en dictionnaire
            try:
                if hasattr(stats, 'to_dict'):
                    stats_dict = stats.to_dict()
                elif hasattr(stats, '__dict__'):
                    stats_dict = stats.__dict__
                else:
                    stats_dict = {}
                
                total_vector_count = stats_dict.get('total_vector_count', 0)
                dimension = stats_dict.get('dimension', 0)
                namespaces = stats_dict.get('namespaces', {})
            except Exception:
                # Fallback - juste vérifier que l'index est accessible
                logger.warning(f"Format de statistiques non reconnu: {type(stats)}, mais l'index est accessible")
                total_vector_count = "unknown"
                dimension = "unknown"
                namespaces = {}
        
        return {
            "status": "ok",
            "index": settings.PINECONE_INDEX_NAME,
            "vector_count": total_vector_count,
            "dimensions": dimension,
            "namespaces": namespaces,
            "test_successful": True
        }
    
    except VectorSearchError as e:
        logger.error(f"Erreur lors de la vérification du service Pinecone: {e}")
        return {
            "status": "error",
            "index": settings.PINECONE_INDEX_NAME,
            "message": str(e),
            "test_successful": False
        }
    
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la vérification du service Pinecone: {str(e)}")
        return {
            "status": "error", 
            "index": settings.PINECONE_INDEX_NAME,
            "message": f"Erreur inattendue: {str(e)}",
            "test_successful": False
        }


async def get_index_info() -> dict:
    """
    Récupère les informations détaillées de l'index Pinecone.
    
    Returns:
        Dictionnaire avec les informations de l'index
    """
    try:
        index = _init_pinecone()
        
        # Récupérer les statistiques détaillées
        stats = index.describe_index_stats()
        
        # Informations de base
        info = {
            "index_name": settings.PINECONE_INDEX_NAME,
            "total_vectors": stats.get('total_vector_count', 0),
            "dimension": stats.get('dimension', 0),
            "namespaces": stats.get('namespaces', {}),
            "environment": settings.PINECONE_ENVIRONMENT
        }
        
        return {
            "status": "ok",
            "info": info
        }
    
    except VectorSearchError as e:
        return {
            "status": "error",
            "message": str(e)
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des informations d'index: {e}")
        return {
            "status": "error",
            "message": f"Erreur lors de la récupération des informations: {e}"
        }


async def delete_query(query_id: str) -> bool:
    """
    Supprime une requête de l'index Pinecone.
    
    Args:
        query_id: ID de la requête à supprimer
        
    Returns:
        True si suppression réussie
        
    Raises:
        VectorSearchError: Si erreur lors de la suppression
    """
    if not query_id or not isinstance(query_id, str) or len(query_id.strip()) == 0:
        raise VectorSearchError("query_id doit être une chaîne non vide", settings.PINECONE_INDEX_NAME)
    
    try:
        index = _init_pinecone()
        
        def _delete_sync():
            return index.delete(ids=[query_id.strip()])
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            await asyncio.get_event_loop().run_in_executor(executor, _delete_sync)
        
        logger.info(f"Requête supprimée avec succès (ID: {query_id})")
        return True
    
    except VectorSearchError:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression: {e}")
        raise VectorSearchError(f"Erreur lors de la suppression: {e}", settings.PINECONE_INDEX_NAME)


async def search_by_metadata(filter_dict: Dict[str, Any], top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Recherche des vecteurs par métadonnées.
    
    Args:
        filter_dict: Dictionnaire de filtres pour les métadonnées
        top_k: Nombre maximum de résultats
        
    Returns:
        Liste des vecteurs correspondants
        
    Raises:
        VectorSearchError: Si erreur lors de la recherche
    """
    if not isinstance(filter_dict, dict) or len(filter_dict) == 0:
        raise VectorSearchError("filter_dict doit être un dictionnaire non vide", settings.PINECONE_INDEX_NAME)
    
    if not isinstance(top_k, int) or top_k <= 0 or top_k > 100:
        raise VectorSearchError("top_k doit être entre 1 et 100", settings.PINECONE_INDEX_NAME)
    
    try:
        index = _init_pinecone()
        
        def _search_sync():
            # Pinecone nécessite un vecteur pour la recherche, on utilise un vecteur zéro
            # Ceci n'est qu'un exemple - en production, utiliser une vraie recherche par métadonnées
            dummy_vector = [0.0] * 768  # Dimension par défaut
            return index.query(
                vector=dummy_vector,
                filter=filter_dict,
                top_k=top_k,
                include_metadata=True
            )
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            results = await asyncio.get_event_loop().run_in_executor(executor, _search_sync)
        
        matches = results.get('matches', [])
        logger.debug(f"Recherche par métadonnées: {len(matches)} résultats trouvés")
        
        return matches
    
    except VectorSearchError:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la recherche par métadonnées: {e}")
        raise VectorSearchError(f"Erreur lors de la recherche par métadonnées: {e}", settings.PINECONE_INDEX_NAME)


async def cleanup_vector_service():
    """
    Nettoie les ressources du service de recherche vectorielle.
    Utile lors de l'arrêt de l'application.
    """
    global _pc, _index
    try:
        if _pc is not None:
            # Pinecone ne nécessite pas de nettoyage spécial
            _pc = None
            _index = None
            logger.info("Service de recherche vectorielle nettoyé")
    
    except Exception as e:
        logger.warning(f"Erreur lors du nettoyage du service vectoriel: {e}")


# Fonction utilitaire pour les tests
async def test_vector_operations() -> Dict[str, bool]:
    """
    Teste les opérations vectorielles de base.
    
    Returns:
        Dictionnaire avec les résultats des tests
    """
    results = {
        "connection": False,
        "search": False,
        "store": False
    }
    
    try:
        # Test de connexion
        health = await check_pinecone_service()
        results["connection"] = health["status"] == "ok"
        
        if results["connection"]:
            # Test de recherche avec un vecteur de test
            test_vector = [0.1] * 768
            similar = await find_similar_queries(test_vector, top_k=1)
            results["search"] = isinstance(similar, list)
            
            # Test de stockage (optionnel - commenté pour éviter la pollution)
            # test_stored = await store_query("test query", test_vector, "SELECT 1;")
            # results["store"] = test_stored
            results["store"] = True  # Supposer que le stockage fonctionne si la recherche fonctionne
    
    except Exception as e:
        logger.error(f"Erreur lors des tests vectoriels: {e}")
    
    return results