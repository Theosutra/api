# app/core/llm_service.py
import aiohttp
import logging
import json
from typing import Dict, Any, Optional, Tuple, List

from app.config import get_settings
from app.api.models import LLMProvider

# Configuration du logger
logger = logging.getLogger(__name__)
settings = get_settings()

class LLMService:
    """
    Service pour interagir avec différentes API de modèles de langage.
    """
    
    @staticmethod
    async def generate_completion(
        messages: list,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Génère une complétion en utilisant le fournisseur et modèle spécifiés.
        
        Args:
            messages: Liste des messages pour le contexte
            provider: Fournisseur à utiliser (openai, anthropic, google)
            model: Modèle spécifique à utiliser
            temperature: Température pour la génération
            
        Returns:
            Texte généré par le modèle
        """
        # Utiliser les valeurs par défaut si non spécifiées
        if provider is None:
            provider = settings.DEFAULT_PROVIDER
        
        if temperature is None:
            temperature = settings.LLM_TEMPERATURE
        
        # Déterminer quelle implémentation utiliser selon le fournisseur
        if provider == LLMProvider.OPENAI:
            return await LLMService._generate_openai(messages, model, temperature)
        elif provider == LLMProvider.ANTHROPIC:
            return await LLMService._generate_anthropic(messages, model, temperature)
        elif provider == LLMProvider.GOOGLE:
            return await LLMService._generate_google(messages, model, temperature)
        else:
            # Fallback sur OpenAI
            logger.warning(f"Fournisseur '{provider}' non reconnu, utilisation d'OpenAI par défaut")
            return await LLMService._generate_openai(messages, model, temperature)
    
    @staticmethod
    async def _generate_openai(messages: list, model: Optional[str] = None, temperature: float = 0.2) -> str:
        """
        Génère une complétion en utilisant l'API OpenAI.
        """
        if not settings.OPENAI_API_KEY:
            raise ValueError("Clé API OpenAI non configurée")
        
        if model is None:
            model = settings.DEFAULT_OPENAI_MODEL
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        
        logger.debug(f"Appel API OpenAI avec modèle {model}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=settings.LLM_TIMEOUT
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Erreur OpenAI ({response.status}): {error_text}")
                        raise RuntimeError(f"Erreur lors de l'appel à l'API OpenAI: {response.status} - {error_text}")
                    
                    result = await response.json()
                    return result["choices"][0]["message"]["content"].strip()
        
        except Exception as e:
            logger.error(f"Erreur lors de l'appel à l'API OpenAI: {str(e)}")
            raise
    
    @staticmethod
    async def _generate_anthropic(messages: list, model: Optional[str] = None, temperature: float = 0.2) -> str:
        """
        Génère une complétion en utilisant l'API Anthropic Claude.
        """
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("Clé API Anthropic non configurée")
        
        if model is None:
            model = settings.DEFAULT_ANTHROPIC_MODEL
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }
        
        # Convertir format de messages OpenAI vers format Anthropic
        system_message = ""
        user_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            elif msg["role"] == "user":
                user_messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                user_messages.append({"role": "assistant", "content": msg["content"]})
        
        payload = {
            "model": model,
            "system": system_message,
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": 4000
        }
        
        logger.debug(f"Appel API Anthropic avec modèle {model}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=settings.LLM_TIMEOUT
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Erreur Anthropic ({response.status}): {error_text}")
                        raise RuntimeError(f"Erreur lors de l'appel à l'API Anthropic: {response.status} - {error_text}")
                    
                    result = await response.json()
                    return result["content"][0]["text"].strip()
        
        except Exception as e:
            logger.error(f"Erreur lors de l'appel à l'API Anthropic: {str(e)}")
            raise
    
    @staticmethod
    async def _generate_google(messages: list, model: Optional[str] = None, temperature: float = 0.2) -> str:
        """
        Génère une complétion en utilisant l'API Google (Gemini).
        """
        if not settings.GOOGLE_API_KEY:
            raise ValueError("Clé API Google non configurée")
        
        if model is None:
            model = settings.DEFAULT_GOOGLE_MODEL
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Convertir format OpenAI en format Google Gemini
        gemini_messages = []
        system_content = None
        
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            elif msg["role"] == "user":
                gemini_messages.append({"role": "user", "parts": [{"text": msg["content"]}]})
            elif msg["role"] == "assistant":
                gemini_messages.append({"role": "model", "parts": [{"text": msg["content"]}]})
        
        # Si un message système existe, l'ajouter au début
        if system_content:
            # Préfixer le premier message utilisateur avec le contenu système
            for msg in gemini_messages:
                if msg["role"] == "user":
                    msg["parts"][0]["text"] = f"Instructions système: {system_content}\n\nUtilisateur: {msg['parts'][0]['text']}"
                    break
        
        payload = {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 4000
            }
        }
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GOOGLE_API_KEY}"
        
        logger.debug(f"Appel API Google avec modèle {model}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=settings.LLM_TIMEOUT
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Erreur Google ({response.status}): {error_text}")
                        raise RuntimeError(f"Erreur lors de l'appel à l'API Google: {response.status} - {error_text}")
                    
                    result = await response.json()
                    return result["candidates"][0]["content"]["parts"][0]["text"].strip()
        
        except Exception as e:
            logger.error(f"Erreur lors de l'appel à l'API Google: {str(e)}")
            raise

    @staticmethod
    async def get_available_models() -> List[Dict[str, str]]:
        """
        Récupère la liste des modèles disponibles pour chaque fournisseur.
        """
        available_models = []
        
        # OpenAI
        if settings.OPENAI_API_KEY:
            available_models.extend([
                {"provider": "openai", "id": "gpt-4o", "name": "GPT-4o"},
                {"provider": "openai", "id": "gpt-4-turbo", "name": "GPT-4 Turbo"},
                {"provider": "openai", "id": "gpt-4", "name": "GPT-4"},
                {"provider": "openai", "id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo"}
            ])
        
        # Anthropic
        if settings.ANTHROPIC_API_KEY:
            available_models.extend([
                {"provider": "anthropic", "id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
                {"provider": "anthropic", "id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet"},
                {"provider": "anthropic", "id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"}
            ])
        
        # Google
        if settings.GOOGLE_API_KEY:
            available_models.extend([
                {"provider": "google", "id": "gemini-pro", "name": "Gemini Pro"},
                {"provider": "google", "id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
                {"provider": "google", "id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}
            ])
        
        return available_models