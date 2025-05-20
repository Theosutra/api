import asyncio
import concurrent.futures
from typing import List, Dict, Any, Optional
import logging
from pinecone import Pinecone, PodSpec

from app.config import get_settings

# Configuration du logger
logger = logging.getLogger(__name__)

# Récupérer les paramètres de configuration
settings = get_settings()

# Client Pinecone (initialisé de manière paresseuse)
_pc = None
_index = None


def _init_pinecone():
    """
    Initialise le client Pinecone et l'index de manière paresseuse.
    
    Returns:
        L'index Pinecone initialisé
        
    Raises:
        RuntimeError: Si Pinecone ne peut pas être initialisé
    """
    global _pc, _index
    if _pc is None:
        try:
            logger.info(f"Initialisation de Pinecone avec l'index '{settings.PINECONE_INDEX_NAME}'")
            _pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            
            # Vérifier si l'index existe
            indexes = _pc.list_indexes()
            index_exists = any(idx.name == settings.PINECONE_INDEX_NAME for idx in indexes)
            
            if not index_exists:
                logger.warning(f"L'index '{settings.PINECONE_INDEX_NAME}' n'existe pas, création...")
                # Créer l'index s'il n'existe pas
                _pc.create_index(
                    name=settings.PINECONE_INDEX_NAME,
                    dimension=768,  
                    metric="cosine",
                    spec=PodSpec(
                        environment=settings.PINECONE_ENVIRONMENT
                    )
                )
            
            _index = _pc.Index(settings.PINECONE_INDEX_NAME)
            logger.info(f"Index Pinecone initialisé avec succès")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de Pinecone: {str(e)}")
            raise RuntimeError(f"Erreur lors de l'initialisation de Pinecone: {str(e)}")
    
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
    """
    index = _init_pinecone()
    
    try:
        results = index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True
        )
        
        return results['matches']
    
    except Exception as e:
        logger.error(f"Erreur lors de la recherche de requêtes similaires: {str(e)}")
        raise RuntimeError(f"Erreur lors de la recherche dans Pinecone: {str(e)}")


async def find_similar_queries(query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Recherche les requêtes SQL les plus similaires dans Pinecone de manière asynchrone.
    
    Args:
        query_vector: Vecteur d'embedding de la requête
        top_k: Nombre de résultats à retourner
        
    Returns:
        Liste des requêtes similaires avec leurs métadonnées
    """
    logger.debug(f"Recherche des {top_k} requêtes les plus similaires dans Pinecone")
    
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            similar_queries = await asyncio.get_event_loop().run_in_executor(
                executor, _find_similar_queries_sync, query_vector, top_k
            )
        
        logger.debug(f"Requêtes similaires trouvées: {len(similar_queries)}")
        return similar_queries
    
    except Exception as e:
        logger.error(f"Erreur lors de la recherche de requêtes similaires: {str(e)}")
        raise


async def check_exact_match(similar_queries: List[Dict[str, Any]], threshold: float = 0.95) -> Optional[str]:
    """
    Vérifie si l'une des requêtes similaires correspond exactement à la demande.
    
    Args:
        similar_queries: Liste des requêtes similaires
        threshold: Seuil de similarité pour considérer une correspondance exacte
        
    Returns:
        La requête SQL correspondante si une correspondance exacte est trouvée, None sinon
    """
    if not similar_queries or len(similar_queries) == 0:
        logger.debug("Aucune requête similaire trouvée")
        return None
    
    # Vérifier si le premier résultat a un score très élevé (> threshold)
    top_match = similar_queries[0]
    
    if top_match['score'] > threshold:
        logger.info(f"Correspondance exacte trouvée avec un score de {top_match['score']:.4f}")
        return top_match['metadata'].get('requete', None)
    
    logger.debug(f"Pas de correspondance exacte (meilleur score: {top_match['score']:.4f})")
    return None


async def store_query(
    query_text: str, 
    query_vector: List[float], 
    sql_query: str, 
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Stocke une nouvelle requête dans Pinecone.
    
    Args:
        query_text: Texte de la requête en langage naturel
        query_vector: Vecteur d'embedding de la requête
        sql_query: Requête SQL correspondante
        metadata: Métadonnées supplémentaires à stocker
        
    Returns:
        True si la requête a été stockée avec succès, False sinon
    """
    index = _init_pinecone()
    
    # Préparer les métadonnées
    if metadata is None:
        metadata = {}
    
    metadata.update({
        'texte_complet': query_text,
        'requete': sql_query
    })
    
    # Générer un ID unique (on peut utiliser un hash du texte de la requête)
    import hashlib
    query_id = hashlib.md5(query_text.encode('utf-8')).hexdigest()
    
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            await asyncio.get_event_loop().run_in_executor(
                executor,
                lambda: index.upsert(
                    vectors=[
                        {
                            'id': query_id,
                            'values': query_vector,
                            'metadata': metadata
                        }
                    ]
                )
            )
        
        logger.info(f"Requête stockée avec succès dans Pinecone (ID: {query_id})")
        return True
    
    except Exception as e:
        logger.error(f"Erreur lors du stockage de la requête dans Pinecone: {str(e)}")
        return False


async def check_pinecone_service() -> dict:
    """
    Vérifie que le service Pinecone fonctionne correctement.
    
    Returns:
        Dictionnaire indiquant le statut du service
    """
    try:
        # Initialiser Pinecone
        index = _init_pinecone()
        
        # Vérifier que l'index est accessible
        stats = index.describe_index_stats()
        
        return {
            "status": "ok",
            "index": settings.PINECONE_INDEX_NAME,
            "vector_count": stats.get('total_vector_count', 0),
            "dimensions": stats.get('dimension', 0)
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du service Pinecone: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }