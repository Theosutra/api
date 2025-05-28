"""
Service de validation unifié pour l'API NL2SQL.

Ce service centralise toutes les validations (syntaxe, sécurité, framework, sémantique)
en remplaçant les validateurs dispersés dans le code.

Author: Datasulting
Version: 2.0.0 - CORRIGÉ avec support du contexte
"""

import logging
import re
from typing import Dict, Any, Optional, Tuple, List
from app.config import get_settings
from app.core.exceptions import ValidationError, FrameworkError
from app.core.llm_service import LLMService

# Import du gestionnaire de prompts avec fallback
try:
    from app.prompts.prompt_manager import get_prompt_manager
    PROMPTS_AVAILABLE = True
except ImportError:
    PROMPTS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ValidationService:
    """
    Service centralisé pour toutes les validations de l'application.
    
    Unifie et remplace:
    - app/utils/validators.py
    - app/utils/sql_validator.py 
    - app/utils/simple_framework_check.py
    
    Fonctionnalités:
    - Validation syntaxique SQL
    - Validation de sécurité (opérations destructives)
    - Validation du framework obligatoire
    - Validation sémantique via LLM
    - Correction automatique
    - Support des prompts Jinja2
    """
    
    def __init__(self, config=None):
        """
        Initialise le service de validation.
        
        Args:
            config: Configuration de l'application (utilise get_settings() si None)
        """
        self.config = config or get_settings()
        
        # Gestionnaire de prompts Jinja2 avec fallback
        if PROMPTS_AVAILABLE:
            try:
                self.prompt_manager = get_prompt_manager()
                logger.debug("PromptManager initialisé pour ValidationService")
            except Exception as e:
                logger.warning(f"Erreur initialisation PromptManager: {e}")
                self.prompt_manager = None
        else:
            self.prompt_manager = None
        
        # Patterns de validation réutilisables
        self.forbidden_operations = [
            r'^\s*DELETE\s+',
            r'^\s*DROP\s+',
            r'^\s*TRUNCATE\s+',
            r'^\s*ALTER\s+',
            r'^\s*UPDATE\s+',
            r'^\s*INSERT\s+',
            r'^\s*CREATE\s+',
            r'EXECUTE\s+',
            r'EXEC\s+'
        ]
        
        # Patterns de framework
        self.framework_patterns = {
            'user_filter': r'\b\w+\.ID_USER\s*=\s*\?',
            'depot_table': r'\bDEPOT\s+\w+',
            'hashtags': r'#\w+#',
            'join_depot': r'\bJOIN\s+DEPOT\b'
        }
        
        # Patterns SQL suspects
        self.injection_patterns = [
            r';\s*DROP\s+',
            r';\s*DELETE\s+',
            r';\s*UPDATE\s+',
            r';\s*INSERT\s+',
            r';\s*ALTER\s+',
            r'UNION\s+SELECT',
            r'--(?!\s*#)',  # Commentaires SQL mais pas hashtags
            r'/\*.*\*/'
        ]
    
    # ==========================================================================
    # VALIDATION SYNTAXIQUE
    # ==========================================================================
    
    def validate_sql_syntax(self, sql_query: str) -> Tuple[bool, Optional[str]]:
        """
        Validation syntaxique basique d'une requête SQL.
        
        Args:
            sql_query: Requête SQL à valider
            
        Returns:
            Tuple (is_valid, error_message)
            
        Raises:
            ValidationError: Si les paramètres sont invalides
        """
        if not sql_query or not isinstance(sql_query, str):
            raise ValidationError("sql_query doit être une chaîne non vide", "sql_query", sql_query)
        
        sql_query = sql_query.strip()
        
        try:
            # Vérifier les mots-clés SQL de base
            basic_keywords = [
                'SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING', 'JOIN',
                'INNER JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'OUTER JOIN', 'UNION',
                'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TRUNCATE'
            ]
            
            has_keyword = any(
                re.search(r'\b' + keyword.replace(' ', r'\s+') + r'\b', sql_query, re.IGNORECASE)
                for keyword in basic_keywords
            )
            
            if not has_keyword:
                return False, "La requête ne contient aucun mot-clé SQL standard"
            
            # Vérifier l'équilibre des parenthèses
            if sql_query.count('(') != sql_query.count(')'):
                return False, "Les parenthèses ne sont pas équilibrées"
            
            # Vérifier les guillemets
            quotes_checks = [
                ("'", "guillemets simples (')"),
                ('"', 'guillemets doubles (")'),
                ('`', 'backticks (`)')
            ]
            
            for quote_char, quote_name in quotes_checks:
                if sql_query.count(quote_char) % 2 != 0:
                    return False, f"Les {quote_name} ne sont pas équilibrés"
            
            # Vérifier si la requête commence par un mot-clé SQL valide
            first_word = sql_query.split()[0].upper() if sql_query.split() else ""
            valid_first_words = [
                'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 
                'TRUNCATE', 'WITH', 'EXPLAIN', 'DESCRIBE', 'SHOW'
            ]
            
            if first_word not in valid_first_words:
                return False, f"La requête commence par '{first_word}', qui n'est pas un mot-clé SQL standard"
            
            return True, None
        
        except Exception as e:
            logger.error(f"Erreur lors de la validation syntaxique: {e}")
            raise ValidationError(f"Erreur lors de la validation syntaxique: {e}", "syntax_validation", sql_query)
    
    # ==========================================================================
    # VALIDATION DE SÉCURITÉ
    # ==========================================================================
    
    def validate_security(self, sql_query: str) -> Tuple[bool, str]:
        """
        Validation de sécurité (opérations destructives et injections).
        
        Args:
            sql_query: Requête SQL à valider
            
        Returns:
            Tuple (is_safe, message)
            
        Raises:
            ValidationError: Si les paramètres sont invalides
        """
        if not sql_query or not isinstance(sql_query, str):
            raise ValidationError("sql_query doit être une chaîne non vide", "sql_query", sql_query)
        
        try:
            # 1. Vérifier les opérations destructives
            is_destructive, destructive_msg = self._check_destructive_operations(sql_query)
            if is_destructive:
                return False, destructive_msg
            
            # 2. Vérifier les injections SQL
            is_injection, injection_msg = self._check_sql_injection(sql_query)
            if is_injection:
                return False, injection_msg
            
            return True, "Requête sécurisée"
        
        except Exception as e:
            logger.error(f"Erreur lors de la validation de sécurité: {e}")
            raise ValidationError(f"Erreur lors de la validation de sécurité: {e}", "security_validation", sql_query)
    
    def _check_destructive_operations(self, sql_query: str) -> Tuple[bool, str]:
        """Vérifie les opérations destructives."""
        normalized_query = sql_query.upper()
        
        destructive_messages = {
            r'^\s*DELETE\s+': "Les opérations DELETE ne sont pas autorisées",
            r'^\s*DROP\s+': "Les opérations DROP ne sont pas autorisées", 
            r'^\s*TRUNCATE\s+': "Les opérations TRUNCATE ne sont pas autorisées",
            r'^\s*ALTER\s+': "Les opérations ALTER ne sont pas autorisées",
            r'^\s*UPDATE\s+': "Les opérations UPDATE ne sont pas autorisées",
            r'^\s*INSERT\s+': "Les opérations INSERT ne sont pas autorisées",
            r'^\s*CREATE\s+': "Les opérations CREATE ne sont pas autorisées",
            r'EXECUTE\s+': "L'exécution de procédures stockées n'est pas autorisée",
            r'EXEC\s+': "L'exécution de procédures stockées n'est pas autorisée"
        }
        
        for pattern, message in destructive_messages.items():
            if re.search(pattern, normalized_query):
                return True, message
        
        return False, "Aucune opération destructive détectée"
    
    def _check_sql_injection(self, sql_query: str) -> Tuple[bool, str]:
        """Vérifie les patterns d'injection SQL."""
        for pattern in self.injection_patterns:
            if re.search(pattern, sql_query, re.IGNORECASE):
                return True, f"Pattern d'injection SQL détecté: {pattern}"
        
        return False, "Aucun pattern d'injection détecté"
    
    # ==========================================================================
    # VALIDATION DU FRAMEWORK
    # ==========================================================================
    
    def validate_framework(self, sql_query: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validation complète du framework obligatoire.
        
        Args:
            sql_query: Requête SQL à valider
            
        Returns:
            Tuple (is_compliant, message, details)
            
        Raises:
            ValidationError: Si les paramètres sont invalides
        """
        if not sql_query or not isinstance(sql_query, str):
            raise ValidationError("sql_query doit être une chaîne non vide", "sql_query", sql_query)
        
        sql_query = sql_query.strip()
        
        try:
            # Analyser chaque élément du framework
            elements = self._analyze_framework_elements(sql_query)
            
            # Vérifier les éléments obligatoires
            missing_elements = []
            
            if not elements["has_user_filter"]:
                missing_elements.append("filtre WHERE [alias].ID_USER = ?")
            
            if not elements["has_depot_table"]:
                missing_elements.append("table DEPOT")
            
            if not elements["has_hashtags"]:
                missing_elements.append("hashtags (#DEPOT_alias#)")
            
            if not elements["is_select_query"]:
                missing_elements.append("requête SELECT uniquement")
            
            # Déterminer la conformité
            is_compliant = len(missing_elements) == 0
            
            if is_compliant:
                message = "Requête conforme au framework obligatoire"
            else:
                message = f"Éléments manquants: {', '.join(missing_elements)}"
            
            return is_compliant, message, elements
        
        except Exception as e:
            logger.error(f"Erreur lors de la validation du framework: {e}")
            raise ValidationError(f"Erreur lors de la validation du framework: {e}", "framework_validation", sql_query)
    
    def _analyze_framework_elements(self, sql_query: str) -> Dict[str, Any]:
        """Analyse détaillée des éléments du framework."""
        elements = {
            "has_user_filter": bool(re.search(self.framework_patterns['user_filter'], sql_query, re.IGNORECASE)),
            "has_depot_table": bool(re.search(self.framework_patterns['depot_table'], sql_query, re.IGNORECASE)),
            "has_hashtags": bool(re.search(self.framework_patterns['hashtags'], sql_query)),
            "is_select_query": sql_query.upper().startswith('SELECT'),
            "has_where_clause": bool(re.search(r'\bWHERE\b', sql_query, re.IGNORECASE)),
            "has_join_depot": bool(re.search(self.framework_patterns['join_depot'], sql_query, re.IGNORECASE))
        }
        
        # Extraire les alias
        depot_aliases = re.findall(r'\bDEPOT\s+(\w+)', sql_query, re.IGNORECASE)
        facts_aliases = re.findall(r'\bFACTS\s+(\w+)', sql_query, re.IGNORECASE)
        
        elements.update({
            "depot_aliases": depot_aliases,
            "facts_aliases": facts_aliases,
            "has_depot_alias": len(depot_aliases) > 0,
            "has_facts_alias": len(facts_aliases) > 0
        })
        
        # Analyser les hashtags
        hashtags = re.findall(r'#(\w+)#', sql_query)
        elements.update({
            "found_hashtags": hashtags,
            "has_depot_hashtag": any(tag.startswith('DEPOT_') for tag in hashtags),
            "has_facts_hashtag": any(tag.startswith('FACTS_') for tag in hashtags),
            "has_periode_hashtag": 'PERIODE' in hashtags
        })
        
        return elements
    
    def fix_framework_compliance(self, sql_query: str) -> str:
        """
        Corrige automatiquement une requête pour respecter le framework.
        
        Args:
            sql_query: Requête SQL à corriger
            
        Returns:
            Requête SQL corrigée
            
        Raises:
            FrameworkError: Si la correction automatique échoue
        """
        if not sql_query or not isinstance(sql_query, str):
            raise ValidationError("sql_query doit être une chaîne non vide", "sql_query", sql_query)
        
        modified_query = sql_query.strip()
        
        try:
            # 1. Ajouter le filtre ID_USER si manquant
            if not re.search(self.framework_patterns['user_filter'], modified_query, re.IGNORECASE):
                modified_query = self._add_user_filter(modified_query)
            
            # 2. Ajouter les hashtags si manquants
            if not re.search(self.framework_patterns['hashtags'], modified_query):
                modified_query = self._add_hashtags(modified_query)
            
            # 3. Valider le résultat
            is_compliant, _, _ = self.validate_framework(modified_query)
            if not is_compliant:
                raise FrameworkError("Correction automatique échouée", modified_query)
            
            return modified_query
        
        except FrameworkError:
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la correction du framework: {e}")
            raise FrameworkError(f"Erreur lors de la correction automatique: {e}", sql_query)
    
    def _add_user_filter(self, sql_query: str) -> str:
        """Ajoute le filtre ID_USER manquant."""
        depot_match = re.search(r'\bDEPOT\s+(\w+)', sql_query, re.IGNORECASE)
        if not depot_match:
            raise FrameworkError("Impossible d'ajouter le filtre ID_USER: table DEPOT non trouvée", sql_query)
        
        depot_alias = depot_match.group(1)
        user_filter = f"{depot_alias}.ID_USER = ?"
        
        if ' WHERE ' in sql_query.upper():
            # Ajouter au début de la clause WHERE existante
            sql_query = re.sub(
                r'(\bWHERE\s+)', 
                f'\\1{user_filter} AND ', 
                sql_query, 
                flags=re.IGNORECASE
            )
        else:
            # Ajouter une nouvelle clause WHERE
            insert_patterns = [
                (r'(\s+GROUP\s+BY)', f' WHERE {user_filter}\\1'),
                (r'(\s+ORDER\s+BY)', f' WHERE {user_filter}\\1'),
                (r'(\s*;?\s*$)', f' WHERE {user_filter}\\1')
            ]
            
            for pattern, replacement in insert_patterns:
                if re.search(pattern, sql_query, re.IGNORECASE):
                    sql_query = re.sub(pattern, replacement, sql_query, flags=re.IGNORECASE)
                    break
        
        return sql_query
    
    def _add_hashtags(self, sql_query: str) -> str:
        """Ajoute les hashtags manquants."""
        hashtags = []
        
        # Hashtags basés sur les tables
        depot_match = re.search(r'\bDEPOT\s+(\w+)', sql_query, re.IGNORECASE)
        facts_match = re.search(r'\bFACTS\s+(\w+)', sql_query, re.IGNORECASE)
        
        if depot_match:
            hashtags.append(f"#DEPOT_{depot_match.group(1)}#")
        if facts_match:
            hashtags.append(f"#FACTS_{facts_match.group(1)}#")
        
        # Hashtag temporel si nécessaire
        if re.search(r'\bPERIODE\b|\bDATE\b|\bMOIS\b|\bANNEE\b', sql_query, re.IGNORECASE):
            hashtags.append("#PERIODE#")
        
        if not hashtags:
            raise FrameworkError("Impossible de déterminer les hashtags appropriés", sql_query)
        
        # Ajouter les hashtags à la fin
        hashtag_string = " " + " ".join(hashtags)
        if sql_query.rstrip().endswith(';'):
            sql_query = sql_query.rstrip()[:-1] + hashtag_string + ';'
        else:
            sql_query = sql_query + hashtag_string
        
        return sql_query
    
    # ==========================================================================
    # VALIDATION SÉMANTIQUE
    # ==========================================================================
    
    async def validate_semantics(
        self, 
        sql_query: str, 
        original_request: str, 
        schema: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None  # NOUVEAU PARAMÈTRE AJOUTÉ
    ) -> Tuple[bool, str]:
        """
        Validation sémantique via LLM avec prompts Jinja2.
        
        Args:
            sql_query: Requête SQL à valider
            original_request: Demande originale en langage naturel
            schema: Schéma de la base de données
            provider: Fournisseur LLM
            model: Modèle LLM
            context: Contexte de validation (mode strict, etc.)  # NOUVEAU
            
        Returns:
            Tuple (is_valid, message)
        """
        if not sql_query or not original_request:
            raise ValidationError("sql_query et original_request sont obligatoires")
        
        try:
            # Enrichir le contexte avec des informations de validation
            validation_context = context or {}
            validation_context.update({
                "strict_mode": True,
                "business_domain": "HR",
                "validation_level": "semantic"
            })
            
            return await LLMService.validate_sql_semantically(
                sql_query=sql_query,
                original_request=original_request,
                schema=schema,
                provider=provider,
                model=model,
                context=validation_context  # NOUVEAU PARAMÈTRE PASSÉ
            )
        except Exception as e:
            logger.error(f"Erreur lors de la validation sémantique: {e}")
            # Ne pas faire échouer la validation pour une erreur LLM
            return True, "Validation sémantique ignorée due à une erreur LLM"
    
    # ==========================================================================
    # VALIDATION COMPLÈTE
    # ==========================================================================
    
    async def validate_complete(
        self, 
        sql_query: str, 
        original_request: str = None,
        schema: str = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        auto_fix: bool = True
    ) -> Dict[str, Any]:
        """
        Validation complète d'une requête SQL (syntaxe + sécurité + framework + sémantique).
        
        Args:
            sql_query: Requête SQL à valider
            original_request: Demande originale (pour validation sémantique)
            schema: Schéma de la base de données (pour validation sémantique)
            provider: Fournisseur LLM
            model: Modèle LLM
            auto_fix: Tenter une correction automatique si non conforme
            
        Returns:
            Dictionnaire avec tous les résultats de validation
        """
        result = {
            "original_query": sql_query,
            "final_query": sql_query,
            "valid": False,
            "message": "",
            "details": {},
            "corrected": False,
            "auto_fix_applied": False
        }
        
        try:
            # 1. Validation syntaxique
            syntax_valid, syntax_msg = self.validate_sql_syntax(sql_query)
            result["details"]["syntax"] = {
                "valid": syntax_valid,
                "message": syntax_msg
            }
            
            if not syntax_valid:
                result["message"] = f"Erreur de syntaxe: {syntax_msg}"
                return result
            
            # 2. Validation de sécurité
            security_safe, security_msg = self.validate_security(sql_query)
            result["details"]["security"] = {
                "safe": security_safe,
                "message": security_msg
            }
            
            if not security_safe:
                result["message"] = f"Erreur de sécurité: {security_msg}"
                return result
            
            # 3. Validation du framework
            framework_compliant, framework_msg, framework_details = self.validate_framework(sql_query)
            result["details"]["framework"] = {
                "compliant": framework_compliant,
                "message": framework_msg,
                "elements": framework_details
            }
            
            # 4. Correction automatique si nécessaire
            if not framework_compliant and auto_fix:
                try:
                    corrected_query = self.fix_framework_compliance(sql_query)
                    result["final_query"] = corrected_query
                    result["corrected"] = True
                    result["auto_fix_applied"] = True
                    
                    # Re-valider la requête corrigée
                    framework_compliant, framework_msg, framework_details = self.validate_framework(corrected_query)
                    result["details"]["framework"]["compliant"] = framework_compliant
                    result["details"]["framework"]["message"] = f"Corrigé automatiquement: {framework_msg}"
                    
                except FrameworkError as e:
                    result["message"] = f"Erreur de framework (correction échouée): {str(e)}"
                    return result
            
            if not framework_compliant:
                result["message"] = f"Erreur de framework: {framework_msg}"
                return result
            
            # 5. Validation sémantique (optionnelle)
            if original_request and schema:
                semantic_valid, semantic_msg = await self.validate_semantics(
                    result["final_query"], original_request, schema, provider, model
                )
                result["details"]["semantic"] = {
                    "valid": semantic_valid,
                    "message": semantic_msg
                }
                
                if not semantic_valid:
                    result["message"] = f"Erreur sémantique: {semantic_msg}"
                    return result
            
            # Toutes les validations passées
            result["valid"] = True
            result["message"] = "Validation complète réussie"
            
            return result
        
        except Exception as e:
            logger.error(f"Erreur lors de la validation complète: {e}")
            result["message"] = f"Erreur lors de la validation: {str(e)}"
            return result
    
    # ==========================================================================
    # VALIDATION DES ENTRÉES UTILISATEUR
    # ==========================================================================
    
    def validate_user_input(self, user_query: str) -> Tuple[bool, str]:
        """
        Valide l'entrée utilisateur en langage naturel.
        
        Args:
            user_query: Question de l'utilisateur
            
        Returns:
            Tuple (is_valid, message)
        """
        if not user_query or not isinstance(user_query, str):
            return False, "La requête doit être une chaîne non vide"
        
        user_query = user_query.strip()
        
        if len(user_query) < 3:
            return False, "La requête doit contenir au moins 3 caractères"
        
        if len(user_query) > 1000:
            return False, "La requête ne peut pas dépasser 1000 caractères"
        
        # Vérifier les caractères suspects
        suspicious_patterns = [
            r'<script',
            r'javascript:',
            r'data:',
            r'vbscript:',
            r'on\w+\s*='
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, user_query, re.IGNORECASE):
                return False, "La requête contient des caractères suspects"
        
        return True, "Entrée utilisateur valide"
    
    def sanitize_user_input(self, user_query: str) -> str:
        """
        Nettoie l'entrée utilisateur.
        
        Args:
            user_query: Question de l'utilisateur
            
        Returns:
            Question nettoyée
        """
        if not user_query:
            return ""
        
        # Supprimer les caractères de contrôle
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', user_query)
        
        # Normaliser les espaces
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        # Limiter la longueur
        if len(sanitized) > 1000:
            sanitized = sanitized[:1000]
        
        return sanitized.strip()
    
    # ==========================================================================
    # UTILITAIRES
    # ==========================================================================
    
    def get_validation_suggestions(self, sql_query: str) -> List[str]:
        """
        Génère des suggestions pour corriger une requête non conforme.
        
        Args:
            sql_query: Requête SQL à analyser
            
        Returns:
            Liste des suggestions
        """
        try:
            suggestions = []
            _, _, elements = self.validate_framework(sql_query)
            
            if not elements["is_select_query"]:
                suggestions.append("Utilisez uniquement des requêtes SELECT")
            
            if not elements["has_depot_table"]:
                suggestions.append("Ajoutez la table DEPOT avec un alias (ex: DEPOT a)")
            
            if not elements["has_user_filter"]:
                if elements["has_depot_alias"]:
                    alias = elements["depot_aliases"][0]
                    suggestions.append(f"Ajoutez le filtre WHERE {alias}.ID_USER = ?")
                else:
                    suggestions.append("Ajoutez le filtre WHERE [alias_depot].ID_USER = ?")
            
            if not elements["has_hashtags"]:
                hashtag_suggestions = []
                if elements["has_depot_alias"]:
                    hashtag_suggestions.append(f"#DEPOT_{elements['depot_aliases'][0]}#")
                if elements["has_facts_alias"]:
                    hashtag_suggestions.append(f"#FACTS_{elements['facts_aliases'][0]}#")
                
                if hashtag_suggestions:
                    suggestions.append(f"Ajoutez les hashtags: {' '.join(hashtag_suggestions)}")
                else:
                    suggestions.append("Ajoutez les hashtags appropriés (#DEPOT_alias# #FACTS_alias#)")
            
            return suggestions
        
        except Exception as e:
            logger.error(f"Erreur lors de la génération des suggestions: {e}")
            return ["Erreur lors de l'analyse de la requête"]