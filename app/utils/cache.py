# app/utils/cache.py - Version avec exceptions centralisées
import json
import logging
import hashlib
from typing import Any, Optional, Dict, Tuple, Union
import redis.asyncio as redis
import time
import os
from functools import wraps
from app.config import get_settings
from app.core.exceptions import CacheError  # NOUVELLE IMPORT

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
    Récupère un client Redis de manière paresseuse avec gestion d'erreurs améliorée.
    
    Returns:
        Client Redis ou None si la connexion échoue
        
    Raises:
        CacheError: Si erreur critique Redis en production
    """
    global _redis_client
    if _redis_client is None:
        try:
            if not REDIS_URL:
                raise CacheError("REDIS_URL non configurée", "connection")
            
            logger.info(f"Initialisation du client Redis: {REDIS_URL}")
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            
            # Vérifier la connexion avec timeout court
            await asyncio.wait_for(_redis_client.ping(), timeout=5.0)
            logger.info("Connexion Redis établie avec succès")
        
        except asyncio.TimeoutError:
            error_msg = "Timeout lors de la connexion Redis"
            logger.error(error_msg)
            _redis_client = None
            
            # En mode développement, on continue sans Redis
            if os.getenv("ENVIRONMENT") != "production":
                logger.warning("Redis non disponible, le cache sera désactivé")
                return None
            else:
                raise CacheError(error_msg, "connection")
        
        except redis.ConnectionError as e:
            error_msg = f"Erreur de connexion Redis: {str(e)}"
            logger.error(error_msg)
            _redis_client = None
            
            # En mode développement, on continue sans Redis
            if os.getenv("ENVIRONMENT") != "production":
                logger.warning("Redis non disponible, le cache sera désactivé")
                return None
            else:
                raise CacheError(error_msg, "connection")
        
        except Exception as e:
            error_msg = f"Erreur lors de l'initialisation de Redis: {str(e)}"
            logger.error(error_msg)
            _redis_client = None
            
            # En mode développement, on continue sans Redis
            if os.getenv("ENVIRONMENT") != "production":
                logger.warning("Redis non disponible, le cache sera désactivé")
                return None
            else:
                raise CacheError(error_msg, "initialization")
    
    return _redis_client


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Génère une clé de cache cohérente à partir des arguments avec validation.
    
    Args:
        prefix: Préfixe pour la clé (ex: 'translate')
        *args, **kwargs: Arguments à inclure dans la clé
        
    Returns:
        Clé de cache unique
        
    Raises:
        CacheError: Si les paramètres sont invalides
    """
    try:
        if not prefix or not isinstance(prefix, str):
            raise CacheError("Le préfixe de clé cache doit être une chaîne non vide", "key_generation")
        
        # Filtrer les arguments qui ne doivent pas être dans la clé de cache
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ['store_result', 'provider']}
        
        # Convertir les arguments en chaîne JSON
        key_data = {
            "args": args,
            "kwargs": filtered_kwargs
        }
        
        # Générer un hash pour les données
        key_string = json.dumps(key_data, sort_keys=True, ensure_ascii=True)
        key_hash = hashlib.md5(key_string.encode('utf-8')).hexdigest()
        
        # Construire la clé finale avec limitations de longueur
        cache_key = f"nl2sql:{prefix}:{key_hash}"
        
        # Redis a une limite de 512MB par clé, mais on limite à 250 caractères pour être sûr
        if len(cache_key) > 250:
            logger.warning(f"Clé cache très longue ({len(cache_key)} chars), hachage supplémentaire")
            cache_key = f"nl2sql:{prefix}:{hashlib.sha256(cache_key.encode()).hexdigest()}"
        
        return cache_key
    
    except json.JSONEncodeError as e:
        raise CacheError(f"Erreur lors de la sérialisation des arguments de clé: {e}", "key_generation")
    except Exception as e:
        raise CacheError(f"Erreur lors de la génération de clé cache: {e}", "key_generation")


