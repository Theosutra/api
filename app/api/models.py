from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from enum import Enum
import re


class LLMProvider(str, Enum):
    """
    Énumération des fournisseurs de modèles de langage.
    """
    OPENAI = "openai"
    ANTHROPIC = "anthropic" 
    GOOGLE = "google"


class SimilarQueryDetail(BaseModel):
    """
    Modèle pour les détails d'une requête similaire trouvée par la recherche vectorielle.
    """
    score: float = Field(..., description="Score de similarité (0-1)")
    texte_complet: str = Field(..., description="Texte original de la requête similaire")
    requete: str = Field(..., description="Requête SQL correspondante")
    id: Optional[str] = Field(None, description="Identifiant unique du vecteur dans Pinecone")
    
    class Config:
        json_schema_extra = {
            "example": {
                "score": 0.89,
                "texte_complet": "Liste des employés en CDI embauchés en 2023",
                "requete": "SELECT f.NOM, f.PRENOM FROM FACTS f JOIN DEPOT d ON f.ID_NUMDEPOT = d.ID WHERE d.ID_USER = ? AND f.NATURE_CONTRAT = '01';",
                "id": "vec_123456"
            }
        }


class SQLTranslationRequest(BaseModel):
    """
    Modèle Pydantic pour la requête de traduction du langage naturel vers SQL.
    Définit la structure et les contraintes des données d'entrée.
    """
    query: str = Field(
        ..., 
        description="Requête en langage naturel à traduire en SQL",
        min_length=3,
        max_length=1000
    )
    schema_path: Optional[str] = Field(
        None, 
        description="Chemin vers le fichier de schéma SQL (optionnel)"
    )
    # Renommé 'validate' en 'should_validate' pour éviter le conflit avec la méthode de BaseModel
    should_validate: bool = Field(
        True, 
        description="Valider la requête SQL générée",
        alias="validate"  # Permet aux clients API d'utiliser toujours 'validate'
    )
    explain: bool = Field(
        True, 
        description="Fournir une explication de la requête SQL"
    )
    
    # NOUVEAUX CHAMPS pour le choix du provider et modèle
    provider: Optional[LLMProvider] = Field(
        None,
        description="Fournisseur LLM à utiliser (openai, anthropic, google). Si non spécifié, utilise la valeur par défaut."
    )
    model: Optional[str] = Field(
        None,
        description="Modèle spécifique à utiliser (ex: gpt-4o, claude-3-opus-20240229, gemini-pro). Si non spécifié, utilise le modèle par défaut du fournisseur."
    )
    
    # NOUVEAUX CHAMPS pour le contrôle avancé
    use_cache: bool = Field(
        True,
        description="Utiliser le cache Redis. Si False, force la régénération."
    )
    user_id_placeholder: str = Field(
        "?",
        description="Placeholder pour l'ID utilisateur dans la requête SQL générée"
    )
    
    # NOUVEAU CHAMP pour inclure les détails des vecteurs similaires
    include_similar_details: bool = Field(
        False,
        description="Inclure les détails complets des 5 vecteurs similaires trouvés dans la réponse"
    )
    
    @validator('query')
    def validate_query(cls, v):
        """Valide que la requête ne contient pas d'éléments potentiellement malveillants"""
        # Vérifier qu'il ne s'agit pas d'une injection SQL déguisée
        sql_patterns = [
            r';\s*DROP\s+TABLE',
            r';\s*DELETE\s+FROM',
            r';\s*INSERT\s+INTO',
            r';\s*UPDATE\s+.*\s+SET',
            r'UNION\s+SELECT',
            r'--',
            r'/\*.*\*/'
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("La requête contient des motifs SQL suspects")
        
        return v
    
    @validator('schema_path')
    def validate_schema_path(cls, v):
        """Valide que le chemin du schéma est sécurisé"""
        if v is not None:
            # Vérifier que le chemin ne contient pas de caractères dangereux
            if '..' in v or '~' in v:
                raise ValueError("Le chemin du schéma contient des caractères non autorisés")
            
            # Vérifier que le chemin mène à un fichier SQL ou MD
            if not (v.endswith('.sql') or v.endswith('.md')):
                raise ValueError("Le chemin doit pointer vers un fichier SQL ou MD")
        
        return v
    
    @validator('model')
    def validate_model(cls, v, values):
        """Valide que le modèle est compatible avec le provider choisi"""
        if v is not None and 'provider' in values:
            provider = values['provider']
            
            # Modèles OpenAI
            openai_models = ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo']
            # Modèles Anthropic
            anthropic_models = ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307']
            # Modèles Google
            google_models = ['gemini-pro', 'gemini-1.5-pro', 'gemini-1.5-flash']
            
            if provider == LLMProvider.OPENAI and v not in openai_models:
                raise ValueError(f"Modèle '{v}' non compatible avec OpenAI. Modèles disponibles: {openai_models}")
            elif provider == LLMProvider.ANTHROPIC and v not in anthropic_models:
                raise ValueError(f"Modèle '{v}' non compatible avec Anthropic. Modèles disponibles: {anthropic_models}")
            elif provider == LLMProvider.GOOGLE and v not in google_models:
                raise ValueError(f"Modèle '{v}' non compatible avec Google. Modèles disponibles: {google_models}")
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Liste des clients qui ont effectué plus de 5 commandes en 2023",
                "schema_path": None,
                "validate": True,
                "explain": True,
                "provider": "openai",
                "model": "gpt-4o",
                "use_cache": True,
                "user_id_placeholder": "?",
                "include_similar_details": True
            }
        }
        # Permet d'utiliser 'validate' dans la requête JSON tout en évitant le conflit
        populate_by_name = True


class SQLTranslationResponse(BaseModel):
    """
    Modèle Pydantic pour la réponse de traduction.
    Définit la structure des données de sortie.
    """
    query: str = Field(
        ..., 
        description="Requête originale en langage naturel"
    )
    sql: Optional[str] = Field(
        None, 
        description="Requête SQL générée"
    )
    valid: Optional[bool] = Field(
        None, 
        description="Indique si la requête SQL est valide"
    )
    validation_message: Optional[str] = Field(
        None, 
        description="Message de validation"
    )
    explanation: Optional[str] = Field(
        None, 
        description="Explication de la requête SQL en langage naturel"
    )
    is_exact_match: bool = Field(
        False, 
        description="Indique si la requête a été trouvée dans la base de connaissances"
    )
    status: str = Field(
        ..., 
        description="Statut de la traduction (success, warning ou error)"
    )
    processing_time: Optional[float] = Field(
        None,
        description="Temps de traitement en secondes"
    )
    similar_queries: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Liste simplifiée des requêtes similaires trouvées (rétrocompatibilité)"
    )
    
    # NOUVEAU CHAMP : Détails complets des vecteurs similaires
    similar_queries_details: Optional[List[SimilarQueryDetail]] = Field(
        None,
        description="Détails complets des 5 vecteurs similaires trouvés (texte_complet + requete + score + id)"
    )
    
    # NOUVEAUX CHAMPS pour les informations du framework et LLM
    framework_compliant: Optional[bool] = Field(
        None,
        description="Indique si la requête respecte le framework obligatoire"
    )
    framework_details: Optional[Dict[str, Any]] = Field(
        None,
        description="Détails sur la conformité au framework (debug)"
    )
    from_cache: Optional[bool] = Field(
        None,
        description="Indique si le résultat provient du cache Redis"
    )
    provider: Optional[str] = Field(
        None,
        description="Fournisseur LLM utilisé pour générer la requête"
    )
    model: Optional[str] = Field(
        None,
        description="Modèle LLM spécifique utilisé"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Liste des clients qui ont effectué plus de 5 commandes en 2023",
                "sql": "SELECT c.nom, c.prenom, COUNT(cmd.id) as nb_commandes FROM clients c JOIN commandes cmd ON c.id = cmd.client_id WHERE YEAR(cmd.date) = 2023 GROUP BY c.id HAVING COUNT(cmd.id) > 5;",
                "valid": True,
                "validation_message": "La requête SQL correspond bien à votre demande et est compatible avec le schéma.",
                "explanation": "Cette requête recherche les clients ayant passé plus de 5 commandes en 2023, en affichant leur nom et prénom.",
                "is_exact_match": False,
                "status": "success",
                "processing_time": 2.34,
                "similar_queries": None,
                "similar_queries_details": [
                    {
                        "score": 0.89,
                        "texte_complet": "Liste des employés en CDI embauchés en 2023",
                        "requete": "SELECT f.NOM, f.PRENOM FROM FACTS f JOIN DEPOT d ON f.ID_NUMDEPOT = d.ID WHERE d.ID_USER = ? AND f.NATURE_CONTRAT = '01';",
                        "id": "vec_123456"
                    }
                ],
                "framework_compliant": True,
                "framework_details": None,
                "from_cache": False,
                "provider": "openai",
                "model": "gpt-4o"
            }
        }


