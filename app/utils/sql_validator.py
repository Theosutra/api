 #Version simplifiée avec commentaires autorisés
import logging
import re
from typing import Tuple, Dict, Any, List, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class SQLValidator:
    """
    Classe simplifiée pour valider les requêtes SQL.
    Se concentre sur la détection d'opérations dangereuses/destructives.
    """
    
    def __init__(self, schema_content: str = None, schema_path: str = None):
        """
        Initialise le validateur SQL simplifié.
        
        Args:
            schema_content: Contenu du schéma (non utilisé dans cette version simplifiée)
            schema_path: Chemin vers le fichier de schéma (non utilisé dans cette version simplifiée)
        """
        self.schema_path = schema_path
    
    async def load_and_parse_schema(self):
        """
        Méthode maintenue pour compatibilité avec le code existant.
        Ne fait rien dans cette version simplifiée.
        """
        pass
    
    def check_for_sql_injection(self, sql_query: str) -> Tuple[bool, str]:
        """
        Vérifie si la requête contient des motifs d'injection SQL.
        Autorise les commentaires SQL légitimes.
        
        Args:
            sql_query: Requête SQL à vérifier
            
        Returns:
            Tuple (safe, message) où:
            - safe: booléen indiquant si la requête est sûre
            - message: message explicatif
        """
        # Motifs suspects d'injection SQL
        suspicious_patterns = [
            r';\s*DROP\s+',
            r';\s*DELETE\s+',
            r';\s*UPDATE\s+',
            r';\s*INSERT\s+',
            r';\s*ALTER\s+',
            r'UNION\s+SELECT',
            r'--'  # Commentaires de style -- peuvent être suspects
            # Nous retirons '/\*.*\*/' qui correspond aux commentaires SQL légitimes
        ]
        
        # Vérifier chaque motif
        for pattern in suspicious_patterns:
            if re.search(pattern, sql_query, re.IGNORECASE):
                return False, f"Possible injection SQL détectée: motif '{pattern}' trouvé"
        
        return True, "Aucun motif d'injection SQL détecté"
    
    def check_destructive_operations(self, sql_query: str) -> Tuple[bool, str]:
        """
        Vérifie si la requête contient des opérations destructives ou à haut risque.
        
        Args:
            sql_query: Requête SQL à vérifier
            
        Returns:
            Tuple (is_destructive, message) où:
            - is_destructive: booléen indiquant si la requête est destructive
            - message: message explicatif
        """
        # Si le mode lecture seule n'est pas activé, autoriser les opérations d'écriture
        if hasattr(settings, 'SQL_READ_ONLY') and not settings.SQL_READ_ONLY:
            return False, "Opérations d'écriture autorisées"
            
        # Normaliser la requête pour la recherche
        normalized_query = sql_query.upper()
        
        # Liste des opérations destructives ou à haut risque
        destructive_patterns = [
            (r'^\s*DELETE\s+', "Les opérations DELETE ne sont pas autorisées pour des raisons de sécurité"),
            (r'^\s*DROP\s+', "Les opérations DROP ne sont pas autorisées pour des raisons de sécurité"),
            (r'^\s*TRUNCATE\s+', "Les opérations TRUNCATE ne sont pas autorisées pour des raisons de sécurité"),
            (r'^\s*ALTER\s+', "Les opérations ALTER ne sont pas autorisées pour des raisons de sécurité"),
            (r'^\s*UPDATE\s+', "Les opérations UPDATE ne sont pas autorisées pour des raisons de sécurité"),
            (r'^\s*INSERT\s+', "Les opérations INSERT ne sont pas autorisées pour des raisons de sécurité"),
            (r'^\s*CREATE\s+', "Les opérations CREATE ne sont pas autorisées pour des raisons de sécurité"),
            (r'EXECUTE\s+', "L'exécution de procédures stockées n'est pas autorisée pour des raisons de sécurité"),
            (r'EXEC\s+', "L'exécution de procédures stockées n'est pas autorisée pour des raisons de sécurité")
        ]
        
        for pattern, message in destructive_patterns:
            if re.search(pattern, normalized_query):
                logger.warning(f"Opération destructive détectée: {pattern.strip()}")
                return True, message
        
        return False, "Aucune opération destructive détectée"
    
    async def validate_sql_query(self, sql_query: str, original_request: str) -> Dict[str, Any]:
        """
        Méthode simplifiée pour valider une requête SQL.
        Se concentre uniquement sur la sécurité.
        
        Args:
            sql_query: Requête SQL à valider
            original_request: Requête en langage naturel (non utilisée dans cette version simplifiée)
            
        Returns:
            Dictionnaire avec les résultats de validation
        """
        # Vérifier si la requête contient des opérations destructives
        is_destructive, destructive_message = self.check_destructive_operations(sql_query)
        
        if is_destructive:
            return {
                "valid": False,
                "message": destructive_message,
                "details": {
                    "syntax": {"valid": True, "message": "Syntaxe correcte, mais opération non autorisée"},
                    "injection": {"safe": False, "message": destructive_message},
                    "schema": {"valid": False, "message": "Les opérations destructives ne sont pas autorisées", "warnings": []},
                    "intention": {"valid": False}
                }
            }
        
        # Vérifier les injections SQL
        injection_safe, injection_message = self.check_for_sql_injection(sql_query)
        
        if not injection_safe:
            return {
                "valid": False,
                "message": injection_message,
                "details": {
                    "syntax": {"valid": True, "message": "Syntaxe correcte, mais motifs d'injection détectés"},
                    "injection": {"safe": False, "message": injection_message},
                    "schema": {"valid": True, "message": "Validation du schéma ignorée", "warnings": []},
                    "intention": {"valid": True}
                }
            }
        
        # Si aucun problème n'est détecté, considérer la requête comme valide
        return {
            "valid": True,
            "message": "La requête SQL est sécurisée",
            "details": {
                "syntax": {"valid": True, "message": "Validation de syntaxe ignorée"},
                "injection": {"safe": True, "message": injection_message},
                "schema": {"valid": True, "message": "Validation du schéma ignorée", "warnings": []},
                "intention": {"valid": True, "message": "Validation d'intention ignorée"}
            }
        }