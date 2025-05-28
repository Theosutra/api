"""
Décorateur de cache pour l'architecture Service Layer.

Ce module fournit un décorateur de cache spécialisé pour les services,
remplaçant le décorateur @cached qui était dans cache.py et utilisé par translator.py.

Author: Datasulting
Version: 2.0.0
"""

import logging
import hashlib
import json
import time
from functools import wraps
from typing import Any, Dict, Optional

from app.utils.cache import get_redis_client, CACHE_ENABLED, REDIS_TTL
from app.core.exceptions import CacheError

logger = logging.getLogger(__name__)


def cache_service_method(ttl: int = REDIS_TTL, key_prefix: str = "service"):
    """
    Décorateur de cache spécialisé pour les méthodes de services.
    
    Args:
        ttl: Durée de vie en secondes (par défaut 1 heure)
        key_prefix: Préfixe pour les clés de cache
        
    Returns:
        Décorateur pour méthodes de service
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Vérifier si le cache est activé globalement ET pour cette requête
            use_cache_for_request = kwargs.get('use_cache', True)
            
            if not CACHE_ENABLED or not use_cache_for_request:
                # Cache désactivé globalement ou pour cette requête spécifique
                result = await func(*args, **kwargs)
                if isinstance(result, dict):
                    result["from_cache"] = False
                return result
            
            try:
                # Générer la clé de cache
                cache_key = _generate_service_cache_key(func, key_prefix, *args, **kwargs)
                
                # Essayer de récupérer du cache
                cached_result = await _get_from_cache(cache_key)
                if cached_result is not None:
                    cached_result["from_cache"] = True
                    logger.debug(f"Cache hit pour service {func.__name__}")
                    return cached_result
            
            except CacheError as e:
                logger.warning(f"Erreur cache lors de la récupération pour {func.__name__}: {e}")
                # Continuer sans cache en cas d'erreur
            except Exception as e:
                logger.warning(f"Erreur inattendue cache pour {func.__name__}: {e}")
                # Continuer sans cache en cas d'erreur
            
            # Exécuter la fonction
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Stocker dans le cache seulement si le résultat est valide
            if (isinstance(result, dict) and 
                result.get("status") == "success" and 
                kwargs.get("store_result", True)):
                
                try:
                    # Ajouter le temps d'exécution dans les métadonnées
                    if "processing_time" in result:
                        result["execution_time"] = execution_time
                    
                    # Indiquer que le résultat ne vient pas du cache
                    result["from_cache"] = False
                    
                    # Mettre en cache
                    await _store_in_cache(cache_key, result, ttl)
                    logger.debug(f"Résultat mis en cache pour service {func.__name__}")
                
                except CacheError as e:
                    logger.warning(f"Erreur cache lors du stockage pour {func.__name__}: {e}")
                    # Continuer même si la mise en cache échoue
                except Exception as e:
                    logger.warning(f"Erreur inattendue cache lors du stockage pour {func.__name__}: {e}")
                    # Continuer même si la mise en cache échoue
            else:
                # Pas de mise en cache, mais indiquer que ce n'est pas du cache
                if isinstance(result, dict):
                    result["from_cache"] = False
            
            return result
        
        return wrapper
    
    return decorator


def _generate_service_cache_key(func, key_prefix: str, *args, **kwargs) -> str:
    """
    Génère une clé de cache pour une méthode de service.
    
    Args:
        func: Fonction à mettre en cache
        key_prefix: Préfixe pour la clé
        *args, **kwargs: Arguments de la fonction
        
    Returns:
        Clé de cache unique
    """
    try:
        # Ignorer 'self' (premier argument des méthodes de classe)
        cache_args = args[1:] if args else args
        
        # Filtrer les arguments qui ne doivent pas être dans la clé de cache
        filtered_kwargs = {
            k: v for k, v in kwargs.items() 
            if k not in ['store_result', 'use_cache']
        }
        
        # Construire les données pour la clé
        key_data = {
            "class": func.__qualname__.split('.')[0] if '.' in func.__qualname__ else 'function',
            "method": func.__name__,
            "args": cache_args,
            "kwargs": filtered_kwargs
        }
        
        # Générer un hash pour les données
        key_string = json.dumps(key_data, sort_keys=True, ensure_ascii=True, default=str)
        key_hash = hashlib.md5(key_string.encode('utf-8')).hexdigest()
        
        # Construire la clé finale
        cache_key = f"nl2sql:{key_prefix}:{func.__name__}:{key_hash}"
        
        # Limiter la longueur de la clé
        if len(cache_key) > 250:
            cache_key = f"nl2sql:{key_prefix}:{hashlib.sha256(cache_key.encode()).hexdigest()}"
        
        return cache_key
    
    except Exception as e:
        logger.error(f"Erreur lors de la génération de clé cache: {e}")
        # Fallback: clé simple basée sur le nom de la fonction
        return f"nl2sql:{key_prefix}:{func.__name__}:{int(time.time())}"


async def _get_from_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    Récupère une valeur du cache.
    
    Args:
        cache_key: Clé de cache
        
    Returns:
        Valeur du cache ou None
    """
    if not CACHE_ENABLED:
        return None
    
    client = await get_redis_client()
    if client is None:
        return None
    
    try:
        cached_value = await client.get(cache_key)
        if cached_value:
            return json.loads(cached_value)
        return None
    
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération cache: {e}")
        return None


async def _store_in_cache(cache_key: str, value: Dict[str, Any], ttl: int) -> bool:
    """
    Stocke une valeur dans le cache.
    
    Args:
        cache_key: Clé de cache
        value: Valeur à stocker
        ttl: Durée de vie en secondes
        
    Returns:
        True si stocké avec succès
    """
    if not CACHE_ENABLED:
        return False
    
    client = await get_redis_client()
    if client is None:
        return False
    
    try:
        # Sérialiser la valeur
        value_json = json.dumps(value, ensure_ascii=True, separators=(',', ':'), default=str)
        
        # Vérifier la taille (limiter à 10MB)
        if len(value_json) > 10 * 1024 * 1024:
            logger.warning(f"Valeur cache trop grande ({len(value_json)} bytes), stockage ignoré")
            return False
        
        # Stocker avec TTL
        await client.setex(cache_key, ttl, value_json)
        return True
    
    except Exception as e:
        logger.warning(f"Erreur lors du stockage cache: {e}")
        return False


async def invalidate_service_cache(service_name: str, method_name: str = "*") -> int:
    """
    Invalide le cache pour un service spécifique.
    
    Args:
        service_name: Nom du service
        method_name: Nom de la méthode (ou * pour toutes)
        
    Returns:
        Nombre de clés invalidées
    """
    try:
        from app.utils.cache import cache_pattern_invalidate
        
        if method_name == "*":
            pattern = f"nl2sql:service:*"
        else:
            pattern = f"nl2sql:service:{method_name}:*"
        
        count = await cache_pattern_invalidate(pattern)
        logger.info(f"Cache invalidé pour {service_name}.{method_name}: {count} clés")
        return count
    
    except Exception as e:
        logger.error(f"Erreur lors de l'invalidation cache service: {e}")
        return 0