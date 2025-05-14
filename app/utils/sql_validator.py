# app/utils/sql_validator.py
import logging
import re
from typing import Tuple, Dict, Any, List, Optional
import sqlglot
import sqlglot.expressions as exp
from sqlglot import parse_one, ParseError
from app.utils.schema_loader import load_schema
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class SQLValidator:
    """
    Classe pour valider les requêtes SQL de manière robuste.
    Utilise SQLGlot pour le parsing et la validation syntaxique.
    """
    
    def __init__(self, schema_content: str = None, schema_path: str = None):
        """
        Initialise le validateur SQL.
        
        Args:
            schema_content: Contenu du schéma SQL (prioritaire si fourni)
            schema_path: Chemin vers le fichier de schéma SQL
        """
        self.schema_content = schema_content
        self.schema_path = schema_path
        self.table_columns = {}  # Mapping des tables et colonnes
        self.tables = set()  # Ensemble des tables disponibles
        
        # Analyser le schéma SQL si disponible
        if self.schema_content:
            self._parse_schema(self.schema_content)
        
    async def load_and_parse_schema(self):
        """Charge et analyse le schéma SQL de manière asynchrone"""
        if self.schema_path and not self.schema_content:
            self.schema_content = await load_schema(self.schema_path)
            self._parse_schema(self.schema_content)
    
    def _parse_schema(self, schema_content: str):
        """
        Analyse le schéma SQL pour extraire les tables et colonnes.
        
        Args:
            schema_content: Contenu du schéma SQL
        """
        # Expressions régulières pour extraire les tables et colonnes
        create_table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"]?(\w+)[`"]?\s*\((.*?)\)'
        column_pattern = r'[`"]?(\w+)[`"]?\s+(\w+)'
        
        # Trouver toutes les définitions de tables
        for table_match in re.finditer(create_table_pattern, schema_content, re.IGNORECASE | re.DOTALL):
            table_name = table_match.group(1).lower()
            columns_def = table_match.group(2)
            
            self.tables.add(table_name)
            self.table_columns[table_name] = []
            
            # Extraire les définitions de colonnes
            for col_match in re.finditer(column_pattern, columns_def):
                column_name = col_match.group(1).lower()
                column_type = col_match.group(2).lower()
                self.table_columns[table_name].append({
                    "name": column_name,
                    "type": column_type
                })
        
        logger.info(f"Schéma analysé: {len(self.tables)} tables trouvées")
    
    def validate_syntax(self, sql_query: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Valide la syntaxe d'une requête SQL.
        
        Args:
            sql_query: Requête SQL à valider
            
        Returns:
            Tuple (valid, message, ast) où:
            - valid: booléen indiquant si la requête est syntaxiquement valide
            - message: message explicatif
            - ast: arbre syntaxique abstrait de la requête si valide, None sinon
        """
        try:
            # Nettoyer la requête
            sql_query = sql_query.strip()
            if sql_query.endswith(';'):
                sql_query = sql_query[:-1]
            
            # Parser la requête
            ast = parse_one(sql_query)
            
            return True, "Requête SQL syntaxiquement valide", ast
            
        except ParseError as e:
            logger.warning(f"Erreur de syntaxe SQL: {str(e)}")
            return False, f"Erreur de syntaxe SQL: {str(e)}", None
            
        except Exception as e:
            logger.error(f"Erreur lors de la validation SQL: {str(e)}")
            return False, f"Erreur lors de la validation: {str(e)}", None
    
    def validate_schema_compatibility(self, ast) -> Tuple[bool, str, List[str]]:
        """
        Valide la compatibilité de la requête avec le schéma.
        
        Args:
            ast: Arbre syntaxique abstrait de la requête
            
        Returns:
            Tuple (valid, message, warnings) où:
            - valid: booléen indiquant si la requête est compatible
            - message: message explicatif
            - warnings: liste des avertissements
        """
        if not ast:
            return False, "Impossible de valider la requête sans AST", []
        
        if not self.tables:
            return True, "Validation du schéma ignorée (schéma non disponible)", []
        
        warnings = []
        used_tables = set()
        used_columns = {}
        
        # Extraire les tables et colonnes utilisées dans la requête
        self._extract_tables_and_columns(ast, used_tables, used_columns)
        
        # Vérifier si toutes les tables existent
        invalid_tables = [t for t in used_tables if t.lower() not in self.tables]
        if invalid_tables:
            return False, f"Tables non trouvées dans le schéma: {', '.join(invalid_tables)}", warnings
        
        # Vérifier si toutes les colonnes existent
        for table, columns in used_columns.items():
            table_lower = table.lower()
            if table_lower in self.table_columns:
                valid_columns = [col["name"] for col in self.table_columns[table_lower]]
                invalid_columns = [c for c in columns if c.lower() not in valid_columns and c != '*']
                
                if invalid_columns:
                    warnings.append(f"Colonnes non trouvées dans '{table}': {', '.join(invalid_columns)}")
        
        if warnings:
            return True, "Requête compatible avec le schéma, mais avec des avertissements", warnings
            
        return True, "Requête entièrement compatible avec le schéma", []
    
    def _extract_tables_and_columns(self, node, used_tables, used_columns):
        """
        Extrait récursivement les tables et colonnes d'un AST.
        
        Args:
            node: Nœud de l'AST à analyser
            used_tables: Ensemble des tables utilisées (modifié par référence)
            used_columns: Dictionnaire des colonnes utilisées par table (modifié par référence)
        """
        if isinstance(node, exp.Table):
            table_name = node.name
            used_tables.add(table_name)
            
            # Initialiser l'entrée du dictionnaire pour cette table
            if table_name not in used_columns:
                used_columns[table_name] = set()
                
        elif isinstance(node, exp.Column):
            # Traiter les colonnes
            col_name = node.name
            
            # La table peut être définie dans la colonne ou plus haut dans l'arbre
            table_name = None
            if hasattr(node, 'table') and node.table:
                table_name = node.table
                used_tables.add(table_name)
                
                if table_name not in used_columns:
                    used_columns[table_name] = set()
                    
                used_columns[table_name].add(col_name)
        
        # Parcourir récursivement tous les enfants
        if hasattr(node, 'expressions'):
            for child in node.expressions:
                self._extract_tables_and_columns(child, used_tables, used_columns)
    
    def check_for_sql_injection(self, sql_query: str) -> Tuple[bool, str]:
        """
        Vérifie si la requête contient des motifs d'injection SQL.
        
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
            r'--',
            r'/\*.*\*/'
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
    
    def validate_query_intention(self, sql_query: str, original_request: str) -> bool:
        """
        Vérifie simplement si la requête contient des mots clés pertinents.
        Cette méthode est basique et complémentaire à l'approche LLM.
        
        Args:
            sql_query: Requête SQL à valider
            original_request: Requête en langage naturel
            
        Returns:
            booléen indiquant si la requête semble correspondre à la demande
        """
        # Extraire les mots clés de la requête originale
        request_keywords = set(re.findall(r'\b\w+\b', original_request.lower()))
        
        # Extraire les tables et colonnes de la requête SQL
        syntax_valid, _, ast = self.validate_syntax(sql_query)
        if not syntax_valid or not ast:
            return False
        
        tables = set()
        columns = {}
        self._extract_tables_and_columns(ast, tables, columns)
        
        # Aplatir les colonnes
        flat_columns = set()
        for table_cols in columns.values():
            flat_columns.update(table_cols)
        
        # Vérifier si les mots clés de la requête se retrouvent dans les tables/colonnes
        sql_entities = set([t.lower() for t in tables]).union(set([c.lower() for c in flat_columns]))
        
        # Calculer l'intersection
        common_keywords = request_keywords.intersection(sql_entities)
        
        # Si au moins 1 mot clé est commun, on considère que la requête correspond
        return len(common_keywords) > 0
    
    async def validate_sql_query(self, sql_query: str, original_request: str) -> Dict[str, Any]:
        """
        Méthode principale pour valider une requête SQL.
        Combine toutes les validations.
        
        Args:
            sql_query: Requête SQL à valider
            original_request: Requête en langage naturel
            
        Returns:
            Dictionnaire avec les résultats de validation
        """
        # Vérifier d'abord si la requête est destructive (blocage immédiat)
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
        
        # S'assurer que le schéma est chargé
        await self.load_and_parse_schema()
        
        # Valider la syntaxe
        syntax_valid, syntax_message, ast = self.validate_syntax(sql_query)
        
        # Vérifier les injections SQL
        injection_safe, injection_message = self.check_for_sql_injection(sql_query)
        
        # Valider la compatibilité avec le schéma
        schema_valid, schema_message, warnings = (False, "Non vérifié (syntaxe invalide)", []) 
        if syntax_valid:
            schema_valid, schema_message, warnings = self.validate_schema_compatibility(ast)
        
        # Vérification basique de l'intention
        intention_valid = False
        if syntax_valid:
            intention_valid = self.validate_query_intention(sql_query, original_request)
        
        # Résultats combinés
        valid = syntax_valid and injection_safe and schema_valid and intention_valid
        
        # Prioriser les messages
        if not syntax_valid:
            primary_message = syntax_message
        elif not injection_safe:
            primary_message = injection_message
        elif not schema_valid:
            primary_message = schema_message
        elif not intention_valid:
            primary_message = "La requête SQL ne semble pas correspondre à la demande originale"
        else:
            primary_message = "Requête SQL valide et sécurisée"
        
        return {
            "valid": valid,
            "message": primary_message,
            "details": {
                "syntax": {"valid": syntax_valid, "message": syntax_message},
                "injection": {"safe": injection_safe, "message": injection_message},
                "schema": {"valid": schema_valid, "message": schema_message, "warnings": warnings},
                "intention": {"valid": intention_valid}
            }
        }