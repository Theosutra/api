"""
Gestionnaire de prompts centralisé avec Jinja2.

Ce module charge et rend les prompts depuis des templates Jinja2,
permettant une modularisation et personnalisation avancées.

Author: Datasulting
Version: 2.0.0
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template
from functools import lru_cache
import json

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Gestionnaire centralisé pour les prompts Jinja2.
    
    Fonctionnalités:
    - Chargement des templates depuis app/prompts/
    - Rendu avec variables dynamiques
    - Cache des templates pour les performances
    - Validation des paramètres requis
    - Support de contextes personnalisés
    """
    
    def __init__(self, templates_dir: str = "app/prompts"):
        """
        Initialise le gestionnaire de prompts.
        
        Args:
            templates_dir: Répertoire contenant les templates Jinja2
        """
        self.templates_dir = Path(templates_dir)
        
        # Configuration Jinja2 sécurisée
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        
        # Cache des templates compilés
        self._template_cache: Dict[str, Template] = {}
        
        # Vérifier que le répertoire existe
        if not self.templates_dir.exists():
            logger.warning(f"Répertoire de templates {self.templates_dir} introuvable")
        else:
            logger.info(f"PromptManager initialisé avec {self.templates_dir}")
    
    @lru_cache(maxsize=128)
    def get_template(self, template_name: str) -> Template:
        """
        Récupère un template compilé avec cache.
        
        Args:
            template_name: Nom du fichier template (ex: 'sql_generation.j2')
            
        Returns:
            Template Jinja2 compilé
            
        Raises:
            FileNotFoundError: Si le template n'existe pas
        """
        try:
            if template_name not in self._template_cache:
                self._template_cache[template_name] = self.env.get_template(template_name)
                logger.debug(f"Template {template_name} chargé et mis en cache")
            
            return self._template_cache[template_name]
        
        except Exception as e:
            logger.error(f"Erreur lors du chargement du template {template_name}: {e}")
            raise FileNotFoundError(f"Template {template_name} introuvable: {e}")
    
    def render_macro(self, template_name: str, macro_name: str, **kwargs) -> str:
        """
        Rend une macro spécifique d'un template.
        
        Args:
            template_name: Nom du fichier template
            macro_name: Nom de la macro à rendre
            **kwargs: Variables pour le rendu
            
        Returns:
            Prompt rendu
            
        Raises:
            ValueError: Si la macro n'existe pas
        """
        try:
            template = self.get_template(template_name)
            
            # Vérifier que la macro existe
            if macro_name not in template.module.__dict__:
                available_macros = [name for name in template.module.__dict__.keys() 
                                  if not name.startswith('_')]
                raise ValueError(
                    f"Macro '{macro_name}' introuvable dans {template_name}. "
                    f"Macros disponibles: {available_macros}"
                )
            
            # Rendre la macro
            macro = getattr(template.module, macro_name)
            rendered = macro(**kwargs)
            
            logger.debug(f"Macro {macro_name} rendue depuis {template_name}")
            return rendered.strip()
        
        except Exception as e:
            logger.error(f"Erreur lors du rendu de {macro_name} dans {template_name}: {e}")
            raise
    
    # ========================================================================
    # MÉTHODES SPÉCIALISÉES POUR LA GÉNÉRATION SQL
    # ========================================================================
    
    def get_system_message(self) -> str:
        """Récupère le message système pour la génération SQL."""
        return self.render_macro('sql_generation.j2', 'system_message')
    
    def get_sql_generation_prompt(
        self, 
        user_query: str, 
        schema: str,
        similar_queries: List[Dict[str, Any]] = None,
        context: Dict[str, Any] = None
    ) -> str:
        """
        Génère le prompt principal de création SQL.
        
        Args:
            user_query: Question en langage naturel
            schema: Schéma de la base de données
            similar_queries: Requêtes similaires trouvées
            context: Contexte additionnel (période, département, etc.)
            
        Returns:
            Prompt de génération SQL complet
        """
        return self.render_macro(
            'sql_generation.j2', 
            'generate_sql_prompt',
            user_query=user_query,
            schema=schema,
            similar_queries=similar_queries or [],
            context=context or {}
        )
    
    def get_relevance_check_prompt(self, user_query: str) -> str:
        """Génère le prompt de vérification de pertinence RH."""
        return self.render_macro(
            'sql_generation.j2',
            'check_relevance_prompt', 
            user_query=user_query
        )
    
    def get_explanation_prompt(
        self, 
        sql_query: str, 
        original_request: str,
        context: Dict[str, Any] = None
    ) -> str:
        """Génère le prompt d'explication SQL."""
        return self.render_macro(
            'sql_generation.j2',
            'explain_sql_prompt',
            sql_query=sql_query,
            original_request=original_request,
            context=context or {}
        )
    
    def get_auto_fix_prompt(self, sql_query: str, issues_found: List[str]) -> str:
        """Génère le prompt de correction automatique."""
        return self.render_macro(
            'sql_generation.j2',
            'auto_fix_prompt',
            sql_query=sql_query,
            issues_found=issues_found
        )
    
    def get_suggestions_prompt(
        self, 
        user_query: str, 
        failed_attempts: List[Dict[str, str]] = None
    ) -> str:
        """Génère le prompt de suggestions d'amélioration."""
        return self.render_macro(
            'sql_generation.j2',
            'suggest_improvements_prompt',
            user_query=user_query,
            failed_attempts=failed_attempts or []
        )
    
    # ========================================================================
    # MÉTHODES SPÉCIALISÉES POUR LA VALIDATION
    # ========================================================================
    
    def get_semantic_validation_prompt(
        self,
        sql_query: str,
        original_request: str, 
        schema: str,
        context: Dict[str, Any] = None
    ) -> str:
        """Génère le prompt de validation sémantique."""
        return self.render_macro(
            'sql_validation.j2',
            'semantic_validation_prompt',
            sql_query=sql_query,
            original_request=original_request,
            schema=schema,
            context=context or {}
        )
    
    def get_framework_validation_prompt(
        self,
        sql_query: str,
        required_elements: Dict[str, Any] = None
    ) -> str:
        """Génère le prompt de validation du framework."""
        return self.render_macro(
            'sql_validation.j2',
            'framework_validation_prompt',
            sql_query=sql_query,
            required_elements=required_elements or {}
        )
    
    def get_performance_validation_prompt(
        self,
        sql_query: str,
        expected_complexity: str = "medium"
    ) -> str:
        """Génère le prompt de validation de performance."""
        return self.render_macro(
            'sql_validation.j2',
            'performance_validation_prompt',
            sql_query=sql_query,
            expected_complexity=expected_complexity
        )
    
    def get_business_validation_prompt(
        self,
        sql_query: str,
        original_request: str,
        domain_rules: Dict[str, Any] = None
    ) -> str:
        """Génère le prompt de validation métier RH."""
        return self.render_macro(
            'sql_validation.j2',
            'business_validation_prompt',
            sql_query=sql_query,
            original_request=original_request,
            domain_rules=domain_rules or {}
        )
    
    def get_temporal_validation_prompt(
        self,
        sql_query: str,
        original_request: str,
        detected_dates: List[Dict[str, str]] = None
    ) -> str:
        """Génère le prompt de validation temporelle."""
        return self.render_macro(
            'sql_validation.j2',
            'temporal_validation_prompt',
            sql_query=sql_query,
            original_request=original_request,
            detected_dates=detected_dates or []
        )
    
    def get_validation_report_prompt(
        self,
        sql_query: str,
        original_request: str,
        all_checks: List[Dict[str, str]]
    ) -> str:
        """Génère le prompt de rapport de validation."""
        return self.render_macro(
            'sql_validation.j2',
            'validation_report_prompt',
            sql_query=sql_query,
            original_request=original_request,
            all_checks=all_checks
        )
    
    # ========================================================================
    # MÉTHODES UTILITAIRES
    # ========================================================================
    
    def list_available_templates(self) -> List[str]:
        """Retourne la liste des templates disponibles."""
        try:
            return [f.name for f in self.templates_dir.glob("*.j2")]
        except Exception as e:
            logger.error(f"Erreur lors de la liste des templates: {e}")
            return []
    
    def list_template_macros(self, template_name: str) -> List[str]:
        """Retourne la liste des macros d'un template."""
        try:
            template = self.get_template(template_name)
            return [name for name in template.module.__dict__.keys() 
                   if not name.startswith('_')]
        except Exception as e:
            logger.error(f"Erreur lors de la liste des macros de {template_name}: {e}")
            return []
    
    def validate_template_syntax(self, template_name: str) -> bool:
        """Valide la syntaxe d'un template."""
        try:
            self.get_template(template_name)
            return True
        except Exception as e:
            logger.error(f"Erreur de syntaxe dans {template_name}: {e}")
            return False
    
    def render_with_fallback(
        self, 
        template_name: str, 
        macro_name: str, 
        fallback_text: str = "", 
        **kwargs
    ) -> str:
        """
        Rend une macro avec fallback en cas d'erreur.
        
        Args:
            template_name: Nom du template
            macro_name: Nom de la macro
            fallback_text: Texte de fallback si erreur
            **kwargs: Variables pour le rendu
            
        Returns:
            Prompt rendu ou texte de fallback
        """
        try:
            return self.render_macro(template_name, macro_name, **kwargs)
        except Exception as e:
            logger.warning(f"Échec du rendu {macro_name}, utilisation du fallback: {e}")
            return fallback_text
    
    def clear_cache(self):
        """Vide le cache des templates."""
        self._template_cache.clear()
        self.get_template.cache_clear()
        logger.info("Cache des templates vidé")


# Instance globale (singleton pattern)
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """
    Récupère l'instance globale du gestionnaire de prompts.
    
    Returns:
        Instance PromptManager
    """
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


# Fonctions de convenance pour l'API
def render_sql_prompt(user_query: str, schema: str, **kwargs) -> str:
    """Fonction de convenance pour générer un prompt SQL."""
    return get_prompt_manager().get_sql_generation_prompt(user_query, schema, **kwargs)


def render_validation_prompt(sql_query: str, original_request: str, **kwargs) -> str:
    """Fonction de convenance pour générer un prompt de validation."""
    return get_prompt_manager().get_semantic_validation_prompt(
        sql_query, original_request, **kwargs
    )