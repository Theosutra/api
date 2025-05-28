"""
Service de traduction principal pour l'API NL2SQL.

Ce service centralise toute la logique métier de traduction NL2SQL,
remplaçant complètement translator.py et la logique dispersée dans routes.py.

Author: Datasulting
Version: 2.0.0
"""

import time
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from app.config import get_settings
from app.core.embedding import get_embedding
from app.core.vector_search import find_similar_queries, check_exact_match, store_query
from app.core.llm_service import LLMService
from app.utils.schema_loader import load_schema
from app.services.validation_service import ValidationService
from app.utils.cache_decorator import cache_service_method
from app.core.exceptions import (
    ValidationError, FrameworkError, LLMError, LLMNetworkError, 
    LLMAuthError, LLMQuotaError, EmbeddingError, VectorSearchError, SchemaError
)

# Import du gestionnaire de prompts avec fallback
try:
    from app.prompts.prompt_manager import get_prompt_manager
    PROMPTS_AVAILABLE = True
except ImportError:
    PROMPTS_AVAILABLE = False

logger = logging.getLogger(__name__)


class TranslationService:
    """
    Service principal de traduction NL2SQL avec architecture service-oriented.
    
    Centralise toute la logique métier et remplace la fonction translate_nl_to_sql
    dispersée dans translator.py avec une approche plus maintenable.
    
    Fonctionnalités:
    - Traduction complète NL2SQL
    - Gestion des correspondances exactes
    - Validation unifiée (syntaxe, sécurité, framework, sémantique)
    - Correction automatique
    - Gestion du cache et stockage
    - Formatage des réponses
    - Support des prompts Jinja2
    """
    
    def __init__(self, config=None):
        """
        Initialise le service de traduction.
        
        Args:
            config: Configuration de l'application (utilise get_settings() si None)
        """
        self.config = config or get_settings()
        self.validation_service = ValidationService(self.config)
        
        # Gestionnaire de prompts Jinja2 avec fallback
        if PROMPTS_AVAILABLE:
            try:
                self.prompt_manager = get_prompt_manager()
                logger.info("PromptManager initialisé pour TranslationService")
            except Exception as e:
                logger.warning(f"Erreur initialisation PromptManager: {e}")
                self.prompt_manager = None
        else:
            self.prompt_manager = None
            logger.warning("PromptManager non disponible, utilisation des prompts par défaut")
        
        # Opérations interdites dans la requête utilisateur
        self.forbidden_operations = ["insert", "update", "delete", "drop", "truncate", "alter", "create"]
    
    # ==========================================================================
    # MÉTHODE PRINCIPALE DE TRADUCTION
    # ==========================================================================
    
    @cache_service_method(ttl=3600, key_prefix="translation")  # Cache 1h pour les traductions
    async def translate(
        self,
        user_query: str,
        schema_path: Optional[str] = None,
        validate: bool = True,
        explain: bool = True,
        store_result: bool = False,
        return_similar_queries: bool = False,
        user_id_placeholder: str = "?",
        use_cache: bool = True,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        include_similar_details: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Traduction principale NL2SQL avec toute la logique métier centralisée.
        
        Args:
            user_query: Requête en langage naturel
            schema_path: Chemin du schéma (optionnel)
            validate: Activer la validation
            explain: Générer une explication
            store_result: Stocker le résultat dans Pinecone
            return_similar_queries: Inclure les requêtes similaires (format simple)
            user_id_placeholder: Placeholder pour l'ID utilisateur
            use_cache: Utiliser le cache
            provider: Fournisseur LLM
            model: Modèle LLM
            include_similar_details: Inclure les détails complets des vecteurs
            
        Returns:
            Résultat complet de la traduction
        """
        start_time = time.time()
        
        # Initialiser le résultat
        result = self._init_translation_result(user_query, provider, model)
        
        try:
            # 1. Validation de l'entrée utilisateur
            await self._validate_user_input(user_query, result)
            if result["status"] == "error":
                return result
            
            # 2. Vérification de pertinence RH
            await self._check_relevance(user_query, provider, model, result)
            if result["status"] == "error":
                return result
            
            # 3. Chargement du schéma
            schema = await self._load_schema(schema_path, result)
            if result["status"] == "error":
                return result
            
            # 4. Recherche vectorielle
            similar_queries = await self._perform_vector_search(user_query, result)
            if result["status"] == "error":
                return result
            
            # 5. Formatage des requêtes similaires pour la réponse
            await self._format_similar_queries_response(
                similar_queries, return_similar_queries, include_similar_details, result
            )
            
            # 6. Vérification de correspondance exacte
            exact_match = await self._check_exact_match(similar_queries, result)
            
            if exact_match:
                # 7a. Traitement correspondance exacte
                await self._handle_exact_match(exact_match, result)
            else:
                # 7b. Génération nouvelle requête SQL
                await self._generate_new_sql(
                    user_query, schema, similar_queries, provider, model, result
                )
            
            # 8. Validation complète
            if validate and result["sql"]:
                await self._perform_complete_validation(
                    result["sql"], user_query, schema, provider, model, result
                )
            
            # 9. Génération d'explication
            if explain and result["sql"] and result["status"] != "error":
                await self._generate_explanation(result["sql"], user_query, provider, model, result)
            
            # 10. Stockage du résultat
            if store_result and result["valid"] and result["sql"]:
                await self._store_result(user_query, result["sql"], result)
        
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la traduction: {e}", exc_info=True)
            result["status"] = "error"
            result["validation_message"] = f"Erreur interne: {str(e)}"
        
        finally:
            # Finaliser le résultat
            self._finalize_result(result, start_time)
        
        return result
    
    # ==========================================================================
    # MÉTHODES PRIVÉES - ÉTAPES DE TRADUCTION
    # ==========================================================================
    
    def _init_translation_result(self, user_query: str, provider: Optional[str], model: Optional[str]) -> Dict[str, Any]:
        """Initialise le dictionnaire de résultat."""
        return {
            "query": user_query,
            "sql": None,
            "valid": None,
            "validation_message": None,
            "explanation": None,
            "is_exact_match": False,
            "status": "processing",
            "processing_time": None,
            "similar_queries": None,
            "similar_queries_details": None,
            "from_cache": False,
            "framework_compliant": False,
            "framework_details": None,
            "provider": provider or self.config.DEFAULT_PROVIDER,
            "model": model
        }
    
    async def _validate_user_input(self, user_query: str, result: Dict[str, Any]):
        """Valide l'entrée utilisateur."""
        try:
            # Validation basique
            is_valid, message = self.validation_service.validate_user_input(user_query)
            if not is_valid:
                result["status"] = "error"
                result["validation_message"] = message
                return
            
            # Vérification des opérations interdites
            for op in self.forbidden_operations:
                if op in user_query.lower():
                    result["status"] = "error"
                    result["validation_message"] = (
                        f"Opération '{op.upper()}' non autorisée. "
                        "Seules les requêtes de consultation (SELECT) sont permises."
                    )
                    return
        
        except Exception as e:
            logger.error(f"Erreur lors de la validation de l'entrée: {e}")
            result["status"] = "error"
            result["validation_message"] = f"Erreur de validation de l'entrée: {str(e)}"
    
    async def _check_relevance(
        self, 
        user_query: str, 
        provider: Optional[str], 
        model: Optional[str], 
        result: Dict[str, Any]
    ):
        """Vérifie la pertinence RH de la requête."""
        try:
            is_relevant = await LLMService.check_relevance(user_query, provider=provider, model=model)
            
            if not is_relevant:
                result["status"] = "error"
                result["validation_message"] = (
                    "Cette requête ne semble pas concerner les ressources humaines. "
                    "Cette base de données contient uniquement des informations RH "
                    "(employés, contrats, absences, paie, etc.)."
                )
        
        except (LLMAuthError, LLMQuotaError) as e:
            logger.error(f"Erreur LLM critique lors de la vérification de pertinence: {e}")
            result["status"] = "error"
            result["validation_message"] = f"Service LLM temporairement indisponible: {e.message}"
        
        except LLMNetworkError as e:
            logger.warning(f"Erreur réseau LLM, skip vérification pertinence: {e}")
            # Continuer en cas d'erreur réseau
        
        except LLMError as e:
            logger.error(f"Erreur LLM lors de la vérification de pertinence: {e}")
            result["status"] = "error"
            result["validation_message"] = f"Erreur du service LLM: {e.message}"
    
    async def _load_schema(self, schema_path: Optional[str], result: Dict[str, Any]) -> Optional[str]:
        """Charge le schéma de la base de données."""
        try:
            if schema_path is None:
                schema_path = self.config.SCHEMA_PATH
            
            logger.info(f"Chargement du schéma: {schema_path}")
            return await load_schema(schema_path)
        
        except FileNotFoundError as e:
            logger.error(f"Fichier de schéma introuvable: {e}")
            result["status"] = "error"
            result["validation_message"] = f"Fichier de schéma introuvable: {schema_path}"
            return None
        
        except Exception as e:
            logger.error(f"Erreur lors du chargement du schéma: {e}")
            result["status"] = "error"
            result["validation_message"] = f"Erreur de chargement du schéma: {str(e)}"
            return None
    
    async def _perform_vector_search(self, user_query: str, result: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Effectue la recherche vectorielle."""
        try:
            # Vectorisation
            query_vector = await get_embedding(user_query)
            
            # Recherche des requêtes similaires
            similar_queries = await find_similar_queries(query_vector, self.config.TOP_K_RESULTS)
            
            logger.debug(f"Recherche vectorielle: {len(similar_queries)} requêtes similaires trouvées")
            return similar_queries
        
        except EmbeddingError as e:
            logger.error(f"Erreur lors de la vectorisation: {e}")
            result["status"] = "error"
            result["validation_message"] = f"Erreur du service de vectorisation: {str(e)}"
            return None
        
        except VectorSearchError as e:
            logger.error(f"Erreur lors de la recherche vectorielle: {e}")
            result["status"] = "error"
            result["validation_message"] = f"Erreur du service de recherche: {str(e)}"
            return None
    
    async def _format_similar_queries_response(
        self,
        similar_queries: List[Dict[str, Any]],
        return_similar_queries: bool,
        include_similar_details: bool,
        result: Dict[str, Any]
    ):
        """Formate les requêtes similaires pour la réponse."""
        try:
            if include_similar_details:
                result["similar_queries_details"] = self._format_similar_queries_detailed(similar_queries)
            
            if return_similar_queries:
                result["similar_queries"] = self._format_similar_queries_simple(similar_queries)
        
        except Exception as e:
            logger.warning(f"Erreur lors du formatage des requêtes similaires: {e}")
            # Non critique, continuer sans les détails
    
    def _format_similar_queries_detailed(self, similar_queries: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """Formate les requêtes similaires avec détails complets."""
        if not similar_queries:
            return None
        
        detailed_queries = []
        for query in similar_queries:
            metadata = query.get('metadata', {})
            detailed_queries.append({
                "score": round(query.get('score', 0), 4),
                "texte_complet": metadata.get('texte_complet', ''),
                "requete": metadata.get('requete', ''),
                "id": query.get('id', '')
            })
        return detailed_queries
    
    def _format_similar_queries_simple(self, similar_queries: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """Formate les requêtes similaires en format simplifié."""
        if not similar_queries:
            return None
        
        simplified_queries = []
        for query in similar_queries:
            metadata = query.get('metadata', {})
            simplified_queries.append({
                "score": round(query.get('score', 0), 4),
                "query": metadata.get('texte_complet', ''),
                "sql": metadata.get('requete', '')
            })
        return simplified_queries
    
    async def _check_exact_match(self, similar_queries: List[Dict[str, Any]], result: Dict[str, Any]) -> Optional[str]:
        """Vérifie s'il y a une correspondance exacte."""
        try:
            exact_match = await check_exact_match(similar_queries, self.config.EXACT_MATCH_THRESHOLD)
            
            if exact_match:
                logger.info("Correspondance exacte trouvée")
                
                # Validation de cohérence sémantique (années)
                user_years = re.findall(r'\b(20\d{2})\b', result["query"])
                sql_years = re.findall(r'\b(20\d{2})\b', exact_match)
                
                if user_years and sql_years and user_years[0] != sql_years[0]:
                    logger.warning(f"Correspondance exacte avec année différente: {user_years[0]} vs {sql_years[0]}")
                    return None
            
            return exact_match
        
        except Exception as e:
            logger.warning(f"Erreur lors de la vérification de correspondance exacte: {e}")
            return None
    
    async def _handle_exact_match(self, exact_match: str, result: Dict[str, Any]):
        """Traite une correspondance exacte trouvée."""
        try:
            # Validation du framework de la correspondance exacte
            validation_result = await self.validation_service.validate_complete(
                sql_query=exact_match,
                auto_fix=True
            )
            
            if not validation_result["valid"]:
                logger.error(f"Correspondance exacte non valide: {validation_result['message']}")
                result["status"] = "error"
                result["validation_message"] = f"Correspondance exacte non conforme: {validation_result['message']}"
                return
            
            # Utiliser la requête corrigée si nécessaire
            final_query = validation_result["final_query"]
            
            result["sql"] = final_query
            result["valid"] = True
            result["validation_message"] = "Requête trouvée directement dans la base de connaissances et conforme au framework."
            result["is_exact_match"] = True
            result["status"] = "success"
            result["framework_compliant"] = True
            result["framework_details"] = validation_result["details"].get("framework", {})
        
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la correspondance exacte: {e}")
            result["status"] = "error"
            result["validation_message"] = f"Erreur lors du traitement de la correspondance exacte: {str(e)}"
    
    async def _generate_new_sql(
        self,
        user_query: str,
        schema: str,
        similar_queries: List[Dict[str, Any]],
        provider: Optional[str],
        model: Optional[str],
        result: Dict[str, Any]
    ):
        """Génère une nouvelle requête SQL avec contexte enrichi."""
        try:
            # Contexte enrichi pour la génération SQL
            context = {
                "period_filter": self._extract_period_from_query(user_query),
                "department_filter": self._extract_department_from_query(user_query),
                "strict_mode": True
            }
            
            # Génération SQL via LLM avec contexte
            sql_result = await LLMService.generate_sql(
                user_query=user_query,
                schema=schema,
                similar_queries=similar_queries,
                provider=provider,
                model=model,
                context=context  # Nouveau paramètre pour Jinja2
            )
            
            # Vérifier les cas spéciaux
            if sql_result is None or sql_result.upper() == "IMPOSSIBLE":
                result["status"] = "error"
                result["validation_message"] = (
                    "Cette demande ne semble pas concerner les ressources humaines "
                    "ou est impossible à traduire en SQL avec le schéma fourni."
                )
                return
            
            if sql_result and sql_result.upper() == "READONLY_VIOLATION":
                result["status"] = "error"
                result["validation_message"] = (
                    "Votre demande concerne une opération d'écriture (INSERT, UPDATE, DELETE, etc.) "
                    "qui n'est pas autorisée. Cette API est en lecture seule."
                )
                return
            
            result["sql"] = sql_result
            result["status"] = "success"
        
        except (LLMAuthError, LLMQuotaError) as e:
            logger.error(f"Erreur LLM critique lors de la génération SQL: {e}")
            result["status"] = "error"
            result["validation_message"] = f"Service LLM temporairement indisponible: {e.message}"
        
        except LLMNetworkError as e:
            logger.error(f"Erreur réseau LLM: {e}")
            result["status"] = "error" 
            result["validation_message"] = f"Erreur de connexion au service LLM: {e.message}"
        
        except LLMError as e:
            logger.error(f"Erreur LLM générique: {e}")
            result["status"] = "error"
            result["validation_message"] = f"Erreur du service LLM: {e.message}"
    
    def _extract_period_from_query(self, user_query: str) -> Optional[str]:
        """Extrait des informations de période de la requête utilisateur."""
        import re
        
        # Recherche d'années
        years = re.findall(r'\b(20\d{2})\b', user_query)
        if years:
            return f"Année: {years[0]}"
        
        # Recherche de mois
        months = re.findall(r'\b(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\b', user_query.lower())
        if months:
            return f"Mois: {months[0]}"
        
        return None
    
    def _extract_department_from_query(self, user_query: str) -> Optional[str]:
        """Extrait des informations de département de la requête utilisateur."""
        import re
        
        # Recherche de départements communs
        departments = ['IT', 'RH', 'Finance', 'Marketing', 'Commercial', 'Production', 'Logistique']
        for dept in departments:
            if dept.lower() in user_query.lower():
                return dept
        
        return None
    
    async def _perform_complete_validation(
        self,
        sql_query: str,
        user_query: str,
        schema: str,
        provider: Optional[str],
        model: Optional[str],
        result: Dict[str, Any]
    ):
        """Effectue la validation complète de la requête générée."""
        try:
            validation_result = await self.validation_service.validate_complete(
                sql_query=sql_query,
                original_request=user_query,
                schema=schema,
                provider=provider,
                model=model,
                auto_fix=True
            )
            
            # Mettre à jour le résultat avec la validation
            result["sql"] = validation_result["final_query"]
            result["valid"] = validation_result["valid"]
            result["validation_message"] = validation_result["message"]
            result["framework_compliant"] = validation_result["details"].get("framework", {}).get("compliant", False)
            result["framework_details"] = validation_result["details"].get("framework", {})
            
            if validation_result["auto_fix_applied"]:
                result["validation_message"] += " (Requête corrigée automatiquement)"
            
            if not validation_result["valid"]:
                result["status"] = "error"
        
        except Exception as e:
            logger.error(f"Erreur lors de la validation complète: {e}")
            # Ne pas faire échouer la traduction pour une erreur de validation
            result["valid"] = True
            result["validation_message"] = f"Validation ignorée due à une erreur: {str(e)}"
    
    async def _generate_explanation(
        self,
        sql_query: str,
        user_query: str,
        provider: Optional[str],
        model: Optional[str],
        result: Dict[str, Any]
    ):
        """Génère une explication de la requête SQL avec contexte personnalisé."""
        try:
            # Contexte personnalisé pour l'explication
            context = {
                "target_audience": "non-technique",  # Adaptable selon l'utilisateur
                "detail_level": "simple"
            }
            
            explanation = await LLMService.explain_sql(
                sql_query, 
                user_query,
                provider=provider,
                model=model,
                context=context  # Nouveau paramètre pour Jinja2
            )
            result["explanation"] = explanation
        
        except (LLMAuthError, LLMQuotaError, LLMNetworkError, LLMError) as e:
            logger.warning(f"Erreur LLM lors de l'explication, skip: {e}")
            result["explanation"] = "Explication non disponible due à une erreur du service LLM."
        
        except Exception as e:
            logger.warning(f"Erreur lors de l'explication: {e}")
            result["explanation"] = "Explication non disponible."
    
    async def _store_result(self, user_query: str, sql_query: str, result: Dict[str, Any]):
        """Stocke le résultat dans la base vectorielle."""
        try:
            # Re-vectoriser pour le stockage
            query_vector = await get_embedding(user_query)
            await store_query(user_query, query_vector, sql_query)
            logger.debug("Résultat stocké dans la base vectorielle")
        
        except Exception as e:
            logger.warning(f"Erreur lors du stockage en base vectorielle: {e}")
            # Ne pas faire échouer la requête pour ça
    
    def _finalize_result(self, result: Dict[str, Any], start_time: float):
        """Finalise le résultat de traduction."""
        # Calculer le temps de traitement
        processing_time = time.time() - start_time
        result["processing_time"] = round(processing_time, 3)
        
        # S'assurer que le statut est défini
        if result["status"] == "processing":
            if result["sql"] and result["valid"] is not False:
                result["status"] = "success"
            else:
                result["status"] = "error"
        
        # Logging final
        framework_status = "conforme" if result.get("framework_compliant", False) else "non conforme"
        similar_count = len(result.get("similar_queries_details", [])) if result.get("similar_queries_details") else 0
        
        logger.info(
            f"Traduction terminée en {processing_time:.3f}s "
            f"(statut: {result['status']}, framework: {framework_status}, "
            f"vecteurs similaires: {similar_count})"
        )
    
    # ==========================================================================
    # MÉTHODES UTILITAIRES
    # ==========================================================================
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Vérifie l'état de santé de tous les services utilisés par la traduction.
        
        Returns:
            État de santé complet
        """
        from app.core.embedding import check_embedding_service
        from app.core.vector_search import check_pinecone_service
        from app.utils.cache import get_cache_stats
        
        services_status = {}
        
        # Service d'embedding
        try:
            services_status["embedding"] = await check_embedding_service()
        except Exception as e:
            services_status["embedding"] = {"status": "error", "error": str(e)}
        
        # Service Pinecone
        try:
            services_status["pinecone"] = await check_pinecone_service()
        except Exception as e:
            services_status["pinecone"] = {"status": "error", "error": str(e)}
        
        # Service LLM
        try:
            services_status["llm"] = await LLMService.check_services_health()
        except Exception as e:
            services_status["llm"] = {"status": "error", "error": str(e)}
        
        # Service de cache
        try:
            services_status["cache"] = await get_cache_stats()
        except Exception as e:
            services_status["cache"] = {"status": "error", "error": str(e)}
        
        # Service de validation
        services_status["validation"] = {"status": "ok", "service": "ValidationService"}
        
        # Service de prompts Jinja2
        if self.prompt_manager:
            try:
                templates = self.prompt_manager.list_available_templates()
                services_status["prompts"] = {
                    "status": "ok",
                    "templates": templates,
                    "template_count": len(templates)
                }
            except Exception as e:
                services_status["prompts"] = {"status": "error", "error": str(e)}
        else:
            services_status["prompts"] = {"status": "fallback", "message": "Utilisation des prompts par défaut"}
        
        # Déterminer le statut global
        critical_services = ["embedding", "pinecone", "llm"]
        all_critical_ok = all(
            services_status.get(service, {}).get("status") == "ok" 
            for service in critical_services
        )
        
        global_status = "ok" if all_critical_ok else "error"
        
        return {
            "status": global_status,
            "version": "2.0.0",
            "services": services_status
        }
    
    def validate_translation_request(self, request_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Valide une requête de traduction complète.
        
        Args:
            request_data: Données de la requête
            
        Returns:
            Tuple (is_valid, message)
        """
        try:
            # Validation de base
            if not request_data.get("query"):
                return False, "Champ 'query' obligatoire manquant"
            
            # Validation de l'entrée utilisateur
            is_valid, message = self.validation_service.validate_user_input(request_data["query"])
            if not is_valid:
                return False, f"Requête invalide: {message}"
            
            # Validation des paramètres optionnels
            if "provider" in request_data:
                valid_providers = ["openai", "anthropic", "google"]
                if request_data["provider"] not in valid_providers:
                    return False, f"Provider invalide. Valides: {valid_providers}"
            
            if "user_id_placeholder" in request_data:
                placeholder = request_data["user_id_placeholder"]
                if not isinstance(placeholder, str) or len(placeholder) == 0:
                    return False, "user_id_placeholder doit être une chaîne non vide"
            
            return True, "Requête valide"
        
        except Exception as e:
            logger.error(f"Erreur lors de la validation de requête: {e}")
            return False, f"Erreur de validation: {str(e)}"
    
    def get_translation_suggestions(self, error_type: str, context: Dict[str, Any] = None) -> List[str]:
        """
        Génère des suggestions pour améliorer une requête de traduction.
        
        Args:
            error_type: Type d'erreur rencontrée
            context: Contexte additionnel
            
        Returns:
            Liste de suggestions
        """
        suggestions = []
        
        if error_type == "relevance":
            suggestions.extend([
                "Reformulez votre question pour qu'elle concerne les ressources humaines",
                "Mentionnez des éléments RH comme : employés, contrats, salaires, absences",
                "Exemples : 'Combien d'employés en CDI ?', 'Liste des salaires par département'"
            ])
        
        elif error_type == "framework":
            suggestions.extend([
                "Cette erreur indique un problème de sécurité dans la requête générée",
                "Essayez de reformuler votre demande de manière plus précise",
                "Contactez l'administrateur si le problème persiste"
            ])
        
        elif error_type == "llm_service":
            suggestions.extend([
                "Le service de génération SQL est temporairement indisponible",
                "Réessayez dans quelques instants",
                "Vérifiez votre connexion internet"
            ])
        
        elif error_type == "semantic":
            suggestions.extend([
                "Votre demande pourrait être ambiguë",
                "Soyez plus spécifique dans votre formulation",
                "Précisez la période, le département ou le type de données souhaité"
            ])
        
        return suggestions