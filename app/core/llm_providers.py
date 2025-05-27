"""
Providers LLM avec interface uniforme et Factory Pattern.

Ce module définit les providers pour chaque fournisseur LLM (OpenAI, Anthropic, Google)
avec une interface commune et une gestion d'erreurs centralisée.

Author: Datasulting
Version: 2.0.0
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import asyncio

from .http_client import HTTPClient
from .exceptions import LLMConfigError, LLMError

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """
    Interface abstraite pour tous les fournisseurs LLM.
    
    Définit les méthodes que chaque provider doit implémenter
    pour assurer une interface uniforme.
    """
    
    def __init__(self, config, http_client: Optional[HTTPClient] = None):
        """
        Initialise le provider.
        
        Args:
            config: Configuration de l'application
            http_client: Client HTTP (créé automatiquement si None)
        """
        self.config = config
        self.http_client = http_client or HTTPClient()
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self):
        """Valide que la configuration du provider est correcte."""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Retourne le nom du provider."""
        pass
    
    @abstractmethod
    def get_default_model(self) -> str:
        """Retourne le modèle par défaut du provider."""
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[Dict[str, str]]:
        """Retourne la liste des modèles disponibles."""
        pass
    
    @abstractmethod
    async def generate_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Génère une completion à partir des messages.
        
        Args:
            messages: Liste des messages de conversation
            model: Modèle à utiliser (défaut si None)
            **kwargs: Paramètres supplémentaires (temperature, max_tokens, etc.)
            
        Returns:
            Texte généré par le modèle
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Vérifie l'état de santé du provider.
        
        Returns:
            Dictionnaire avec le statut et les informations du provider
        """
        pass
    
    def _build_common_payload(
        self, 
        messages: List[Dict[str, str]], 
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Construit les paramètres communs pour les requêtes.
        
        Args:
            messages: Messages de conversation
            model: Modèle à utiliser
            **kwargs: Paramètres supplémentaires
            
        Returns:
            Dictionnaire avec les paramètres de base
        """
        payload = {
            "model": model,
            "temperature": kwargs.get("temperature", self.config.LLM_TEMPERATURE)
        }
        
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]
        
        return payload


class OpenAIProvider(BaseLLMProvider):
    """
    Provider pour l'API OpenAI (GPT-4, GPT-3.5, etc.).
    
    Gère les spécificités de l'API OpenAI, incluant le format des messages
    et les paramètres spécifiques.
    """
    
    AVAILABLE_MODELS = [
        {"id": "gpt-4o", "name": "GPT-4o", "context_length": 128000},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "context_length": 128000},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "context_length": 128000},
        {"id": "gpt-4", "name": "GPT-4", "context_length": 8192},
        {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "context_length": 16385}
    ]
    
    def _validate_config(self):
        """Valide la configuration OpenAI."""
        if not hasattr(self.config, 'OPENAI_API_KEY') or not self.config.OPENAI_API_KEY:
            raise LLMConfigError("openai", "OPENAI_API_KEY manquante dans la configuration")
    
    def get_provider_name(self) -> str:
        return "openai"
    
    def get_default_model(self) -> str:
        return self.config.DEFAULT_OPENAI_MODEL
    
    def get_available_models(self) -> List[Dict[str, str]]:
        """Retourne les modèles OpenAI disponibles."""
        return [
            {
                "provider": "openai",
                "id": model["id"],
                "name": model["name"]
            }
            for model in self.AVAILABLE_MODELS
        ]
    
    async def generate_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Génère une completion via l'API OpenAI.
        
        Args:
            messages: Messages au format OpenAI
            model: Modèle à utiliser
            **kwargs: Paramètres OpenAI (temperature, max_tokens, etc.)
            
        Returns:
            Texte généré
        """
        model = model or self.get_default_model()
        
        # Validation du modèle
        valid_models = [m["id"] for m in self.AVAILABLE_MODELS]
        if model not in valid_models:
            raise LLMError(
                "openai", 
                f"Modèle '{model}' non supporté. Modèles disponibles: {valid_models}"
            )
        
        # Construction du payload
        payload = self._build_common_payload(messages, model, **kwargs)
        payload["messages"] = messages
        
        # Headers OpenAI
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.OPENAI_API_KEY}"
        }
        
        logger.debug(f"[OpenAI] Requête avec modèle {model}, {len(messages)} messages")
        
        # Appel API
        response = await self.http_client.post_json(
            url="https://api.openai.com/v1/chat/completions",
            headers=headers,
            payload=payload,
            timeout=self.config.LLM_TIMEOUT,
            provider="openai"
        )
        
        # Extraction du contenu
        try:
            content = response["choices"][0]["message"]["content"]
            tokens_used = response.get("usage", {}).get("total_tokens", 0)
            
            logger.debug(f"[OpenAI] Réponse générée, {tokens_used} tokens utilisés")
            return content.strip()
        
        except (KeyError, IndexError) as e:
            logger.error(f"[OpenAI] Format de réponse invalide: {e}")
            raise LLMError("openai", f"Format de réponse invalide: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Vérifie la santé du service OpenAI."""
        try:
            # Test simple avec le modèle le plus léger
            test_messages = [{"role": "user", "content": "test"}]
            
            await self.generate_completion(
                test_messages, 
                model="gpt-3.5-turbo",
                max_tokens=1,
                temperature=0
            )
            
            return {
                "status": "ok",
                "provider": "openai",
                "default_model": self.get_default_model(),
                "available_models": len(self.AVAILABLE_MODELS)
            }
        
        except Exception as e:
            logger.error(f"[OpenAI] Health check échoué: {e}")
            return {
                "status": "error",
                "provider": "openai",
                "error": str(e)
            }


