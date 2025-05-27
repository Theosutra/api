import asyncio
from typing import List, Optional
import concurrent.futures
import logging
from sentence_transformers import SentenceTransformer

from app.config import get_settings
from app.core.exceptions import EmbeddingError  # NOUVELLE IMPORT

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
        EmbeddingError: Si le modèle ne peut pas être chargé
    """
    global _model
    if _model is None:
        try:
            logger.info(f"Chargement du modèle d'embedding '{settings.EMBEDDING_MODEL}'")
            _model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info(f"Modèle d'embedding chargé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle d'embedding: {str(e)}")
            raise EmbeddingError(f"Erreur lors de l'initialisation du modèle d'embedding: {str(e)}", settings.EMBEDDING_MODEL)
    return _model


def _get_embedding_sync(text: str) -> List[float]:
    """
    Version synchrone de get_embedding.
    Convertit un texte en un vecteur d'embedding.
    
    Args:
        text: Texte à convertir en vecteur
        
    Returns:
        Vecteur d'embedding sous forme de liste de flottants
        
    Raises:
        EmbeddingError: Si erreur lors de la vectorisation
    """
    if not text or not isinstance(text, str):
        raise EmbeddingError("Le texte à vectoriser doit être une chaîne non vide", settings.EMBEDDING_MODEL)
    
    if len(text.strip()) == 0:
        raise EmbeddingError("Le texte à vectoriser ne peut pas être vide", settings.EMBEDDING_MODEL)
    
    model = _load_model()
    try:
        embedding = model.encode(text)
        result = embedding.tolist()
        
        # Vérifier que l'embedding est valide
        if not result or len(result) == 0:
            raise EmbeddingError("L'embedding généré est vide", settings.EMBEDDING_MODEL)
        
        # Vérifier que toutes les valeurs sont des nombres valides
        if not all(isinstance(x, (int, float)) and not (isinstance(x, float) and (x != x or x == float('inf') or x == float('-inf'))) for x in result):
            raise EmbeddingError("L'embedding contient des valeurs invalides (NaN ou infini)", settings.EMBEDDING_MODEL)
        
        return result
    except EmbeddingError:
        # Re-propager les erreurs EmbeddingError
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la vectorisation du texte: {str(e)}")
        raise EmbeddingError(f"Erreur lors de la vectorisation du texte: {str(e)}", settings.EMBEDDING_MODEL)


async def get_embedding(text: str) -> List[float]:
    """
    Obtient un embedding vectoriel pour un texte donné de manière asynchrone.
    Utilise un thread séparé pour ne pas bloquer la boucle asyncio.
    
    Args:
        text: Texte à convertir en vecteur
        
    Returns:
        Vecteur d'embedding sous forme de liste de flottants
        
    Raises:
        EmbeddingError: Si une erreur se produit lors de la vectorisation
    """
    # Validation des paramètres d'entrée
    if not text or not isinstance(text, str):
        raise EmbeddingError("Le texte à vectoriser doit être une chaîne non vide", settings.EMBEDDING_MODEL)
    
    if len(text.strip()) == 0:
        raise EmbeddingError("Le texte à vectoriser ne peut pas être vide", settings.EMBEDDING_MODEL)
    
    if len(text) > 8192:  # Limite raisonnable pour la plupart des modèles
        logger.warning(f"Texte très long ({len(text)} caractères), troncature à 8192 caractères")
        text = text[:8192]
    
    # Exécuter la fonction synchrone dans un thread séparé
    logger.debug(f"Génération d'embedding pour texte: '{text[:30]}...' ({len(text)} caractères)")
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            result = await asyncio.get_event_loop().run_in_executor(
                executor, _get_embedding_sync, text
            )
        
        logger.debug(f"Embedding généré avec succès (dimension: {len(result)})")
        return result
    
    except EmbeddingError:
        # Re-propager les erreurs EmbeddingError
        raise
    except asyncio.CancelledError:
        logger.warning("Génération d'embedding annulée")
        raise EmbeddingError("Génération d'embedding annulée", settings.EMBEDDING_MODEL)
    except Exception as e:
        logger.error(f"Erreur lors de la génération d'embedding: {str(e)}")
        raise EmbeddingError(f"Erreur lors de la génération d'embedding: {str(e)}", settings.EMBEDDING_MODEL)


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
                "dimensions": len(vector),
                "test_successful": True
            }
        else:
            return {
                "status": "error",
                "model": settings.EMBEDDING_MODEL,
                "message": "L'embedding généré est vide",
                "test_successful": False
            }
    
    except EmbeddingError as e:
        logger.error(f"Erreur lors de la vérification du service d'embedding: {e}")
        return {
            "status": "error",
            "model": settings.EMBEDDING_MODEL,
            "message": str(e),
            "test_successful": False
        }
    
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la vérification du service d'embedding: {str(e)}")
        return {
            "status": "error",
            "model": settings.EMBEDDING_MODEL,
            "message": f"Erreur inattendue: {str(e)}",
            "test_successful": False
        }


async def get_model_info() -> dict:
    """
    Récupère les informations du modèle d'embedding chargé.
    
    Returns:
        Dictionnaire avec les informations du modèle
    """
    try:
        model = _load_model()
        
        # Essayer de récupérer les informations du modèle
        model_info = {
            "model_name": settings.EMBEDDING_MODEL,
            "max_seq_length": getattr(model, 'max_seq_length', 'unknown'),
            "device": str(model.device) if hasattr(model, 'device') else 'unknown'
        }
        
        # Tester la dimension avec un exemple
        try:
            test_embedding = model.encode("test")
            model_info["embedding_dimension"] = len(test_embedding)
        except Exception as e:
            logger.warning(f"Impossible de déterminer la dimension d'embedding: {e}")
            model_info["embedding_dimension"] = 'unknown'
        
        return {
            "status": "ok",
            "info": model_info
        }
    
    except EmbeddingError as e:
        return {
            "status": "error",
            "message": str(e)
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des informations du modèle: {e}")
        return {
            "status": "error",
            "message": f"Erreur lors de la récupération des informations: {e}"
        }


async def cleanup_embedding_service():
    """
    Nettoie les ressources du service d'embedding.
    Utile lors de l'arrêt de l'application.
    """
    global _model
    try:
        if _model is not None:
            # Certains modèles peuvent avoir des ressources à libérer
            if hasattr(_model, 'cpu'):
                _model.cpu()  # Déplacer vers CPU pour libérer GPU
            
            _model = None
            logger.info("Service d'embedding nettoyé")
    
    except Exception as e:
        logger.warning(f"Erreur lors du nettoyage du service d'embedding: {e}")


# Fonction utilitaire pour les tests
async def validate_embedding_dimension(expected_dim: int) -> bool:
    """
    Valide que la dimension d'embedding correspond à celle attendue.
    
    Args:
        expected_dim: Dimension attendue
        
    Returns:
        True si la dimension correspond
    """
    try:
        test_embedding = await get_embedding("test de validation")
        return len(test_embedding) == expected_dim
    except Exception as e:
        logger.error(f"Erreur lors de la validation de dimension: {e}")
        return False