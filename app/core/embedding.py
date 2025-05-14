import asyncio
from typing import List, Optional
import concurrent.futures
import logging
from sentence_transformers import SentenceTransformer

from app.config import get_settings

# Configuration du logger
logger = logging.getLogger(__name__)

# Récupérer les paramètres de configuration
settings = get_settings()

# Modèle d'embedding (initialisé de manière paresseuse)
_model = None


def _load_model() -> SentenceTransformer:
    """
    Charge le modèle SentenceTransformer de manière paresseuse.
    Initialise le modèle lors du premier appel.
    
    Returns:
        Une instance du modèle SentenceTransformer
        
    Raises:
        RuntimeError: Si le modèle ne peut pas être chargé
    """
    global _model
    if _model is None:
        try:
            logger.info(f"Chargement du modèle d'embedding '{settings.EMBEDDING_MODEL}'")
            _model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info(f"Modèle d'embedding chargé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle d'embedding: {str(e)}")
            raise RuntimeError(f"Erreur lors de l'initialisation du modèle d'embedding: {str(e)}")
    return _model


def _get_embedding_sync(text: str) -> List[float]:
    """
    Version synchrone de get_embedding.
    Convertit un texte en un vecteur d'embedding.
    
    Args:
        text: Texte à convertir en vecteur
        
    Returns:
        Vecteur d'embedding sous forme de liste de flottants
    """
    model = _load_model()
    try:
        return model.encode(text).tolist()
    except Exception as e:
        logger.error(f"Erreur lors de la vectorisation du texte: {str(e)}")
        raise RuntimeError(f"Erreur lors de la vectorisation du texte: {str(e)}")


async def get_embedding(text: str) -> List[float]:
    """
    Obtient un embedding vectoriel pour un texte donné de manière asynchrone.
    Utilise un thread séparé pour ne pas bloquer la boucle asyncio.
    
    Args:
        text: Texte à convertir en vecteur
        
    Returns:
        Vecteur d'embedding sous forme de liste de flottants
        
    Raises:
        RuntimeError: Si une erreur se produit lors de la vectorisation
    """
    # Exécuter la fonction synchrone dans un thread séparé
    logger.debug(f"Génération d'embedding pour texte: '{text[:30]}...' ({len(text)} caractères)")
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await asyncio.get_event_loop().run_in_executor(
                executor, _get_embedding_sync, text
            )
        logger.debug(f"Embedding généré avec succès (dimension: {len(result)})")
        return result
    except Exception as e:
        logger.error(f"Erreur lors de la génération d'embedding: {str(e)}")
        raise


async def check_embedding_service() -> dict:
    """
    Vérifie que le service d'embedding fonctionne correctement.
    Tente de générer un embedding pour un texte simple.
    
    Returns:
        Dictionnaire indiquant le statut du service
    """
    try:
        # Essayer de générer un embedding pour un texte simple
        test_text = "Test du service d'embedding"
        vector = await get_embedding(test_text)
        
        if vector and len(vector) > 0:
            return {
                "status": "ok",
                "model": settings.EMBEDDING_MODEL,
                "dimensions": len(vector)
            }
        else:
            return {
                "status": "error",
                "message": "L'embedding généré est vide"
            }
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du service d'embedding: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }