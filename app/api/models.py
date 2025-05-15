from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
import re


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
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Liste des clients qui ont effectué plus de 5 commandes en 2023",
                "schema_path": None,
                "validate": True,
                "explain": True
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
        description="Liste des requêtes similaires trouvées (si demandé)"
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
                "similar_queries": None
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
                    "openai": {"status": "ok"},
                    "embedding": {"status": "ok"},
                    "redis": {"status": "ok"}
                }
            }
        }