class HealthCheckResponse(BaseModel):
    """
    Modèle Pydantic pour la réponse du endpoint de vérification de santé.
    """
    status: str = Field(..., description="Statut du service")
    version: str = Field(..., description="Version de l'API")
    services: Dict[str, Dict[str, Any]] = Field(
        ..., 
        description="État des services dépendants"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "version": "1.0.0",
                "services": {
                    "pinecone": {"status": "ok"},
                    "llm": {
                        "status": "ok",
                        "default_provider": "openai",
                        "providers": {
                            "openai": {"status": "ok", "model": "gpt-4o"},
                            "anthropic": {"status": "ok", "model": "claude-3-opus-20240229"},
                            "google": {"status": "not_configured"}
                        }
                    },
                    "embedding": {"status": "ok"},
                    "redis": {"status": "ok"}
                }
            }
        }


class LLMRequest(BaseModel):
    """
    Modèle générique pour les requêtes envoyées à un service de LLM.
    """
    prompt: str = Field(..., description="Prompt à envoyer au modèle de langage")
    provider: LLMProvider = Field(
        default=LLMProvider.OPENAI, 
        description="Fournisseur du modèle de langage"
    )
    model: Optional[str] = Field(
        None, 
        description="Nom spécifique du modèle (si différent du modèle par défaut du fournisseur)"
    )
    temperature: Optional[float] = Field(
        None, 
        description="Température pour la génération", 
        ge=0.0, 
        le=1.0
    )
    max_tokens: Optional[int] = Field(
        None, 
        description="Nombre maximum de tokens à générer", 
        ge=1, 
        le=8192
    )


class LLMResponse(BaseModel):
    """
    Modèle générique pour les réponses des services de LLM.
    """
    content: str = Field(..., description="Contenu généré par le modèle")
    tokens_used: Optional[int] = Field(
        None, 
        description="Nombre de tokens utilisés"
    )
    provider: LLMProvider = Field(
        ..., 
        description="Fournisseur du modèle de langage"
    )
    model: str = Field(..., description="Modèle utilisé")
    processing_time: Optional[float] = Field(
        None, 
        description="Temps de traitement"
    )


class SQLFrameworkValidationRequest(BaseModel):
    """
    Modèle pour la validation du framework d'une requête SQL.
    """
    sql_query: str = Field(
        ...,
        description="Requête SQL à valider",
        min_length=1,
        max_length=10000
    )
    user_id_placeholder: str = Field(
        "?",
        description="Placeholder pour l'ID utilisateur"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "sql_query": "SELECT f.NOM, f.PRENOM FROM FACTS f JOIN DEPOT d ON f.ID_NUMDEPOT = d.ID WHERE d.ID_USER = ?;",
                "user_id_placeholder": "?"
            }
        }


class SQLFrameworkValidationResponse(BaseModel):
    """
    Modèle pour la réponse de validation du framework.
    """
    sql_query: str = Field(..., description="Requête SQL validée")
    framework_compliant: bool = Field(..., description="Conforme au framework")
    message: str = Field(..., description="Message explicatif")
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Détails de la validation"
    )
    corrected_query: Optional[str] = Field(
        None,
        description="Requête corrigée si non conforme"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "sql_query": "SELECT f.NOM, f.PRENOM FROM FACTS f JOIN DEPOT d ON f.ID_NUMDEPOT = d.ID WHERE d.ID_USER = ?;",
                "framework_compliant": True,
                "message": "Requête conforme au framework obligatoire",
                "details": {
                    "has_user_filter": True,
                    "has_depot_table": True,
                    "has_hashtags": False
                },
                "corrected_query": None
            }
        }


class AvailableModelsResponse(BaseModel):
    """
    Modèle pour la réponse de la liste des modèles disponibles.
    """
    models: List[Dict[str, str]] = Field(
        ...,
        description="Liste des modèles disponibles par provider"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "models": [
                    {"provider": "openai", "id": "gpt-4o", "name": "GPT-4o"},
                    {"provider": "openai", "id": "gpt-4-turbo", "name": "GPT-4 Turbo"},
                    {"provider": "anthropic", "id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
                    {"provider": "google", "id": "gemini-pro", "name": "Gemini Pro"}
                ]
            }
        }