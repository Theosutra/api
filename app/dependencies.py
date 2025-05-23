# app/dependencies.py
from fastapi import Depends, HTTPException, Request, status
from fastapi.security.api_key import APIKeyHeader
from typing import Optional, Dict, Any
import time
import logging
import os
from app.config import get_settings
from app.utils.cache import get_redis_client

# Configuration du logger
logger = logging.getLogger(__name__)
settings = get_settings()

# En-tête pour l'authentification par clé API
api_key_header = APIKeyHeader(name=settings.API_KEY_NAME, auto_error=False)


async def get_api_key(api_key: Optional[str] = Depends(api_key_header)) -> bool:
    """
    Vérifie la validité de la clé API fournie dans l'en-tête de la requête.
    
    Args:
        api_key: La clé API extraite de l'en-tête de la requête
        
    Returns:
        True si la clé API est valide ou si aucune clé n'est configurée
        
    Raises:
        HTTPException: Si la clé API est invalide
    """
    # Si aucune clé API n'est configurée, on n'effectue pas de vérification
    if not settings.API_KEY:
        return True
    
    # Vérifier si la clé API correspond à celle configurée
    if not api_key or api_key != settings.API_KEY:
        logger.warning(f"Tentative d'accès avec une clé API invalide")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide ou manquante",
            headers={"WWW-Authenticate": settings.API_KEY_NAME},
        )
    
    return True


async def rate_limit(request: Request, limit: int = 60, window: int = 60) -> None:
    """
    Limite le nombre de requêtes par IP pour éviter les abus.
    Utilise Redis comme backend si disponible, sinon utilise un dictionnaire en mémoire.
    
    Args:
        request: L'objet Request contenant les informations de la requête
        limit: Nombre maximum de requêtes autorisées dans la fenêtre de temps
        window: Durée de la fenêtre de temps en secondes
        
    Raises:
        HTTPException: Si le taux de requêtes est dépassé
    """
    # Obtenir l'adresse IP du client
    client_ip = request.client.host if request.client else "unknown"
    redis_key = f"rate_limit:{client_ip}"
    
    # Obtenir le client Redis
    redis = await get_redis_client()
    
    # Si Redis est disponible, utiliser Redis pour le rate limiting
    if redis is not None:
        try:
            # Récupérer le compteur actuel
            count = await redis.get(redis_key)
            ttl = await redis.ttl(redis_key)
            
            # Si la clé n'existe pas, l'initialiser
            if count is None:
                await redis.setex(redis_key, window, 1)
                return
            
            # Incrémenter le compteur
            count = int(count) + 1
            await redis.setex(redis_key, ttl if ttl > 0 else window, count)
            
            # Vérifier si le taux de requêtes est dépassé
            if count > limit:
                logger.warning(f"Limite de débit dépassée pour l'IP {client_ip}: {count}/{limit}")
                
                retry_after = int(ttl if ttl > 0 else window)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Trop de requêtes. Veuillez réessayer plus tard.",
                    headers={"Retry-After": str(retry_after)}
                )
        
        except Exception as e:
            logger.error(f"Erreur Redis lors du rate limiting: {str(e)}")
            # En cas d'erreur Redis, on utilise le rate limiting en mémoire comme fallback
            await in_memory_rate_limit(request, limit, window)
    
    # Si Redis n'est pas disponible, utiliser le rate limiting en mémoire
    else:
        await in_memory_rate_limit(request, limit, window)


# Dictionnaire pour la limitation de débit en mémoire (fallback)
rate_limit_store: Dict[str, Dict[str, Any]] = {}

async def in_memory_rate_limit(request: Request, limit: int = 60, window: int = 60) -> None:
    """
    Implémentation de rate limiting en mémoire (fallback si Redis n'est pas disponible).
    
    Args:
        request: L'objet Request contenant les informations de la requête
        limit: Nombre maximum de requêtes autorisées dans la fenêtre de temps
        window: Durée de la fenêtre de temps en secondes
        
    Raises:
        HTTPException: Si le taux de requêtes est dépassé
    """
    # Obtenir l'adresse IP du client
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    # Initialiser l'entrée du client si elle n'existe pas
    if client_ip not in rate_limit_store:
        rate_limit_store[client_ip] = {
            "count": 0,
            "reset_at": current_time + window
        }
    
    # Réinitialiser le compteur si la fenêtre de temps est écoulée
    if current_time > rate_limit_store[client_ip]["reset_at"]:
        rate_limit_store[client_ip] = {
            "count": 0,
            "reset_at": current_time + window
        }
    
    # Incrémenter le compteur de requêtes
    rate_limit_store[client_ip]["count"] += 1
    
    # Vérifier si le taux de requêtes est dépassé
    if rate_limit_store[client_ip]["count"] > limit:
        retry_after = int(rate_limit_store[client_ip]["reset_at"] - current_time)
        logger.warning(f"Limite de débit dépassée pour l'IP {client_ip}")
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de requêtes. Veuillez réessayer plus tard.",
            headers={"Retry-After": str(retry_after)}
        )