async def cache_get(key: str) -> Optional[Dict[str, Any]]:
    """
    Récupère une valeur du cache avec gestion d'erreurs robuste.
    
    Args:
        key: Clé de cache
        
    Returns:
        Valeur du cache ou None si non trouvée
        
    Raises:
        CacheError: Si erreur critique Redis (uniquement en production)
    """
    if not CACHE_ENABLED:
        return None
    
    if not key or not isinstance(key, str):
        logger.warning("Clé de cache invalide")
        return None
    
    client = await get_redis_client()
    if client is None:
        return None
    
    try:
        # Récupérer avec timeout
        cached_value = await asyncio.wait_for(client.get(key), timeout=2.0)
        
        if cached_value:
            logger.debug(f"Cache hit pour la clé: {key[:50]}...")
            
            try:
                return json.loads(cached_value)
            except json.JSONDecodeError as e:
                logger.error(f"Données cache corrompues pour la clé {key}: {e}")
                # Supprimer la clé corrompue
                try:
                    await client.delete(key)
                except Exception:
                    pass  # Ignorer les erreurs de suppression
                return None
        else:
            logger.debug(f"Cache miss pour la clé: {key[:50]}...")
            return None
    
    except asyncio.TimeoutError:
        logger.warning(f"Timeout lors de la récupération cache pour {key}")
        return None
    
    except redis.ConnectionError as e:
        logger.warning(f"Erreur de connexion Redis lors de la récupération: {e}")
        # Réinitialiser le client pour la prochaine tentative
        global _redis_client
        _redis_client = None
        return None
    
    except Exception as e:
        error_msg = f"Erreur lors de la récupération du cache: {str(e)}"
        logger.error(error_msg)
        
        # En production, lever une exception pour les erreurs critiques
        if os.getenv("ENVIRONMENT") == "production":
            raise CacheError(error_msg, "get")
        else:
            return None


async def cache_set(key: str, value: Dict[str, Any], ttl: int = REDIS_TTL) -> bool:
    """
    Stocke une valeur dans le cache avec validation et gestion d'erreurs.
    
    Args:
        key: Clé de cache
        value: Valeur à stocker
        ttl: Durée de vie en secondes (par défaut 1 heure)
        
    Returns:
        True si l'opération a réussi, False sinon
        
    Raises:
        CacheError: Si erreur critique Redis (uniquement en production)
    """
    if not CACHE_ENABLED:
        return False
    
    # Validation des paramètres
    if not key or not isinstance(key, str):
        logger.warning("Clé de cache invalide pour le stockage")
        return False
    
    if not isinstance(value, dict):
        logger.warning("La valeur à mettre en cache doit être un dictionnaire")
        return False
    
    if not isinstance(ttl, int) or ttl <= 0:
        logger.warning(f"TTL invalide ({ttl}), utilisation de la valeur par défaut")
        ttl = REDIS_TTL
    
    # Limiter le TTL maximum à 7 jours
    if ttl > 604800:
        logger.warning(f"TTL très élevé ({ttl}s), limitation à 7 jours")
        ttl = 604800
    
    client = await get_redis_client()
    if client is None:
        return False
    
    try:
        # Sérialiser la valeur
        try:
            value_json = json.dumps(value, ensure_ascii=True, separators=(',', ':'))
        except (TypeError, ValueError) as e:
            logger.error(f"Erreur de sérialisation JSON: {e}")
            return False
        
        # Vérifier la taille (Redis limite à 512MB, on limite à 10MB pour être sûr)
        if len(value_json) > 10 * 1024 * 1024:  # 10MB
            logger.warning(f"Valeur cache très grande ({len(value_json)} bytes), stockage ignoré")
            return False
        
        # Stocker avec un TTL et timeout
        await asyncio.wait_for(
            client.setex(key, ttl, value_json),
            timeout=5.0
        )
        
        logger.debug(f"Valeur mise en cache avec la clé: {key[:50]}... (TTL: {ttl}s, taille: {len(value_json)} bytes)")
        return True
    
    except asyncio.TimeoutError:
        logger.warning(f"Timeout lors du stockage cache pour {key}")
        return False
    
    except redis.ConnectionError as e:
        logger.warning(f"Erreur de connexion Redis lors du stockage: {e}")
        # Réinitialiser le client pour la prochaine tentative
        global _redis_client
        _redis_client = None
        return False
    
    except Exception as e:
        error_msg = f"Erreur lors du stockage dans le cache: {str(e)}"
        logger.error(error_msg)
        
        # En production, lever une exception pour les erreurs critiques
        if os.getenv("ENVIRONMENT") == "production":
            raise CacheError(error_msg, "set")
        else:
            return False