class AnthropicProvider(BaseLLMProvider):
    """
    Provider pour l'API Anthropic (Claude).
    
    Gère les spécificités de l'API Anthropic, incluant la conversion
    du format de messages et les paramètres spécifiques à Claude.
    """
    
    AVAILABLE_MODELS = [
        {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "context_length": 200000},
        {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet", "context_length": 200000},
        {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku", "context_length": 200000},
        {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "context_length": 200000}
    ]
    
    def _validate_config(self):
        """Valide la configuration Anthropic."""
        if not hasattr(self.config, 'ANTHROPIC_API_KEY') or not self.config.ANTHROPIC_API_KEY:
            raise LLMConfigError("anthropic", "ANTHROPIC_API_KEY manquante dans la configuration")
    
    def get_provider_name(self) -> str:
        return "anthropic"
    
    def get_default_model(self) -> str:
        return self.config.DEFAULT_ANTHROPIC_MODEL
    
    def get_available_models(self) -> List[Dict[str, str]]:
        """Retourne les modèles Anthropic disponibles."""
        return [
            {
                "provider": "anthropic",
                "id": model["id"],
                "name": model["name"]
            }
            for model in self.AVAILABLE_MODELS
        ]
    
    def _convert_messages_to_anthropic_format(
        self, 
        messages: List[Dict[str, str]]
    ) -> Tuple[str, List[Dict[str, str]]]:
        """
        Convertit les messages du format OpenAI vers le format Anthropic.
        
        Args:
            messages: Messages au format OpenAI
            
        Returns:
            Tuple (system_message, anthropic_messages)
        """
        system_message = ""
        anthropic_messages = []
        
        for message in messages:
            role = message["role"]
            content = message["content"]
            
            if role == "system":
                system_message = content
            elif role == "user":
                anthropic_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                anthropic_messages.append({"role": "assistant", "content": content})
            else:
                logger.warning(f"[Anthropic] Rôle de message inconnu: {role}")
        
        return system_message, anthropic_messages
    
    async def generate_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Génère une completion via l'API Anthropic.
        
        Args:
            messages: Messages au format OpenAI (convertis automatiquement)
            model: Modèle Claude à utiliser
            **kwargs: Paramètres Anthropic
            
        Returns:
            Texte généré par Claude
        """
        model = model or self.get_default_model()
        
        # Validation du modèle
        valid_models = [m["id"] for m in self.AVAILABLE_MODELS]
        if model not in valid_models:
            raise LLMError(
                "anthropic", 
                f"Modèle '{model}' non supporté. Modèles disponibles: {valid_models}"
            )
        
        # Conversion du format des messages
        system_message, anthropic_messages = self._convert_messages_to_anthropic_format(messages)
        
        # Construction du payload Anthropic
        payload = {
            "model": model,
            "messages": anthropic_messages,
            "temperature": kwargs.get("temperature", self.config.LLM_TEMPERATURE),
            "max_tokens": kwargs.get("max_tokens", 4000)
        }
        
        # Ajouter le message système si présent
        if system_message:
            payload["system"] = system_message
        
        # Headers Anthropic
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }
        
        logger.debug(f"[Anthropic] Requête avec modèle {model}, {len(anthropic_messages)} messages")
        
        # Appel API
        response = await self.http_client.post_json(
            url="https://api.anthropic.com/v1/messages",
            headers=headers,
            payload=payload,
            timeout=self.config.LLM_TIMEOUT,
            provider="anthropic"
        )
        
        # Extraction du contenu
        try:
            content = response["content"][0]["text"]
            tokens_used = response.get("usage", {}).get("output_tokens", 0)
            
            logger.debug(f"[Anthropic] Réponse générée, {tokens_used} tokens utilisés")
            return content.strip()
        
        except (KeyError, IndexError) as e:
            logger.error(f"[Anthropic] Format de réponse invalide: {e}")
            raise LLMError("anthropic", f"Format de réponse invalide: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Vérifie la santé du service Anthropic."""
        try:
            # Test simple avec Claude Haiku (le plus rapide)
            test_messages = [{"role": "user", "content": "test"}]
            
            await self.generate_completion(
                test_messages, 
                model="claude-3-haiku-20240307",
                max_tokens=1,
                temperature=0
            )
            
            return {
                "status": "ok",
                "provider": "anthropic",
                "default_model": self.get_default_model(),
                "available_models": len(self.AVAILABLE_MODELS)
            }
        
        except Exception as e:
            logger.error(f"[Anthropic] Health check échoué: {e}")
            return {
                "status": "error",
                "provider": "anthropic", 
                "error": str(e)
            }


class GoogleProvider(BaseLLMProvider):
    """
    Provider pour l'API Google (Gemini).
    
    Gère les spécificités de l'API Google Generative AI,
    incluant le format spécifique des messages Gemini.
    """
    
    AVAILABLE_MODELS = [
        {"id": "gemini-pro", "name": "Gemini Pro", "context_length": 32768},
        {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "context_length": 1000000},
        {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "context_length": 1000000}
    ]
    
    def _validate_config(self):
        """Valide la configuration Google."""
        if not hasattr(self.config, 'GOOGLE_API_KEY') or not self.config.GOOGLE_API_KEY:
            raise LLMConfigError("google", "GOOGLE_API_KEY manquante dans la configuration")
    
    def get_provider_name(self) -> str:
        return "google"
    
    def get_default_model(self) -> str:
        return self.config.DEFAULT_GOOGLE_MODEL
    
    def get_available_models(self) -> List[Dict[str, str]]:
        """Retourne les modèles Google disponibles."""
        return [
            {
                "provider": "google",
                "id": model["id"],
                "name": model["name"]
            }
            for model in self.AVAILABLE_MODELS
        ]
    
    def _convert_messages_to_gemini_format(
        self, 
        messages: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Convertit les messages du format OpenAI vers le format Gemini.
        
        Args:
            messages: Messages au format OpenAI
            
        Returns:
            Messages au format Gemini
        """
        gemini_messages = []
        system_content = None
        
        for message in messages:
            role = message["role"]
            content = message["content"]
            
            if role == "system":
                system_content = content
            elif role == "user":
                # Intégrer le message système dans le premier message utilisateur
                if system_content:
                    content = f"Instructions système: {system_content}\n\nUtilisateur: {content}"
                    system_content = None  # Utiliser une seule fois
                
                gemini_messages.append({
                    "role": "user",
                    "parts": [{"text": content}]
                })
            elif role == "assistant":
                gemini_messages.append({
                    "role": "model",
                    "parts": [{"text": content}]
                })
            else:
                logger.warning(f"[Google] Rôle de message inconnu: {role}")
        
        return gemini_messages
    
    async def generate_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Génère une completion via l'API Google Gemini.
        
        Args:
            messages: Messages au format OpenAI (convertis automatiquement)
            model: Modèle Gemini à utiliser
            **kwargs: Paramètres Gemini
            
        Returns:
            Texte généré par Gemini
        """
        model = model or self.get_default_model()
        
        # Validation du modèle
        valid_models = [m["id"] for m in self.AVAILABLE_MODELS]
        if model not in valid_models:
            raise LLMError(
                "google", 
                f"Modèle '{model}' non supporté. Modèles disponibles: {valid_models}"
            )
        
        # Conversion du format des messages
        gemini_messages = self._convert_messages_to_gemini_format(messages)
        
        # Construction du payload Gemini
        payload = {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": kwargs.get("temperature", self.config.LLM_TEMPERATURE),
                "maxOutputTokens": kwargs.get("max_tokens", 4000)
            }
        }
        
        # URL avec clé API
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:"
            f"generateContent?key={self.config.GOOGLE_API_KEY}"
        )
        
        # Headers Google (pas d'auth dans headers, clé dans URL)
        headers = {
            "Content-Type": "application/json"
        }
        
        logger.debug(f"[Google] Requête avec modèle {model}, {len(gemini_messages)} messages")
        
        # Appel API
        response = await self.http_client.post_json(
            url=url,
            headers=headers,
            payload=payload,
            timeout=self.config.LLM_TIMEOUT,
            provider="google"
        )
        
        # Extraction du contenu
        try:
            content = response["candidates"][0]["content"]["parts"][0]["text"]
            tokens_used = response.get("usageMetadata", {}).get("totalTokenCount", 0)
            
            logger.debug(f"[Google] Réponse générée, {tokens_used} tokens utilisés")
            return content.strip()
        
        except (KeyError, IndexError) as e:
            logger.error(f"[Google] Format de réponse invalide: {e}")
            raise LLMError("google", f"Format de réponse invalide: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Vérifie la santé du service Google."""
        try:
            # Test simple avec Gemini Flash (le plus rapide)
            test_messages = [{"role": "user", "content": "test"}]
            
            await self.generate_completion(
                test_messages, 
                model="gemini-1.5-flash",
                max_tokens=1,
                temperature=0
            )
            
            return {
                "status": "ok",
                "provider": "google",
                "default_model": self.get_default_model(),
                "available_models": len(self.AVAILABLE_MODELS)
            }
        
        except Exception as e:
            logger.error(f"[Google] Health check échoué: {e}")
            return {
                "status": "error",
                "provider": "google",
                "error": str(e)
            }