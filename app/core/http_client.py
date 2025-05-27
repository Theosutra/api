"""
Client HTTP centralisé pour les requêtes vers les API LLM.

Ce module fournit un client HTTP réutilisable avec gestion d'erreurs uniforme,
retry logic, et optimisations de performance pour les appels aux fournisseurs LLM.

Author: Datasulting
Version: 2.0.0
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Union
import aiohttp
import json

from .exceptions import (
    LLMError, LLMNetworkError, LLMAuthError, 
    LLMQuotaError, LLMConfigError
)

logger = logging.getLogger(__name__)


class HTTPClient:
    """
    Client HTTP centralisé avec gestion d'erreurs uniforme et optimisations.
    
    Fonctionnalités:
    - Pool de connexions réutilisables
    - Gestion d'erreurs spécialisée par code HTTP
    - Retry automatique avec backoff exponentiel
    - Logging détaillé des requêtes
    - Timeout configurables
    """
    
    def __init__(self, max_retries: int = 3, base_timeout: int = 30):
        """
        Initialise le client HTTP.
        
        Args:
            max_retries: Nombre maximum de tentatives en cas d'échec
            base_timeout: Timeout de base en secondes
        """
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self.max_retries = max_retries
        self.base_timeout = base_timeout
        
        # Statistiques de performance (optionnel pour monitoring)
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Récupère ou crée une session HTTP (thread-safe).
        
        La session est créée avec des optimisations de performance:
        - Pool de connexions avec limites appropriées
        - Cache DNS activé
        - Timeouts configurés
        
        Returns:
            Session aiohttp configurée
        """
        if self._session is None or self._session.closed:
            async with self._lock:
                if self._session is None or self._session.closed:
                    # Configuration optimisée du connecteur
                    connector = aiohttp.TCPConnector(
                        limit=100,              # Maximum 100 connexions totales
                        limit_per_host=30,      # Maximum 30 connexions par host
                        ttl_dns_cache=300,      # Cache DNS de 5 minutes
                        use_dns_cache=True,     # Activer le cache DNS
                        enable_cleanup_closed=True,  # Nettoyage automatique
                        keepalive_timeout=30    # Keep-alive de 30 secondes
                    )
                    
                    # Timeout global pour la session
                    timeout = aiohttp.ClientTimeout(total=60)
                    
                    self._session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=timeout,
                        headers={
                            "User-Agent": "NL2SQL-API/2.0.0",
                            "Accept": "application/json",
                            "Accept-Encoding": "gzip, deflate"
                        }
                    )
                    
                    logger.debug("Session HTTP créée avec optimisations")
        
        return self._session
    
    async def post_json(
        self,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        timeout: int = None,
        provider: str = "unknown",
        retry_on_failure: bool = True
    ) -> Dict[str, Any]:
        """
        Effectue une requête POST JSON avec gestion d'erreurs et retry.
        
        Args:
            url: URL de destination
            headers: En-têtes HTTP
            payload: Données JSON à envoyer
            timeout: Timeout spécifique (utilise base_timeout si None)
            provider: Nom du fournisseur pour les logs et erreurs
            retry_on_failure: Active/désactive le retry automatique
            
        Returns:
            Réponse JSON désérialisée
            
        Raises:
            LLMAuthError: Erreur d'authentification (401, 403)
            LLMQuotaError: Limite de débit dépassée (429)
            LLMNetworkError: Erreur réseau ou serveur (5xx, timeout)
            LLMError: Autres erreurs HTTP
        """
        timeout = timeout or self.base_timeout
        session = await self._get_session()
        
        # Logging de la requête (sans données sensibles)
        logger.debug(
            f"[{provider}] POST {url} - Headers: {len(headers)} - "
            f"Payload size: {len(str(payload))} chars - Timeout: {timeout}s"
        )
        
        start_time = time.time()
        last_exception = None
        
        # Retry loop avec backoff exponentiel
        for attempt in range(self.max_retries if retry_on_failure else 1):
            try:
                # Calculer le timeout pour cette tentative
                attempt_timeout = timeout + (attempt * 5)  # +5s par tentative
                
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=attempt_timeout)
                ) as response:
                    
                    response_time = time.time() - start_time
                    
                    # Lecture de la réponse
                    try:
                        response_text = await response.text()
                    except Exception as e:
                        logger.error(f"[{provider}] Impossible de lire la réponse: {e}")
                        raise LLMNetworkError(provider, "Réponse illisible", e)
                    
                    # Logging de la réponse
                    logger.debug(
                        f"[{provider}] Response {response.status} - "
                        f"Size: {len(response_text)} chars - Time: {response_time:.2f}s"
                    )
                    
                    # Gestion des codes d'erreur HTTP
                    if response.status == 401:
                        raise LLMAuthError(provider, "Clé API invalide ou expirée")
                    elif response.status == 403:
                        raise LLMAuthError(provider, "Accès non autorisé")
                    elif response.status == 429:
                        # Extraction du retry-after si présent
                        retry_after = response.headers.get("Retry-After", "60")
                        raise LLMQuotaError(
                            provider, 
                            f"Limite de débit dépassée. Réessayez dans {retry_after}s"
                        )
                    elif 500 <= response.status <= 599:
                        error_msg = f"Erreur serveur {response.status}"
                        try:
                            error_data = json.loads(response_text)
                            if "error" in error_data:
                                error_msg += f": {error_data['error']}"
                        except json.JSONDecodeError:
                            if response_text:
                                error_msg += f": {response_text[:200]}"
                        
                        # Retry automatique pour les erreurs serveur (sauf dernière tentative)
                        if attempt < self.max_retries - 1 and retry_on_failure:
                            wait_time = (2 ** attempt)  # Backoff exponentiel: 1s, 2s, 4s...
                            logger.warning(
                                f"[{provider}] {error_msg}. Tentative {attempt + 1}/{self.max_retries}. "
                                f"Nouvelle tentative dans {wait_time}s"
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        
                        raise LLMNetworkError(provider, error_msg)
                    elif response.status != 200:
                        # Autres codes d'erreur
                        error_msg = f"HTTP {response.status}"
                        try:
                            error_data = json.loads(response_text)
                            if "error" in error_data:
                                error_msg += f": {error_data['error']}"
                        except json.JSONDecodeError:
                            if response_text:
                                error_msg += f": {response_text[:200]}"
                        
                        raise LLMError(provider, error_msg, response.status)
                    
                    # Parsing de la réponse JSON
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError as e:
                        logger.error(f"[{provider}] Réponse JSON invalide: {e}")
                        raise LLMError(provider, f"Réponse JSON invalide: {e}", 502)
                    
                    # Mise à jour des statistiques
                    self._update_stats(True, response_time)
                    
                    logger.info(
                        f"[{provider}] Requête réussie en {response_time:.2f}s "
                        f"(tentative {attempt + 1})"
                    )
                    
                    return response_data
            
            except (asyncio.TimeoutError, aiohttp.ServerTimeoutError) as e:
                last_exception = e
                error_msg = f"Timeout après {attempt_timeout}s"
                
                if attempt < self.max_retries - 1 and retry_on_failure:
                    wait_time = (2 ** attempt)
                    logger.warning(
                        f"[{provider}] {error_msg}. Tentative {attempt + 1}/{self.max_retries}. "
                        f"Nouvelle tentative dans {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                
                self._update_stats(False, time.time() - start_time)
                raise LLMNetworkError(provider, error_msg, e)
            
            except (aiohttp.ClientError, aiohttp.ClientConnectionError) as e:
                last_exception = e
                error_msg = f"Erreur de connexion: {str(e)}"
                
                if attempt < self.max_retries - 1 and retry_on_failure:
                    wait_time = (2 ** attempt)
                    logger.warning(
                        f"[{provider}] {error_msg}. Tentative {attempt + 1}/{self.max_retries}. "
                        f"Nouvelle tentative dans {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                
                self._update_stats(False, time.time() - start_time)
                raise LLMNetworkError(provider, error_msg, e)
            
            except (LLMAuthError, LLMQuotaError, LLMError):
                # Ne pas retry pour les erreurs d'auth, quota, ou autres erreurs LLM
                self._update_stats(False, time.time() - start_time)
                raise
            
            except Exception as e:
                last_exception = e
                error_msg = f"Erreur inattendue: {str(e)}"
                logger.error(f"[{provider}] {error_msg}", exc_info=True)
                
                if attempt < self.max_retries - 1 and retry_on_failure:
                    wait_time = (2 ** attempt)
                    logger.warning(
                        f"[{provider}] Nouvelle tentative dans {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                
                self._update_stats(False, time.time() - start_time)
                raise LLMError(provider, error_msg, 500)
        
        # Si on arrive ici, toutes les tentatives ont échoué
        self._update_stats(False, time.time() - start_time)
        if last_exception:
            raise LLMNetworkError(provider, f"Échec après {self.max_retries} tentatives", last_exception)
        else:
            raise LLMError(provider, f"Échec après {self.max_retries} tentatives", 500)
    
    def _update_stats(self, success: bool, response_time: float):
        """Met à jour les statistiques de performance."""
        self.stats["total_requests"] += 1
        self.stats["total_response_time"] += response_time
        
        if success:
            self.stats["successful_requests"] += 1
        else:
            self.stats["failed_requests"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de performance du client.
        
        Returns:
            Dictionnaire avec les métriques de performance
        """
        total_requests = self.stats["total_requests"]
        if total_requests == 0:
            return {"message": "Aucune requête effectuée"}
        
        return {
            "total_requests": total_requests,
            "successful_requests": self.stats["successful_requests"],
            "failed_requests": self.stats["failed_requests"],
            "success_rate": self.stats["successful_requests"] / total_requests * 100,
            "average_response_time": self.stats["total_response_time"] / total_requests
        }
    
    async def close(self):
        """Ferme proprement la session HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Session HTTP fermée")
    
    async def __aenter__(self):
        """Support du context manager."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Nettoyage automatique lors de la sortie du context manager."""
        await self.close()