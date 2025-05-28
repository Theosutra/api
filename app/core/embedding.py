"""
Service d'embedding utilisant Gemini text-embedding-004.

Ce module utilise uniquement l'API Google Gemini pour l'embedding,
sans dépendance à SentenceTransformers.

Author: Datasulting
Version: 2.0.0 - Gemini uniquement
"""

import asyncio
from typing import List, Optional
import logging
import aiohttp
import json

from app.config import get_settings
from app.core.exceptions import EmbeddingError

# Configuration du logger
logger = logging.getLogger(__name__)

# Récupérer les paramètres de configuration
settings = get_settings()


async def get_embedding(text: str) -> List[float]:
    """
    Obtient un embedding vectoriel pour un texte donné en utilisant Gemini text-embedding-004.
    
    Args:
        text: Texte à convertir en vecteur
        
    Returns:
        Vecteur d'embedding sous forme de liste de flottants
        
    Raises:
        EmbeddingError: Si une erreur se produit lors de la vectorisation
    """
    # Validation des paramètres d'entrée
    if not text or not isinstance(text, str):
        raise EmbeddingError("Le texte à vectoriser doit être une chaîne non vide", "text-embedding-004")
    
    if len(text.strip()) == 0:
        raise EmbeddingError("Le texte à vectoriser ne peut pas être vide", "text-embedding-004")
    
    if len(text) > 8192:  # Limite Gemini
        logger.warning(f"Texte très long ({len(text)} caractères), troncature à 8192 caractères")
        text = text[:8192]
    
    # Vérifier que la clé API Google est disponible
    if not settings.GOOGLE_API_KEY:
        raise EmbeddingError("GOOGLE_API_KEY manquante pour utiliser text-embedding-004", "text-embedding-004")
    
    logger.debug(f"Génération d'embedding Gemini pour texte: '{text[:30]}...' ({len(text)} caractères)")
    
    try:
        # URL de l'API Gemini Embedding
        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={settings.GOOGLE_API_KEY}"
        
        # Payload pour l'API Gemini
        payload = {
            "model": "models/text-embedding-004",
            "content": {
                "parts": [{"text": text}]
            }
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Faire la requête
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=30) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Erreur API Gemini {response.status}: {error_text}")
                    raise EmbeddingError(f"Erreur API Gemini: {response.status} - {error_text}", "text-embedding-004")
                
                response_data = await response.json()
        
        # Extraire l'embedding de la réponse
        if 'embedding' not in response_data or 'values' not in response_data['embedding']:
            logger.error(f"Format de réponse Gemini invalide: {response_data}")
            raise EmbeddingError("Format de réponse Gemini invalide", "text-embedding-004")
        
        embedding = response_data['embedding']['values']
        
        # Vérifier que l'embedding est valide
        if not embedding or len(embedding) == 0:
            raise EmbeddingError("L'embedding généré est vide", "text-embedding-004")
        
        # Vérifier que toutes les valeurs sont des nombres valides
        if not all(isinstance(x, (int, float)) and not (isinstance(x, float) and (x != x or x == float('inf') or x == float('-inf'))) for x in embedding):
            raise EmbeddingError("L'embedding contient des valeurs invalides (NaN ou infini)", "text-embedding-004")
        
        logger.debug(f"Embedding Gemini généré avec succès (dimension: {len(embedding)})")
        return embedding
    
    except EmbeddingError:
        # Re-propager les erreurs EmbeddingError
        raise
    except asyncio.CancelledError:
        logger.warning("Génération d'embedding Gemini annulée")
        raise EmbeddingError("Génération d'embedding annulée", "text-embedding-004")
    except Exception as e:
        logger.error(f"Erreur lors de la génération d'embedding Gemini: {str(e)}")
        raise EmbeddingError(f"Erreur lors de la génération d'embedding Gemini: {str(e)}", "text-embedding-004")


async def check_embedding_service() -> dict:
    """
    Vérifie que le service d'embedding Gemini fonctionne correctement.
    
    Returns:
        Dictionnaire indiquant le statut du service
    """
    try:
        # Essayer de générer un embedding pour un texte simple
        test_text = "Test du service d'embedding Gemini"
        vector = await get_embedding(test_text)
        
        if vector and len(vector) > 0:
            return {
                "status": "ok",
                "model": "text-embedding-004",
                "provider": "google",
                "dimensions": len(vector),
                "test_successful": True
            }
        else:
            return {
                "status": "error",
                "model": "text-embedding-004",
                "provider": "google",
                "message": "L'embedding généré est vide",
                "test_successful": False
            }
    
    except EmbeddingError as e:
        logger.error(f"Erreur lors de la vérification du service d'embedding Gemini: {e}")
        return {
            "status": "error",
            "model": "text-embedding-004",
            "provider": "google",
            "message": str(e),
            "test_successful": False
        }
    
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la vérification du service d'embedding: {str(e)}")
        return {
            "status": "error",
            "model": "text-embedding-004",
            "provider": "google",
            "message": f"Erreur inattendue: {str(e)}",
            "test_successful": False
        }


async def get_model_info() -> dict:
    """
    Récupère les informations du modèle d'embedding Gemini.
    
    Returns:
        Dictionnaire avec les informations du modèle
    """
    try:
        # Tester la dimension avec un exemple
        test_embedding = await get_embedding("test")
        
        model_info = {
            "model_name": "text-embedding-004",
            "provider": "google",
            "embedding_dimension": len(test_embedding),
            "max_input_length": 8192,
            "api_endpoint": "generativelanguage.googleapis.com"
        }
        
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
    Pour Gemini API, pas de nettoyage spécial nécessaire.
    """
    logger.info("Service d'embedding Gemini nettoyé")


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
        actual_dim = len(test_embedding)
        
        if actual_dim == expected_dim:
            logger.info(f"✅ Dimension d'embedding validée: {actual_dim}")
            return True
        else:
            logger.warning(f"❌ Dimension d'embedding incorrecte: {actual_dim} (attendu: {expected_dim})")
            return False
    except Exception as e:
        logger.error(f"Erreur lors de la validation de dimension: {e}")
        return False