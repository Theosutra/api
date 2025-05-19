import aiohttp
import logging
import json
from typing import Dict, Any, Optional, Tuple, List

from app.config import get_settings

# Configuration du logger
logger = logging.getLogger(__name__)
settings = get_settings()

class LLMService:
    """
    Service unifié pour interagir avec différentes API de modèles de langage.
    Remplace complètement le module llm.py avec plus de flexibilité.
    """
    
    @staticmethod
    async def generate_completion(
        messages: list,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Génère une complétion en utilisant le fournisseur et modèle spécifiés.
        
        Args:
            messages: Liste des messages pour le contexte
            provider: Fournisseur à utiliser (openai, anthropic, google)
            model: Modèle spécifique à utiliser
            temperature: Température pour la génération
            max_tokens: Nombre maximum de tokens
            
        Returns:
            Texte généré par le modèle
        """
        # Utiliser les valeurs par défaut si non spécifiées
        if provider is None:
            provider = settings.DEFAULT_PROVIDER
        
        if temperature is None:
            temperature = settings.LLM_TEMPERATURE
        
        # Déterminer quelle implémentation utiliser selon le fournisseur
        if provider == "openai":
            return await LLMService._generate_openai(messages, model, temperature, max_tokens)
        elif provider == "anthropic":
            return await LLMService._generate_anthropic(messages, model, temperature, max_tokens)
        elif provider == "google":
            return await LLMService._generate_google(messages, model, temperature, max_tokens)
        else:
            # Fallback sur OpenAI
            logger.warning(f"Fournisseur '{provider}' non reconnu, utilisation d'OpenAI par défaut")
            return await LLMService._generate_openai(messages, model, temperature, max_tokens)
    
    @staticmethod
    async def generate_sql(
        user_query: str,
        schema: str,
        similar_queries: List[Dict] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Optional[str]:
        """
        Génère une requête SQL à partir d'une demande en langage naturel.
        Remplace la fonction generate_sql de llm.py avec plus de flexibilité.
        
        Args:
            user_query: Requête en langage naturel
            schema: Schéma de la base de données
            similar_queries: Requêtes similaires pour le contexte
            provider: Fournisseur LLM à utiliser
            model: Modèle spécifique
            temperature: Température pour la génération
            
        Returns:
            Requête SQL générée ou None/codes spéciaux
        """
        # Construire le prompt (logique déplacée de translator.py si nécessaire)
        prompt = LLMService._build_sql_prompt(user_query, schema, similar_queries or [])
        
        messages = [
            {
                "role": "system", 
                "content": "Tu es un expert SQL spécialisé dans la traduction de langage naturel en requêtes SQL optimisées. Tu dois retourner UNIQUEMENT le code SQL, sans explications ni formatage markdown. Tu fais tout ton possible pour comprendre l'intention de l'utilisateur, même si la demande est vague."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ]
        
        try:
            response = await LLMService.generate_completion(
                messages=messages,
                provider=provider,
                model=model,
                temperature=temperature
            )
            
            # Nettoyer la réponse (retirer markdown si présent)
            return LLMService._clean_sql_response(response)
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération SQL: {str(e)}")
            raise
    
    @staticmethod
    async def validate_sql_semantically(
        sql_query: str,
        original_request: str,
        schema: str,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Valide qu'une requête SQL correspond sémantiquement à la demande originale.
        Remplace validate_sql_query de llm.py.
        """
        prompt = f"""Tu es un expert SQL chargé d'analyser et de valider des requêtes SQL.

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
        
        messages = [
            {
                "role": "system",
                "content": "Tu es un expert SQL qui valide la correspondance entre une demande et une requête SQL générée."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            response = await LLMService.generate_completion(
                messages=messages,
                provider=provider,
                model=model,
                temperature=0.1
            )
            
            response_upper = response.upper()
            if "HORS SUJET" in response_upper:
                return False, "Cette demande ne concerne pas une requête SQL sur cette base de données."
            elif "OUI" in response_upper:
                return True, "La requête SQL correspond bien à votre demande et est compatible avec le schéma."
            elif "NON" in response_upper:
                return False, "La requête SQL pourrait ne pas correspondre parfaitement à votre demande."
            else:
                # Par défaut, considérer comme valide en cas d'ambiguïté
                return True, "La requête SQL semble correspondre à votre demande."
                
        except Exception as e:
            logger.error(f"Erreur lors de la validation sémantique: {str(e)}")
            return False, f"Impossible de valider la requête: {str(e)}"
    
    @staticmethod
    async def explain_sql(
        sql_query: str,
        original_request: str,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Génère une explication en langage naturel d'une requête SQL.
        Remplace get_sql_explanation de llm.py.
        """
        prompt = f"""Tu es un expert SQL qui explique des requêtes en langage simple.

Demande originale: "{original_request}"

Requête SQL générée:
```sql
{sql_query}
```

Explique en une phrase courte et simple ce que fait cette requête, sans termes techniques complexes.
"""
        
        messages = [
            {
                "role": "system",
                "content": "Tu es un expert SQL qui explique des requêtes SQL de manière simple et accessible."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            return await LLMService.generate_completion(
                messages=messages,
                provider=provider,
                model=model,
                temperature=0.3
            )
        except Exception as e:
            logger.error(f"Erreur lors de l'explication SQL: {str(e)}")
            return "Impossible d'obtenir une explication pour cette requête."
    
    @staticmethod
    async def check_relevance(
        user_query: str,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> bool:
        """
        Vérifie si une requête est pertinente pour une base de données RH.
        Remplace check_query_relevance de llm.py.
        """
        prompt = f"""Tu es un expert RH qui détermine si une question concerne une base de données RH.

La base de données contient des informations sur :
- Employés, contrats, rémunérations
- Entreprises et établissements
- Absences et arrêts de travail
- Déclarations sociales (DSN)

Question: "{user_query}"

Cette question concerne-t-elle les ressources humaines ?
Réponds UNIQUEMENT par "OUI" ou "NON".
"""
        
        messages = [
            {
                "role": "system",
                "content": "Tu détermines si une question concerne les ressources humaines."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            response = await LLMService.generate_completion(
                messages=messages,
                provider=provider,
                model=model,
                temperature=0.1
            )
            return "OUI" in response.upper()
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de pertinence: {str(e)}")
            return True  # Par défaut, considérer comme pertinent
    
    @staticmethod
    def _clean_sql_response(response: str) -> str:
        """Nettoie la réponse du LLM en retirant le formatage markdown."""
        if response.startswith("```sql"):
            response = response.replace("```sql", "", 1)
            if response.endswith("```"):
                response = response[:-3]
        elif response.startswith("```"):
            response = response.replace("```", "", 1)
            if response.endswith("```"):
                response = response[:-3]
        
        return response.strip()
    
    @staticmethod
    def _build_sql_prompt(user_query: str, schema: str, similar_queries: List[Dict]) -> str:
        """Construit le prompt pour la génération SQL (peut être étendu plus tard)."""
        # Version simplifiée - peut être étendue avec la logique complète de build_prompt
        return f"""
Traduis cette question en SQL en respectant le schéma fourni:

Question: {user_query}

Schéma:
{schema}

Tu dois ABSOLUMENT respecter ces règles:
1. Inclure WHERE [alias_depot].ID_USER = ?
2. Joindre avec la table DEPOT
3. Ajouter les hashtags appropriés en fin (#DEPOT_alias# etc.)

SQL:"""
    
    # Méthodes privées pour chaque provider (inchangées)
    @staticmethod
    async def _generate_openai(messages: list, model: Optional[str] = None, temperature: float = 0.2, max_tokens: Optional[int] = None) -> str:
        # Code existant inchangé
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
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
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
                        raise RuntimeError(f"Erreur OpenAI ({response.status}): {error_text}")
                    
                    result = await response.json()
                    return result["choices"][0]["message"]["content"].strip()
        
        except Exception as e:
            logger.error(f"Erreur API OpenAI: {str(e)}")
            raise
    
    @staticmethod
    async def _generate_anthropic(messages: list, model: Optional[str] = None, temperature: float = 0.2, max_tokens: Optional[int] = None) -> str:
        # Code existant inchangé
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("Clé API Anthropic non configurée")
        
        if model is None:
            model = settings.DEFAULT_ANTHROPIC_MODEL
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }
        
        # Convertir format OpenAI vers Anthropic
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
            "max_tokens": max_tokens or 4000
        }
        
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
                        raise RuntimeError(f"Erreur Anthropic ({response.status}): {error_text}")
                    
                    result = await response.json()
                    return result["content"][0]["text"].strip()
        
        except Exception as e:
            logger.error(f"Erreur API Anthropic: {str(e)}")
            raise
    
    @staticmethod
    async def _generate_google(messages: list, model: Optional[str] = None, temperature: float = 0.2, max_tokens: Optional[int] = None) -> str:
        # Code existant inchangé
        if not settings.GOOGLE_API_KEY:
            raise ValueError("Clé API Google non configurée")
        
        if model is None:
            model = settings.DEFAULT_GOOGLE_MODEL
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Convertir format OpenAI vers Google Gemini
        gemini_messages = []
        system_content = None
        
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            elif msg["role"] == "user":
                gemini_messages.append({"role": "user", "parts": [{"text": msg["content"]}]})
            elif msg["role"] == "assistant":
                gemini_messages.append({"role": "model", "parts": [{"text": msg["content"]}]})
        
        # Intégrer le message système dans le premier message utilisateur
        if system_content and gemini_messages:
            for msg in gemini_messages:
                if msg["role"] == "user":
                    msg["parts"][0]["text"] = f"Instructions système: {system_content}\n\nUtilisateur: {msg['parts'][0]['text']}"
                    break
        
        payload = {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens or 4000
            }
        }
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GOOGLE_API_KEY}"
        
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
                        raise RuntimeError(f"Erreur Google ({response.status}): {error_text}")
                    
                    result = await response.json()
                    return result["candidates"][0]["content"]["parts"][0]["text"].strip()
        
        except Exception as e:
            logger.error(f"Erreur API Google: {str(e)}")
            raise
    
    @staticmethod
    async def check_services_health() -> Dict[str, Any]:
        """
        Vérifie l'état de santé de tous les services LLM configurés.
        Remplace check_llm_service de llm.py.
        """
        services_status = {}
        
        # Tester chaque provider configuré
        test_messages = [{"role": "user", "content": "Hello"}]
        
        # OpenAI
        if settings.OPENAI_API_KEY:
            try:
                await LLMService._generate_openai(test_messages, temperature=0.1)
                services_status["openai"] = {
                    "status": "ok",
                    "model": settings.DEFAULT_OPENAI_MODEL
                }
            except Exception as e:
                services_status["openai"] = {
                    "status": "error",
                    "message": str(e)
                }
        else:
            services_status["openai"] = {"status": "not_configured"}
        
        # Anthropic
        if settings.ANTHROPIC_API_KEY:
            try:
                await LLMService._generate_anthropic(test_messages, temperature=0.1)
                services_status["anthropic"] = {
                    "status": "ok",
                    "model": settings.DEFAULT_ANTHROPIC_MODEL
                }
            except Exception as e:
                services_status["anthropic"] = {
                    "status": "error",
                    "message": str(e)
                }
        else:
            services_status["anthropic"] = {"status": "not_configured"}
        
        # Google
        if settings.GOOGLE_API_KEY:
            try:
                await LLMService._generate_google(test_messages, temperature=0.1)
                services_status["google"] = {
                    "status": "ok",
                    "model": settings.DEFAULT_GOOGLE_MODEL
                }
            except Exception as e:
                services_status["google"] = {
                    "status": "error",
                    "message": str(e)
                }
        else:
            services_status["google"] = {"status": "not_configured"}
        
        # Déterminer le statut global
        default_provider = settings.DEFAULT_PROVIDER
        global_status = "ok"
        
        if default_provider in services_status and services_status[default_provider]["status"] != "ok":
            global_status = "error"
        
        return {
            "status": global_status,
            "default_provider": default_provider,
            "providers": services_status
        }
    
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
                {"provider": "openai", "id": "gpt-4o-mini", "name": "GPT-4o Mini"},
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