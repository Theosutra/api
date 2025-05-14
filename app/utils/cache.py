# app/utils/cache.py
import json
import logging
import hashlib
from typing import Any, Optional, Dict, Tuple, Union
import redis.asyncio as redis
import time
import os
from functools import wraps
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Configuration Redis (avec valeurs par défaut)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_TTL = int(os.getenv("REDIS_TTL", "3600"))  # 1 heure par défaut
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"

# Client Redis (initialisé de manière paresseuse)
_redis_client = None

async def get_redis_client() -> Optional[redis.Redis]:
    """
    Récupère un client Redis de manière paresseuse.
    
    Returns:
        Client Redis ou None si la connexion échoue
    """
    global _redis_client
    if _redis_client is None:
        try:
            logger.info(f"Initialisation du client Redis: {REDIS_URL}")
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            # Vérifier la connexion
            await _redis_client.ping()
            logger.info("Connexion Redis établie avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de Redis: {str(e)}")
            # En mode développement, on continue même sans Redis
            if os.getenv("ENVIRONMENT") != "production":
                logger.warning("Redis non disponible, le cache sera désactivé")
                return None
            else:
                # En production, on réessaie pour être sûr
                raise RuntimeError(f"Impossible de se connecter à Redis: {str(e)}")
    
    return _redis_client

def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Génère une clé de cache cohérente à partir des arguments.
    
    Args:
        prefix: Préfixe pour la clé (ex: 'translate')
        *args, **kwargs: Arguments à inclure dans la clé
        
    Returns:
        Clé de cache unique
    """
    # Convertir les arguments en chaîne JSON
    key_data = {
        "args": args,
        "kwargs": {k: v for k, v in kwargs.items() if k != "store_result"}
    }
    
    # Générer un hash pour les données
    key_hash = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    return f"nl2sql:{prefix}:{key_hash}"

async def cache_get(key: str) -> Optional[Dict[str, Any]]:
    """
    Récupère une valeur du cache.
    
    Args:
        key: Clé de cache
        
    Returns:
        Valeur du cache ou None si non trouvée
    """
    if not CACHE_ENABLED:
        return None
        
    client = await get_redis_client()
    if client is None:
        return None
    
    try:
        cached_value = await client.get(key)
        if cached_value:
            logger.debug(f"Cache hit pour la clé: {key}")
            return json.loads(cached_value)
        else:
            logger.debug(f"Cache miss pour la clé: {key}")
            return None
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du cache: {str(e)}")
        return None

async def cache_set(key: str, value: Dict[str, Any], ttl: int = REDIS_TTL) -> bool:
    """
    Stocke une valeur dans le cache.
    
    Args:
        key: Clé de cache
        value: Valeur à stocker
        ttl: Durée de vie en secondes (par défaut 1 heure)
        
    Returns:
        True si l'opération a réussi, False sinon
    """
    if not CACHE_ENABLED:
        return False
        
    client = await get_redis_client()
    if client is None:
        return False
    
    try:
        # Sérialiser la valeur
        value_json = json.dumps(value)
        
        # Stocker avec un TTL
        await client.setex(key, ttl, value_json)
        logger.debug(f"Valeur mise en cache avec la clé: {key} (TTL: {ttl}s)")
        return True
    except Exception as e:
        logger.error(f"Erreur lors du stockage dans le cache: {str(e)}")
        return False

async def cache_invalidate(key: str) -> bool:
    """
    Invalide une clé de cache.
    
    Args:
        key: Clé de cache
        
    Returns:
        True si l'opération a réussi, False sinon
    """
    if not CACHE_ENABLED:
        return False
        
    client = await get_redis_client()
    if client is None:
        return False
    
    try:
        await client.delete(key)
        logger.debug(f"Clé de cache invalidée: {key}")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'invalidation du cache: {str(e)}")
        return False

async def cache_pattern_invalidate(pattern: str) -> int:
    """
    Invalide toutes les clés correspondant à un motif.
    
    Args:
        pattern: Motif de clé (ex: 'nl2sql:translate:*')
        
    Returns:
        Nombre de clés invalidées
    """
    if not CACHE_ENABLED:
        return 0
        
    client = await get_redis_client()
    if client is None:
        return 0
    
    try:
        # Récupérer toutes les clés correspondant au motif
        keys = []
        async for key in client.scan_iter(match=pattern):
            keys.append(key)
        
        # Supprimer les clés
        if keys:
            count = await client.delete(*keys)
            logger.debug(f"{count} clés de cache invalidées avec le motif: {pattern}")
            return count
        return 0
    except Exception as e:
        logger.error(f"Erreur lors de l'invalidation du cache par motif: {str(e)}")
        return 0

def cached(ttl: int = REDIS_TTL):
    """
    Décorateur pour mettre en cache les résultats d'une fonction asynchrone.
    
    Args:
        ttl: Durée de vie en secondes (par défaut 1 heure)
        
    Returns:
        Décorateur
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not CACHE_ENABLED:
                return await func(*args, **kwargs)
            
            # Générer la clé de cache
            prefix = f"{func.__module__}:{func.__name__}"
            cache_key = generate_cache_key(prefix, *args, **kwargs)
            
            # Essayer de récupérer du cache
            cached_result = await cache_get(cache_key)
            if cached_result is not None:
                # Ajouter une indication que le résultat vient du cache
                cached_result["from_cache"] = True
                return cached_result
            
            # Exécuter la fonction
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Stocker dans le cache seulement si store_result n'est pas False
            if result.get("status") == "success" and kwargs.get("store_result", True):
                # Ajouter le temps d'exécution dans les métadonnées
                if "processing_time" in result:
                    result["execution_time"] = execution_time
                
                # Indiquer que le résultat ne vient pas du cache
                result["from_cache"] = False
                
                # Mettre en cache
                await cache_set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    
    return decorator