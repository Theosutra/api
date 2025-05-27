"""
Exceptions personnalisées pour l'API NL2SQL.

Ce module définit toutes les exceptions spécifiques à l'application,
permettant une gestion d'erreurs fine et des messages d'erreur appropriés.

Author: Datasulting
Version: 2.0.0
"""

from typing import Optional, Dict, Any


class NL2SQLError(Exception):
    """
    Exception de base pour toutes les erreurs spécifiques à NL2SQL.
    
    Toutes les autres exceptions de l'application héritent de cette classe
    pour permettre une gestion d'erreurs centralisée.
    """
    pass


class LLMError(NL2SQLError):
    """
    Exception générique pour les erreurs liées aux fournisseurs LLM.
    
    Args:
        provider: Nom du fournisseur LLM (openai, anthropic, google)
        message: Message d'erreur détaillé
        status_code: Code de statut HTTP associé (défaut: 500)
        details: Informations supplémentaires sur l'erreur
    """
    
    def __init__(
        self, 
        provider: str, 
        message: str, 
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.provider = provider
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(f"[{provider}] {message}")


class LLMNetworkError(LLMError):
    """
    Exception pour les erreurs réseau avec les API LLM.
    
    Levée quand une requête réseau échoue (timeout, connexion refusée, etc.)
    """
    
    def __init__(self, provider: str, message: str, original_error: Optional[Exception] = None):
        details = {"original_error": str(original_error)} if original_error else {}
        super().__init__(provider, f"Erreur réseau: {message}", 503, details)


class LLMAuthError(LLMError):
    """
    Exception pour les erreurs d'authentification avec les API LLM.
    
    Levée quand la clé API est invalide, expirée ou manquante.
    """
    
    def __init__(self, provider: str, message: str = "Clé API invalide ou expirée"):
        super().__init__(provider, message, 401)


class LLMQuotaError(LLMError):
    """
    Exception pour les erreurs de quota/limite de débit des API LLM.
    
    Levée quand les limites de l'API sont dépassées.
    """
    
    def __init__(self, provider: str, message: str = "Limite de débit ou quota dépassé"):
        super().__init__(provider, message, 429)


class LLMConfigError(LLMError):
    """
    Exception pour les erreurs de configuration des fournisseurs LLM.
    
    Levée quand un fournisseur n'est pas configuré correctement.
    """
    
    def __init__(self, provider: str, message: str):
        super().__init__(provider, f"Erreur de configuration: {message}", 500)


class ValidationError(NL2SQLError):
    """
    Exception pour les erreurs de validation des données.
    
    Args:
        message: Message d'erreur
        field: Champ qui a échoué à la validation (optionnel)
        value: Valeur qui a échoué à la validation (optionnel)
    """
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None):
        self.field = field
        self.value = value
        full_message = f"Validation échouée: {message}"
        if field:
            full_message += f" (champ: {field})"
        super().__init__(full_message)


class FrameworkError(ValidationError):
    """
    Exception pour les erreurs de conformité au framework SQL obligatoire.
    
    Levée quand une requête SQL ne respecte pas les règles de sécurité obligatoires.
    """
    
    def __init__(self, message: str, sql_query: Optional[str] = None):
        self.sql_query = sql_query
        super().__init__(f"Framework non respecté: {message}", "sql_query", sql_query)


class EmbeddingError(NL2SQLError):
    """
    Exception pour les erreurs du service d'embedding.
    
    Levée quand la génération d'embeddings échoue.
    """
    
    def __init__(self, message: str, model_name: Optional[str] = None):
        self.model_name = model_name
        full_message = f"Erreur embedding: {message}"
        if model_name:
            full_message += f" (modèle: {model_name})"
        super().__init__(full_message)


class VectorSearchError(NL2SQLError):
    """
    Exception pour les erreurs de recherche vectorielle (Pinecone).
    
    Levée quand les opérations Pinecone échouent.
    """
    
    def __init__(self, message: str, index_name: Optional[str] = None):
        self.index_name = index_name
        full_message = f"Erreur recherche vectorielle: {message}"
        if index_name:
            full_message += f" (index: {index_name})"
        super().__init__(full_message)


class CacheError(NL2SQLError):
    """
    Exception pour les erreurs du système de cache Redis.
    
    Levée quand les opérations Redis échouent (non critique).
    """
    
    def __init__(self, message: str, operation: Optional[str] = None):
        self.operation = operation
        full_message = f"Erreur cache: {message}"
        if operation:
            full_message += f" (opération: {operation})"
        super().__init__(full_message)


class SchemaError(NL2SQLError):
    """
    Exception pour les erreurs de chargement ou de validation du schéma.
    
    Levée quand le fichier de schéma est introuvable ou invalide.
    """
    
    def __init__(self, message: str, schema_path: Optional[str] = None):
        self.schema_path = schema_path
        full_message = f"Erreur schéma: {message}"
        if schema_path:
            full_message += f" (chemin: {schema_path})"
        super().__init__(full_message)


# Mapping des codes d'erreur HTTP vers les exceptions
HTTP_ERROR_MAPPING = {
    400: ValidationError,
    401: LLMAuthError,
    403: LLMAuthError,
    429: LLMQuotaError,
    500: LLMError,
    503: LLMNetworkError
}