async def cache_invalidate(key: str) -> bool:
    """
    Invalide une clé de cache avec gestion d'erreurs.
    
    Args:
        key: Clé de cache
        
    Returns:
        True si l'opération a réussi, False sinon
    """
    if not CACHE_ENABLED:
        return False
    
    if not key or not isinstance(key, str):
        logger.warning("Clé de cache invalide pour l'invalidation")
        return False
    
    client = await get_redis_client()
    if client is None:
        return False
    
    try:
        result = await asyncio.wait_for(client.delete(key), timeout=2.0)
        logger.debug(f"Clé de cache invalidée: {key[:50]}... (résultat: {result})")
        return True
    
    except asyncio.TimeoutError:
        logger.warning(f"Timeout lors de l'invalidation cache pour {key}")
        return False
    
    except Exception as e:
        logger.error(f"Erreur lors de l'invalidation du cache: {str(e)}")
        return False


async def cache_pattern_invalidate(pattern: str) -> int:
    """
    Invalide toutes les clés correspondant à un motif avec gestion d'erreurs.
    
    Args:
        pattern: Motif de clé (ex: 'nl2sql:translate:*')
        
    Returns:
        Nombre de clés invalidées
    """
    if not CACHE_ENABLED:
        return 0
    
    if not pattern or not isinstance(pattern, str):
        logger.warning("Motif de cache invalide")
        return 0
    
    client = await get_redis_client()
    if client is None:
        return 0
    
    try:
        # Récupérer toutes les clés correspondant au motif avec timeout
        keys = []
        async for key in client.scan_iter(match=pattern, count=100):
            keys.append(key)
            # Limitation pour éviter de surcharger Redis
            if len(keys) >= 1000:
                logger.warning(f"Trop de clés à invalider ({len(keys)}), arrêt à 1000")
                break
        
        # Supprimer les clés par batches
        if keys:
            batch_size = 100
            total_deleted = 0
            
            for i in range(0, len(keys), batch_size):
                batch_keys = keys[i:i + batch_size]
                try:
                    count = await asyncio.wait_for(
                        client.delete(*batch_keys),
                        timeout=5.0
                    )
                    total_deleted += count
                except Exception as e:
                    logger.warning(f"Erreur lors de la suppression du batch {i}: {e}")
            
            logger.debug(f"{total_deleted} clés de cache invalidées avec le motif: {pattern}")
            return total_deleted
        
        return 0
    
    except Exception as e:
        logger.error(f"Erreur lors de l'invalidation du cache par motif: {str(e)}")
        return 0


# DÉCORATEUR @cached DÉPLACÉ VERS app/utils/cache_decorator.py
# pour éviter les dépendances circulaires avec les services


async def get_cache_stats() -> Dict[str, Any]:
    """
    Récupère les statistiques du cache Redis.
    
    Returns:
        Dictionnaire avec les statistiques
    """
    if not CACHE_ENABLED:
        return {"status": "disabled"}
    
    client = await get_redis_client()
    if client is None:
        return {"status": "unavailable"}
    
    try:
        info = await client.info()
        
        return {
            "status": "ok",
            "memory_used": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "total_commands_processed": info.get("total_commands_processed", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "hit_rate": round(
                info.get("keyspace_hits", 0) / max(
                    info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1
                ) * 100, 2
            ) if info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0) > 0 else 0
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats Redis: {e}")
        return {"status": "error", "message": str(e)}


async def cleanup_cache_service():
    """
    Nettoie les ressources du service de cache.
    Utile lors de l'arrêt de l'application.
    """
    global _redis_client
    try:
        if _redis_client and not _redis_client.closed:
            await _redis_client.close()
            _redis_client = None
            logger.info("Service de cache nettoyé")
    
    except Exception as e:
        logger.warning(f"Erreur lors du nettoyage du cache: {e}")


# Import nécessaire pour asyncio
import asyncio