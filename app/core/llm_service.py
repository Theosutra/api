"""
Service LLM unifié utilisant le Factory Pattern.

Ce module remplace complètement l'ancien llm_service.py et utilise
la nouvelle architecture avec Factory Pattern pour une meilleure maintenabilité.

Author: Datasulting
Version: 2.0.0
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from functools import lru_cache

from .llm_factory import LLMFactory
from .exceptions import LLMError, LLMConfigError
from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    Service LLM unifié avec Factory Pattern.
    
    Remplace l'ancienne classe LLMService en utilisant le nouveau
    Factory Pattern pour une architecture plus maintenable et extensible.
    
    Cette classe maintient la compatibilité avec l'API existante
    tout en utilisant la nouvelle architecture en arrière-plan.
    """
    
    _factory: Optional[LLMFactory] = None
    _settings = None
    
    @classmethod
    def _get_factory(cls) -> LLMFactory:
        """
        Récupère l'instance de factory (lazy initialization).
        
        Returns:
            Instance LLMFactory configurée
        """
        if cls._factory is None:
            cls._settings = get_settings()
            cls._factory = LLMFactory(cls._settings)
            logger.debug("LLMFactory initialisée")
        
        return cls._factory
    
    @classmethod
    async def generate_completion(
        cls,
        messages: List[Dict[str, str]],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Génère une completion en utilisant le fournisseur et modèle spécifiés.
        
        Args:
            messages: Liste des messages pour le contexte
            provider: Fournisseur à utiliser (openai, anthropic, google)
            model: Modèle spécifique à utiliser
            temperature: Température pour la génération
            max_tokens: Nombre maximum de tokens
            
        Returns:
            Texte généré par le modèle
            
        Raises:
            LLMError: Si la génération échoue
        """
        factory = cls._get_factory()
        
        # Préparer les paramètres optionnels
        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        
        try:
            return await factory.generate_completion(
                messages=messages,
                provider=provider,
                model=model,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Erreur lors de la génération completion: {e}")
            raise
    
    @classmethod
    async def generate_sql(
        cls,
        user_query: str,
        schema: str,
        similar_queries: Optional[List[Dict]] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Optional[str]:
        """
        Génère une requête SQL à partir d'une demande en langage naturel.
        
        Args:
            user_query: Requête en langage naturel
            schema: Schéma de la base de données
            similar_queries: Requêtes similaires pour le contexte
            provider: Fournisseur LLM à utiliser
            model: Modèle spécifique
            temperature: Température pour la génération
            
        Returns:
            Requête SQL générée ou None en cas d'erreur
        """
        factory = cls._get_factory()
        
        try:
            return await factory.generate_sql(
                user_query=user_query,
                schema=schema,
                similar_queries=similar_queries,
                provider=provider,
                model=model,
                temperature=temperature
            )
        except Exception as e:
            logger.error(f"Erreur lors de la génération SQL: {e}")
            return None
    
    @classmethod
    async def validate_sql_semantically(
        cls,
        sql_query: str,
        original_request: str,
        schema: str,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Valide qu'une requête SQL correspond sémantiquement à la demande originale.
        
        Args:
            sql_query: Requête SQL à valider
            original_request: Demande originale en langage naturel
            schema: Schéma de la base de données
            provider: Fournisseur LLM pour la validation
            model: Modèle spécifique
            
        Returns:
            Tuple (is_valid, message)
        """
        factory = cls._get_factory()
        
        try:
            return await factory.validate_sql_semantically(
                sql_query=sql_query,
                original_request=original_request,
                schema=schema,
                provider=provider,
                model=model
            )
        except Exception as e:
            logger.error(f"Erreur lors de la validation sémantique: {e}")
            return False, f"Impossible de valider la requête: {e}"
    
    @classmethod
    async def explain_sql(
        cls,
        sql_query: str,
        original_request: str,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Génère une explication en langage naturel d'une requête SQL.
        
        Args:
            sql_query: Requête SQL à expliquer
            original_request: Demande originale
            provider: Fournisseur LLM pour l'explication
            model: Modèle spécifique
            
        Returns:
            Explication en langage naturel
        """
        factory = cls._get_factory()
        
        try:
            return await factory.explain_sql(
                sql_query=sql_query,
                original_request=original_request,
                provider=provider,
                model=model
            )
        except Exception as e:
            logger.error(f"Erreur lors de l'explication SQL: {e}")
            return "Impossible d'obtenir une explication pour cette requête."
    
    @classmethod
    async def check_relevance(
        cls,
        user_query: str,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> bool:
        """
        Vérifie si une requête est pertinente pour une base de données RH.
        
        Args:
            user_query: Question à vérifier
            provider: Fournisseur LLM
            model: Modèle spécifique
            
        Returns:
            True si la question concerne les RH
        """
        factory = cls._get_factory()
        
        try:
            return await factory.check_relevance(
                user_query=user_query,
                provider=provider,
                model=model
            )
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de pertinence: {e}")
            return True  # Par défaut, considérer comme pertinent
    
    @classmethod
    async def check_services_health(cls) -> Dict[str, Any]:
        """
        Vérifie l'état de santé de tous les services LLM configurés.
        
        Returns:
            Dictionnaire avec l'état de chaque service
        """
        factory = cls._get_factory()
        
        try:
            return await factory.health_check_all()
        except Exception as e:
            logger.error(f"Erreur lors du health check: {e}")
            return {
                "status": "error",
                "default_provider": cls._settings.DEFAULT_PROVIDER if cls._settings else "unknown",
                "providers": {},
                "error": str(e)
            }
    
    @classmethod
    async def get_available_models(cls) -> List[Dict[str, str]]:
        """
        Récupère la liste des modèles disponibles pour tous les fournisseurs.
        
        Returns:
            Liste des modèles disponibles
        """
        factory = cls._get_factory()
        
        try:
            return await factory.get_available_models()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des modèles: {e}")
            return []
    
    @classmethod
    def get_configured_providers(cls) -> List[str]:
        """
        Retourne la liste des providers correctement configurés.
        
        Returns:
            Liste des noms des providers configurés
        """
        factory = cls._get_factory()
        
        try:
            return factory.get_configured_providers()
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des providers: {e}")
            return []
    
    @classmethod
    async def cleanup(cls):
        """
        Nettoie les ressources (à appeler lors de l'arrêt de l'application).
        """
        if cls._factory:
            try:
                await cls._factory.close()
                cls._factory = None
                logger.info("LLMService nettoyé")
            except Exception as e:
                logger.error(f"Erreur lors du nettoyage LLMService: {e}")


# =============================================================================
# FONCTIONS DE COMPATIBILITÉ AVEC L'ANCIEN CODE
# =============================================================================
# Ces fonctions maintiennent la compatibilité avec l'ancien code qui appelle
# directement les fonctions du module llm_service.py

async def generate_sql(
    user_query: str,
    schema: str,
    similar_queries: Optional[List[Dict]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None
) -> Optional[str]:
    """
    Fonction de compatibilité pour generate_sql.
    
    DEPRECATED: Utilisez LLMService.generate_sql() à la place.
    """
    logger.warning("Utilisation de generate_sql() dépréciée. Utilisez LLMService.generate_sql()")
    return await LLMService.generate_sql(
        user_query=user_query,
        schema=schema,
        similar_queries=similar_queries,
        provider=provider,
        model=model,
        temperature=temperature
    )


async def validate_sql_query(
    sql_query: str,
    original_request: str,
    schema: str,
    provider: Optional[str] = None,
    model: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Fonction de compatibilité pour validate_sql_query.
    
    DEPRECATED: Utilisez LLMService.validate_sql_semantically() à la place.
    """
    logger.warning("Utilisation de validate_sql_query() dépréciée. Utilisez LLMService.validate_sql_semantically()")
    return await LLMService.validate_sql_semantically(
        sql_query=sql_query,
        original_request=original_request,
        schema=schema,
        provider=provider,
        model=model
    )


async def get_sql_explanation(
    sql_query: str,
    original_request: str,
    provider: Optional[str] = None,
    model: Optional[str] = None
) -> str:
    """
    Fonction de compatibilité pour get_sql_explanation.
    
    DEPRECATED: Utilisez LLMService.explain_sql() à la place.
    """
    logger.warning("Utilisation de get_sql_explanation() dépréciée. Utilisez LLMService.explain_sql()")
    return await LLMService.explain_sql(
        sql_query=sql_query,
        original_request=original_request,
        provider=provider,
        model=model
    )


async def check_query_relevance(
    user_query: str,
    provider: Optional[str] = None,
    model: Optional[str] = None
) -> bool:
    """
    Fonction de compatibilité pour check_query_relevance.
    
    DEPRECATED: Utilisez LLMService.check_relevance() à la place.
    """
    logger.warning("Utilisation de check_query_relevance() dépréciée. Utilisez LLMService.check_relevance()")
    return await LLMService.check_relevance(
        user_query=user_query,
        provider=provider,
        model=model
    )


async def check_llm_service() -> Dict[str, Any]:
    """
    Fonction de compatibilité pour check_llm_service.
    
    DEPRECATED: Utilisez LLMService.check_services_health() à la place.
    """
    logger.warning("Utilisation de check_llm_service() dépréciée. Utilisez LLMService.check_services_health()")
    return await LLMService.check_services_health()


# =============================================================================
# INITIALISATION ET NETTOYAGE DE L'APPLICATION
# =============================================================================

async def initialize_llm_service():
    """
    Initialise le service LLM (appelé au démarrage de l'application).
    """
    try:
        # Forcer l'initialisation de la factory
        LLMService._get_factory()
        
        # Vérifier les providers configurés
        configured_providers = LLMService.get_configured_providers()
        logger.info(f"LLMService initialisé avec providers: {configured_providers}")
        
        # Optionnel: vérifier la santé des services
        health = await LLMService.check_services_health()
        if health["status"] != "ok":
            logger.warning(f"Certains services LLM ne sont pas disponibles: {health}")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation LLMService: {e}")
        raise


async def cleanup_llm_service():
    """
    Nettoie le service LLM (appelé à l'arrêt de l'application).
    """
    await LLMService.cleanup()