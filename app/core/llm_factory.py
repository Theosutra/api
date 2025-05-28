"""
Factory Pattern pour la gestion unifiée des fournisseurs LLM avec prompts Jinja2.

Version modifiée pour utiliser le PromptManager centralisé au lieu
des prompts codés en dur.

Author: Datasulting
Version: 2.0.0
"""

import logging
from typing import Dict, Any, List, Optional, Union
import asyncio

from .llm_providers import BaseLLMProvider, OpenAIProvider, AnthropicProvider, GoogleProvider
from .http_client import HTTPClient
from .exceptions import LLMError, LLMConfigError

logger = logging.getLogger(__name__)


class LLMFactory:
    """
    Factory pour créer et gérer les providers LLM avec support Jinja2.
    
    Fonctionnalités:
    - Création centralisée des providers
    - Cache des instances de providers
    - Interface unifiée pour tous les LLM
    - Gestion automatique des erreurs
    - Health checks centralisés
    - Prompts modulaires via Jinja2
    """
    
    # Mapping des providers disponibles
    _PROVIDER_CLASSES = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider
    }
    
    def __init__(self, config):
        """
        Initialise la factory LLM.
        
        Args:
            config: Configuration de l'application contenant les clés API
        """
        self.config = config
        self.http_client = HTTPClient()
        self._provider_instances: Dict[str, BaseLLMProvider] = {}
        self._initialization_lock = asyncio.Lock()
        
        # Gestionnaire de prompts Jinja2 (lazy loading pour éviter dépendances circulaires)
        self._prompt_manager = None
        
        logger.info(f"LLMFactory initialisée avec provider par défaut: {config.DEFAULT_PROVIDER}")
    
    @property
    def prompt_manager(self):
        """Propriété pour lazy loading du PromptManager."""
        if self._prompt_manager is None:
            try:
                from app.prompts.prompt_manager import get_prompt_manager
                self._prompt_manager = get_prompt_manager()
            except ImportError as e:
                logger.warning(f"PromptManager non disponible, utilisation des prompts par défaut: {e}")
                self._prompt_manager = None
        return self._prompt_manager
    
    async def get_provider(self, provider_name: str) -> BaseLLMProvider:
        """
        Récupère ou crée une instance de provider LLM.
        
        Args:
            provider_name: Nom du provider ("openai", "anthropic", "google")
            
        Returns:
            Instance du provider demandé
            
        Raises:
            LLMConfigError: Si le provider n'est pas supporté ou mal configuré
        """
        if provider_name not in self._PROVIDER_CLASSES:
            available_providers = list(self._PROVIDER_CLASSES.keys())
            raise LLMConfigError(
                provider_name, 
                f"Provider non supporté. Providers disponibles: {available_providers}"
            )
        
        # Vérification thread-safe de l'instance en cache
        if provider_name not in self._provider_instances:
            async with self._initialization_lock:
                # Double-check pattern pour éviter la création multiple
                if provider_name not in self._provider_instances:
                    try:
                        provider_class = self._PROVIDER_CLASSES[provider_name]
                        instance = provider_class(self.config, self.http_client)
                        self._provider_instances[provider_name] = instance
                        
                        logger.debug(f"Provider {provider_name} créé et mis en cache")
                    
                    except Exception as e:
                        logger.error(f"Erreur lors de la création du provider {provider_name}: {e}")
                        raise LLMConfigError(provider_name, f"Impossible de créer le provider: {e}")
        
        return self._provider_instances[provider_name]
    
    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Interface unifiée pour générer des completions.
        
        Args:
            messages: Liste des messages de conversation
            provider: Nom du provider (utilise le défaut si None)
            model: Modèle spécifique (utilise le défaut du provider si None)
            **kwargs: Paramètres supplémentaires (temperature, max_tokens, etc.)
            
        Returns:
            Texte généré par le modèle
            
        Raises:
            LLMError: Si la génération échoue
        """
        provider_name = provider or self.config.DEFAULT_PROVIDER
        
        try:
            llm_provider = await self.get_provider(provider_name)
            
            logger.debug(
                f"Génération completion avec {provider_name}, "
                f"modèle: {model or 'défaut'}, "
                f"messages: {len(messages)}"
            )
            
            result = await llm_provider.generate_completion(messages, model, **kwargs)
            
            logger.info(f"Completion générée avec succès par {provider_name}")
            return result
        
        except Exception as e:
            logger.error(f"Erreur lors de la génération avec {provider_name}: {e}")
            raise
    
    async def generate_sql(
        self,
        user_query: str,
        schema: str,
        similar_queries: Optional[List[Dict]] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Génère une requête SQL à partir d'une demande en langage naturel.
        Utilise le PromptManager pour les prompts Jinja2 avec fallback.
        
        Args:
            user_query: Question en langage naturel
            schema: Schéma de la base de données
            similar_queries: Requêtes similaires pour le contexte
            provider: Fournisseur LLM à utiliser
            model: Modèle spécifique
            temperature: Température pour la génération
            context: Contexte additionnel (période, département, etc.)
            
        Returns:
            Requête SQL générée
        """
        try:
            # Tentative d'utilisation du PromptManager
            if self.prompt_manager:
                try:
                    system_content = self.prompt_manager.get_system_message()
                    user_content = self.prompt_manager.get_sql_generation_prompt(
                        user_query=user_query,
                        schema=schema,
                        similar_queries=similar_queries or [],
                        context=context or {}
                    )
                except Exception as e:
                    logger.warning(f"Erreur PromptManager, utilisation prompts par défaut: {e}")
                    system_content, user_content = self._build_fallback_sql_prompt(
                        user_query, schema, similar_queries or []
                    )
            else:
                # Fallback vers les prompts par défaut
                system_content, user_content = self._build_fallback_sql_prompt(
                    user_query, schema, similar_queries or []
                )
            
            messages = [
                {
                    "role": "system",
                    "content": system_content
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ]
            
            completion_kwargs = {}
            if temperature is not None:
                completion_kwargs["temperature"] = temperature
            
            response = await self.generate_completion(
                messages=messages,
                provider=provider,
                model=model,
                **completion_kwargs
            )
            
            # Nettoyer la réponse (retirer markdown si présent)
            return self._clean_sql_response(response)
        
        except Exception as e:
            logger.error(f"Erreur lors de la génération SQL: {e}")
            raise
    
    async def validate_sql_semantically(
        self,
        sql_query: str,
        original_request: str,
        schema: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, str]:
        """
        Valide qu'une requête SQL correspond sémantiquement à la demande originale.
        Utilise le PromptManager pour le prompt de validation avec fallback.
        
        Args:
            sql_query: Requête SQL à valider
            original_request: Demande originale en langage naturel
            schema: Schéma de la base de données
            provider: Fournisseur LLM pour la validation
            model: Modèle spécifique pour la validation
            context: Contexte de validation (mode strict, etc.)
            
        Returns:
            Tuple (is_valid, message)
        """
        try:
            # Tentative d'utilisation du PromptManager
            if self.prompt_manager:
                try:
                    prompt_content = self.prompt_manager.get_semantic_validation_prompt(
                        sql_query=sql_query,
                        original_request=original_request,
                        schema=schema,
                        context=context or {}
                    )
                except Exception as e:
                    logger.warning(f"Erreur PromptManager validation, utilisation prompt par défaut: {e}")
                    prompt_content = self._build_fallback_validation_prompt(
                        sql_query, original_request, schema
                    )
            else:
                # Fallback vers le prompt par défaut
                prompt_content = self._build_fallback_validation_prompt(
                    sql_query, original_request, schema
                )
            
            messages = [
                {
                    "role": "system",
                    "content": "Tu es un expert SQL qui valide la correspondance entre une demande et une requête SQL générée."
                },
                {
                    "role": "user",
                    "content": prompt_content
                }
            ]
            
            response = await self.generate_completion(
                messages=messages,
                provider=provider,
                model=model,
                temperature=0.1
            )
            
            response_upper = response.upper()
            if "HORS_SUJET" in response_upper:
                return False, "Cette demande ne concerne pas une requête SQL sur cette base de données."
            elif "OUI" in response_upper:
                return True, "La requête SQL correspond bien à votre demande et est compatible avec le schéma."
            elif "NON" in response_upper:
                return False, "La requête SQL pourrait ne pas correspondre parfaitement à votre demande."
            else:
                # Par défaut, considérer comme valide en cas d'ambiguïté
                return True, "La requête SQL semble correspondre à votre demande."
        
        except Exception as e:
            logger.error(f"Erreur lors de la validation sémantique: {e}")
            return False, f"Impossible de valider la requête: {e}"
    
    async def explain_sql(
        self,
        sql_query: str,
        original_request: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Génère une explication en langage naturel d'une requête SQL.
        Utilise le PromptManager pour le prompt d'explication avec fallback.
        
        Args:
            sql_query: Requête SQL à expliquer
            original_request: Demande originale
            provider: Fournisseur LLM pour l'explication
            model: Modèle spécifique
            context: Contexte (public cible, niveau de détail, etc.)
            
        Returns:
            Explication en langage naturel
        """
        try:
            # Tentative d'utilisation du PromptManager
            if self.prompt_manager:
                try:
                    prompt_content = self.prompt_manager.get_explanation_prompt(
                        sql_query=sql_query,
                        original_request=original_request,
                        context=context or {}
                    )
                except Exception as e:
                    logger.warning(f"Erreur PromptManager explication, utilisation prompt par défaut: {e}")
                    prompt_content = self._build_fallback_explanation_prompt(
                        sql_query, original_request
                    )
            else:
                # Fallback vers le prompt par défaut
                prompt_content = self._build_fallback_explanation_prompt(
                    sql_query, original_request
                )
            
            messages = [
                {
                    "role": "system",
                    "content": "Tu es un expert SQL qui explique des requêtes SQL de manière simple et accessible."
                },
                {
                    "role": "user",
                    "content": prompt_content
                }
            ]
            
            return await self.generate_completion(
                messages=messages,
                provider=provider,
                model=model,
                temperature=0.3
            )
        except Exception as e:
            logger.error(f"Erreur lors de l'explication SQL: {e}")
            return "Impossible d'obtenir une explication pour cette requête."
    
    async def check_relevance(
        self,
        user_query: str,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> bool:
        """
        Vérifie si une requête est pertinente pour une base de données RH.
        Utilise le PromptManager pour le prompt de pertinence avec fallback.
        
        Args:
            user_query: Question à vérifier
            provider: Fournisseur LLM
            model: Modèle spécifique
            
        Returns:
            True si la question concerne les RH
        """
        try:
            # Tentative d'utilisation du PromptManager
            if self.prompt_manager:
                try:
                    prompt_content = self.prompt_manager.get_relevance_check_prompt(user_query)
                except Exception as e:
                    logger.warning(f"Erreur PromptManager pertinence, utilisation prompt par défaut: {e}")
                    prompt_content = self._build_fallback_relevance_prompt(user_query)
            else:
                # Fallback vers le prompt par défaut
                prompt_content = self._build_fallback_relevance_prompt(user_query)
            
            messages = [
                {
                    "role": "system",
                    "content": "Tu détermines si une question concerne les ressources humaines."
                },
                {
                    "role": "user",
                    "content": prompt_content
                }
            ]
            
            response = await self.generate_completion(
                messages=messages,
                provider=provider,
                model=model,
                temperature=0.1
            )
            return "OUI" in response.upper()
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de pertinence: {e}")
            return True  # Par défaut, considérer comme pertinent
    
    # ========================================================================
    # PROMPTS FALLBACK (anciens prompts codés en dur)
    # ========================================================================
    
    def _build_fallback_sql_prompt(
        self, 
        user_query: str, 
        schema: str, 
        similar_queries: List[Dict]
    ) -> tuple[str, str]:
        """Construit les prompts SQL de fallback."""
        system_message = (
            "Tu es un expert SQL spécialisé dans la traduction de langage naturel "
            "en requêtes SQL optimisées. Tu dois retourner UNIQUEMENT le code SQL, "
            "sans explications ni formatage markdown. Tu fais tout ton possible pour "
            "comprendre l'intention de l'utilisateur, même si la demande est vague."
        )
        
        prompt = f"""
Traduis cette question en SQL en respectant le schéma fourni:

Question: {user_query}

Schéma:
{schema}

Tu dois ABSOLUMENT respecter ces règles:
1. Inclure WHERE [alias_depot].ID_USER = ?
2. Joindre avec la table DEPOT
3. Ajouter les hashtags appropriés en fin (#DEPOT_alias# etc.)

SQL:"""
        
        # Ajouter les requêtes similaires si disponibles
        if similar_queries:
            prompt += "\n\nExemples de requêtes similaires:\n"
            for i, query in enumerate(similar_queries[:3], 1):
                metadata = query.get('metadata', {})
                query_text = metadata.get('texte_complet', 'N/A')
                sql_query = metadata.get('requete', 'N/A')
                score = query.get('score', 0)
                
                prompt += f"""
Exemple {i} (Score: {score:.2f}):
Question: "{query_text}"
SQL: {sql_query}
"""
        
        return system_message, prompt
    
    def _build_fallback_validation_prompt(
        self, 
        sql_query: str, 
        original_request: str, 
        schema: str
    ) -> str:
        """Construit le prompt de validation de fallback."""
        return f"""Tu es un expert SQL chargé d'analyser et de valider des requêtes SQL.

La requête SQL suivante a été générée pour répondre à cette demande: "{original_request}"

Requête SQL générée:
```sql
{sql_query}
```

Schéma de la base de données:
```sql
{schema}
```

TÂCHE:
1. Vérifie si la demande concerne une requête SQL sur cette base de données
2. Si oui, analyse si la requête SQL est compatible avec le schéma
3. Évalue si la requête répond à l'intention de l'utilisateur
4. RÉPONDS UNIQUEMENT par "OUI" ou "NON" ou "HORS SUJET"
"""
    
    def _build_fallback_explanation_prompt(
        self, 
        sql_query: str, 
        original_request: str
    ) -> str:
        """Construit le prompt d'explication de fallback."""
        return f"""Tu es un expert SQL qui explique des requêtes en langage simple.

Demande originale: "{original_request}"

Requête SQL générée:
```sql
{sql_query}
```

Explique en une phrase courte et simple ce que fait cette requête, sans termes techniques complexes.
"""
    
    def _build_fallback_relevance_prompt(self, user_query: str) -> str:
        """Construit le prompt de pertinence de fallback."""
        return f"""Tu es un expert RH qui détermine si une question concerne une base de données RH.

La base de données contient des informations sur :
- Employés, contrats, rémunérations
- Entreprises et établissements
- Absences et arrêts de travail
- Déclarations sociales (DSN)

Question: "{user_query}"

Cette question concerne-t-elle les ressources humaines ?
Réponds UNIQUEMENT par "OUI" ou "NON".
"""
    
    async def health_check_all(self) -> Dict[str, Any]:
        """
        Vérifie l'état de santé de tous les providers LLM configurés.
        
        Returns:
            Dictionnaire avec l'état de chaque provider
        """
        results = {}
        
        # Tester chaque provider disponible
        for provider_name in self._PROVIDER_CLASSES:
            try:
                provider = await self.get_provider(provider_name)
                results[provider_name] = await provider.health_check()
            except LLMConfigError as e:
                results[provider_name] = {
                    "status": "not_configured",
                    "provider": provider_name,
                    "error": e.message
                }
            except Exception as e:
                results[provider_name] = {
                    "status": "error",
                    "provider": provider_name,
                    "error": str(e)
                }
        
        # Déterminer le statut global
        default_provider = self.config.DEFAULT_PROVIDER
        default_status = results.get(default_provider, {}).get("status", "error")
        global_status = "ok" if default_status == "ok" else "error"
        
        # Informations sur le système de prompts
        prompt_status = "ok" if self.prompt_manager else "fallback"
        prompt_info = {
            "status": prompt_status,
            "templates": self.prompt_manager.list_available_templates() if self.prompt_manager else []
        }
        
        return {
            "status": global_status,
            "default_provider": default_provider,
            "providers": results,
            "prompt_manager": prompt_info
        }
    
    async def get_available_models(self) -> List[Dict[str, str]]:
        """
        Récupère la liste de tous les modèles disponibles.
        
        Returns:
            Liste des modèles disponibles pour tous les providers configurés
        """
        all_models = []
        
        for provider_name in self._PROVIDER_CLASSES:
            try:
                provider = await self.get_provider(provider_name)
                models = provider.get_available_models()
                all_models.extend(models)
            except LLMConfigError:
                # Provider non configuré, ignorer
                continue
            except Exception as e:
                logger.warning(f"Impossible de récupérer les modèles pour {provider_name}: {e}")
                continue
        
        return all_models
    
    def get_configured_providers(self) -> List[str]:
        """
        Retourne la liste des providers correctement configurés.
        
        Returns:
            Liste des noms des providers configurés
        """
        configured = []
        
        for provider_name in self._PROVIDER_CLASSES:
            try:
                # Tentative de création pour vérifier la configuration
                provider_class = self._PROVIDER_CLASSES[provider_name]
                provider_class(self.config, self.http_client)
                configured.append(provider_name)
            except LLMConfigError:
                # Provider non configuré
                continue
            except Exception:
                # Autre erreur, considérer comme non configuré
                continue
        
        return configured
    
    @staticmethod
    def _clean_sql_response(response: str) -> str:
        """
        Nettoie la réponse du LLM en retirant le formatage markdown.
        
        Args:
            response: Réponse brute du LLM
            
        Returns:
            Requête SQL nettoyée
        """
        if response.startswith("```sql"):
            response = response.replace("```sql", "", 1)
            if response.endswith("```"):
                response = response[:-3]
        elif response.startswith("```"):
            response = response.replace("```", "", 1)
            if response.endswith("```"):
                response = response[:-3]
        
        return response.strip()
    
    async def close(self):
        """Ferme proprement toutes les ressources."""
        try:
            await self.http_client.close()
            logger.info("LLMFactory fermée proprement")
        except Exception as e:
            logger.error(f"Erreur lors de la fermeture de LLMFactory: {e}")
    
    async def __aenter__(self):
        """Support du context manager."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Nettoyage automatique."""
        await self.close()