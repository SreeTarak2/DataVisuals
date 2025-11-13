# backend/services/ai_service.py

import logging
import json
import httpx
from typing import Dict, List, Any, Optional
from datetime import datetime

import polars as pl
from fastapi import HTTPException
from bson import ObjectId

from database import get_database
from core.chart_definitions import CHART_DEFINITIONS, DataType
from services.analysis_service import analysis_service
from core.prompts import PromptFactory, PromptType
from config import settings

logger = logging.getLogger(__name__)


class AIService:
    """
    The definitive, multi-model AI Service for DataSage AI.
    It orchestrates a pipeline of specialized models to deliver hybrid,
    fact-based AI insights and conversational analysis.
    """

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=180.0, follow_redirects=True)
        
        self.chart_definitions = {chart['id']: chart for chart in CHART_DEFINITIONS}
        self.quis_question_templates = {
            'pattern_analysis': ["What are the main patterns or trends in this dataset?"],
            'performance_analysis': ["Which categories show the highest or lowest performance?"],
            'correlation_analysis': ["What are the most significant relationships between variables?"],
        }
        self.model_health_cache = {}

    @property
    def db(self):
        """Lazily gets the database connection on first access."""
        db_conn = get_database()
        if db_conn is None:
            raise Exception("Database is not connected. Application startup may have failed.")
        return db_conn

    # =================================================================================
    # == 1. CORE LLM ROUTER
    # =================================================================================

    async def _call_ollama(self, prompt: str, model_role: str, expect_json: bool = False) -> Any:
        """A centralized router for calling Ollama with the primary model only."""
        model_config = settings.MODELS.get(model_role)
        if not model_config:
            raise ValueError(f"Invalid model role specified: {model_role}")

        primary_model = model_config.get("primary")
        if not primary_model:
            raise ValueError(f"No primary model configured for role: {model_role}")

        model_name = primary_model["model"]
        base_url = primary_model["base_url"].rstrip('/')

        logger.info(f"Routing request to model '{model_name}' at '{base_url}' for role '{model_role}'.")

        payload = {"model": model_name, "prompt": prompt, "stream": False}
        if expect_json:
            payload["format"] = "json"

        try:
            logger.info(f"Making request to: {base_url}/api/generate")
            logger.info(f"Payload: {payload}")

            response = await self.http_client.post(
                f"{base_url}/api/generate",
                json=payload,
                timeout=240.0  # Increased timeout for Colab/Ollama
            )

            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")

            if response.status_code == 404:
                logger.error(f"404 Error: Ollama API not found at {base_url}. Check if Ollama is running and ngrok is properly configured.")
                raise HTTPException(
                    status_code=404,
                    detail=f"Ollama API not accessible at {base_url}. Please check if Ollama is running and ngrok is configured correctly."
                )

            response.raise_for_status()
            response_data = response.json()

            if expect_json:
                json_string = response_data.get("response", "{}")
                logger.info(f"Raw AI response for {model_role}: {json_string[:500]}...")
                try:
                    result = json.loads(json_string)
                    logger.info(f"Successfully parsed JSON for {model_role}: {result}")
                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"LLM '{model_name}' returned invalid JSON for role '{model_role}'. Response: {json_string[:500]}.... Error: {e}")
                    return {"error": "llm_json_parse_failed", "raw": json_string[:500]}
            else:
                return response_data.get("response", "").strip()

        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.error(f"Model '{model_name}' failed for role '{model_role}': {e}")
            logger.error(f"Connection details - URL: {base_url}, Model: {model_name}, Error type: {type(e).__name__}")

            if expect_json:
                if isinstance(e, httpx.TimeoutException):
                    return {
                        "response_text": f"AI engine for '{model_role}' timed out after 180 seconds. The model may be overloaded or the request is too complex. Please try again with a simpler query.",
                        "error": "model_timeout",
                        "connection_error": str(e)
                    }
                else:
                    return {
                        "response_text": f"AI engine for '{model_role}' is currently unavailable. Connection failed to {base_url}. Error: {str(e)}",
                        "error": "model_unavailable",
                        "connection_error": str(e)
                    }
            else:
                if isinstance(e, httpx.TimeoutException):
                    return f"AI engine for '{model_role}' timed out after 180 seconds. The model may be overloaded or the request is too complex. Please try again with a simpler query."
                else:
                    return f"AI engine for '{model_role}' is currently unavailable. Connection failed to {base_url}. Error: {str(e)}"

        except Exception as e:
            logger.error(f"Unexpected error with model '{model_name}' for role '{model_role}': {e}")
            if expect_json:
                return {
                    "response_text": f"AI engine for '{model_role}' encountered an error. Please try again later.",
                    "error": "model_error"
                }
            else:
                return f"AI engine for '{model_role}' encountered an error. Please try again later."

    async def _check_model_health(self, model_info: Dict[str, str]) -> bool:
        """Check if a model is healthy and responsive."""
        model_name = model_info["model"]
        base_url = model_info["base_url"].rstrip('/')
        cache_key = f"{model_name}_{base_url}"
        
        if cache_key in self.model_health_cache:
            cached_result, timestamp = self.model_health_cache[cache_key]
            if (datetime.now().timestamp() - timestamp) < 60:
                return cached_result
        
        try:
            test_payload = {"model": model_name, "prompt": "test", "stream": False}
            response = await self.http_client.post(
                f"{base_url}/api/generate",
                json=test_payload,
                timeout=settings.MODEL_HEALTH_CHECK_TIMEOUT
            )
            is_healthy = response.status_code == 200
            self.model_health_cache[cache_key] = (is_healthy, datetime.now().timestamp())
            return is_healthy
        except Exception as e:
            logger.warning(f"Health check failed for model '{model_name}': {e}")
            self.model_health_cache[cache_key] = (False, datetime.now().timestamp())
            return False

    async def get_model_status(self) -> Dict[str, Any]:
        """Get the health status of all configured models."""
        status = {}
        for role, config in settings.MODELS.items():
            primary_healthy = await self._check_model_health(config["primary"])
            
            status[role] = {
                "primary": {
                    "model": config["primary"]["model"],
                    "base_url": config["primary"]["base_url"],
                    "healthy": primary_healthy
                },
                "overall_healthy": primary_healthy
            }
        return status
    
    async def test_ollama_connection(self, base_url: str) -> Dict[str, Any]:
        """Test connection to a specific Ollama instance."""
        try:
            # Test basic connectivity
            response = await self.http_client.get(f"{base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return {
                    "status": "connected",
                    "models": [model.get("name", "unknown") for model in models],
                    "message": f"Successfully connected to {base_url}"
                }
            else:
                return {
                    "status": "error",
                    "message": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Connection failed: {str(e)}"
            }
            
    # =================================================================================
    # == 2. PUBLIC ORCHESTRATOR METHODS
    # =================================================================================

    async def generate_ai_dashboard(self, dataset_id: str, user_id: str, force_regenerate: bool = False) -> Dict[str, Any]:
        """Orchestrates AI dashboard generation with persistence and specialized models."""
        # Handle both ObjectId and UUID formats
        try:
            # Try ObjectId format first
            query = {"_id": ObjectId(dataset_id), "user_id": user_id}
        except Exception:
            # If ObjectId fails, treat as string (UUID format)
            query = {"_id": dataset_id, "user_id": user_id}
        
        dataset_doc = await self.db.datasets.find_one(query)
        if not dataset_doc or not dataset_doc.get("metadata"):
            raise HTTPException(status_code=409, detail="Dataset not ready for dashboard generation.")

        # Check for existing cached charts first
        from services.chart_insights_service import chart_insights_service
        cached_charts = await chart_insights_service.get_dataset_cached_charts(dataset_id, user_id)
        
        # If we have cached charts and not forcing regeneration, use them
        if cached_charts and not force_regenerate:
            logger.info(f"Using {len(cached_charts)} cached charts for dashboard")
            return self._build_dashboard_from_cached_charts(cached_charts, dataset_doc)

        # Check for existing dashboard blueprint
        dashboard_blueprint_doc = await self.db.dashboards.find_one({"dataset_id": dataset_id, "user_id": user_id, "is_default": True})
        
        # If force_regenerate is True, delete existing dashboard and regenerate
        if force_regenerate and dashboard_blueprint_doc:
            await self.db.dashboards.delete_one({"_id": dashboard_blueprint_doc["_id"]})
            dashboard_blueprint_doc = None

        if not dashboard_blueprint_doc:
            # Create enhanced context with actual data samples
            context_str = self._create_enhanced_llm_context(dataset_doc["metadata"], dataset_doc["file_path"])
            chart_ids = [chart['id'] for chart in self.chart_definitions.values()]
            
            # Use the new PromptFactory for enhanced functionality
            factory = PromptFactory(dataset_context=context_str)
            prompt = factory.get_prompt(PromptType.DASHBOARD_DESIGNER, chart_options=chart_ids, max_components=12)
            
            logger.info(f"Calling visualization_engine for dashboard generation...")
            layout_response = await self._call_ollama(prompt, model_role="visualization_engine", expect_json=True)
            logger.info(f"Dashboard generation response: {layout_response}")
            
            # Check if there's an error in the response
            if "error" in layout_response:
                logger.error(f"AI returned error: {layout_response}")
                raise HTTPException(status_code=500, detail=f"AI error: {layout_response.get('error', 'Unknown error')}")
            
            blueprint = layout_response.get("dashboard")
            if not blueprint:
                logger.error(f"No 'dashboard' key in AI response. Full response: {layout_response}")
                raise HTTPException(status_code=500, detail="AI response missing 'dashboard' key")
            
            if "components" not in blueprint:
                logger.error(f"No 'components' key in dashboard blueprint. Blueprint: {blueprint}")
                raise HTTPException(status_code=500, detail="AI dashboard blueprint missing 'components' key")

            new_dashboard_doc = {"dataset_id": dataset_id, "user_id": user_id, "is_default": True, "layout_name": "AI Default", "blueprint": blueprint, "created_at": datetime.utcnow()}
            await self.db.dashboards.insert_one(new_dashboard_doc)
            dashboard_blueprint_doc = new_dashboard_doc
        
        # Load file with proper format detection
        file_path = dataset_doc["file_path"]
        file_extension = file_path.split('.')[-1].lower()
        
        try:
            if file_extension in ['xlsx', 'xls']:
                # Handle Excel files
                df = pl.read_excel(file_path)
                logger.info(f"Successfully loaded Excel file for dashboard generation: {file_path}")
            elif file_extension == 'csv':
                # Handle CSV files with robust encoding
                encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                df = None
                for encoding in encodings_to_try:
                    try:
                        df = pl.read_csv(
                            file_path, 
                            encoding=encoding,
                            truncate_ragged_lines=True,
                            ignore_errors=True
                        )
                        logger.info(f"Successfully loaded CSV with encoding: {encoding}")
                        break
                    except UnicodeDecodeError as e:
                        logger.warning(f"Failed to load CSV with encoding '{encoding}': {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Unexpected error loading CSV with '{encoding}': {e}")
                        continue
                
                if df is None:
                    raise HTTPException(status_code=500, detail="Could not read CSV file with any supported encoding.")
            elif file_extension == 'json':
                # Handle JSON files
                df = pl.read_json(file_path)
                logger.info(f"Successfully loaded JSON file for dashboard generation: {file_path}")
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_extension}")
                
        except Exception as e:
            logger.error(f"Failed to load file {file_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Could not read dataset file: {str(e)}")
        blueprint = dashboard_blueprint_doc["blueprint"]
        hydrated_components = []
        for component in blueprint.get("components", []):
            # Some LLM responses may return strings or other non-dict placeholders.
            if not isinstance(component, dict):
                logger.warning(f"Skipping component because it's not a dict: {repr(component)[:200]}")
                continue
            try:
                hydrated_component = component.copy()
                ctype = component.get("type")
                config = component.get("config", {})
                if ctype == "kpi":
                    hydrated_component["value"] = self._hydrate_kpi_data(df, config)
                elif ctype == "chart":
                    hydrated_component["chart_data"] = self._hydrate_chart_data(df, config)
                elif ctype == "table":
                    hydrated_component["table_data"] = self._hydrate_table_data(df, config)

                # Only append components that have some populated data
                if (hydrated_component.get("value") is not None) or hydrated_component.get("chart_data") or hydrated_component.get("table_data"):
                    hydrated_components.append(hydrated_component)
            except Exception as e:
                # Use safe logging in case component lacks 'title' or other keys
                title = component.get('title') if isinstance(component, dict) else None
                logger.warning(f"Could not populate dashboard component '{title}'. Error: {e}")

        return {"layout_grid": blueprint.get("layout_grid", "repeat(1, 1fr)"), "components": hydrated_components}

    def _build_dashboard_from_cached_charts(self, cached_charts: List[Dict], dataset_doc: Dict) -> Dict[str, Any]:
        """Build dashboard from cached charts instead of regenerating."""
        try:
            components = []
            
            for i, cached_chart in enumerate(cached_charts[:6]):  # Limit to 6 charts
                chart_config = cached_chart.get("chart_config", {})
                chart_data = cached_chart.get("chart_data", [])
                insight = cached_chart.get("insight", {})
                
                # Create component from cached chart
                component = {
                    "id": f"cached_chart_{i}",
                    "type": "chart",
                    "title": insight.get("insight", {}).get("title", f"Chart {i+1}"),
                    "chart_type": chart_config.get("chart_type", "bar"),
                    "x_axis": chart_config.get("x_axis", "X"),
                    "y_axis": chart_config.get("y_axis", "Y"),
                    "data": chart_data,
                    "insight": insight,
                    "cached": True,
                    "position": {"row": i // 2, "col": i % 2},
                    "size": "medium" if i < 2 else "small"
                }
                components.append(component)
            
            # Create a simple grid layout
            layout_grid = "repeat(2, 1fr)" if len(components) > 2 else "1fr"
            
            return {
                "layout_grid": layout_grid,
                "components": components,
                "cached": True,
                "chart_count": len(components)
            }
            
        except Exception as e:
            logger.error(f"Error building dashboard from cached charts: {e}")
            # Fallback to regular generation
            return None

    async def process_chat_message_enhanced(self, query: str, dataset_id: str, user_id: str, conversation_id: Optional[str] = None, mode: str = "learning") -> Dict[str, Any]:
        """Enhanced chat processing with schema injection, validation, and RAG integration."""
        try:
            # Use the main method with mode parameter
            return await self.process_chat_message(query, dataset_id, user_id, conversation_id, mode)
        except Exception as e:
            logger.error(f"Enhanced chat error: {e}")
            raise HTTPException(500, "Enhanced chat processing failed")

    def _extract_schema(self, dataset_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Extract schema information from dataset document."""
        metadata = dataset_doc.get("metadata", {})
        column_metadata = metadata.get("column_metadata", [])
        
        schema = {
            "columns": {},
            "key_metrics": [],
            "data_types": {}
        }
        
        for col in column_metadata:
            col_name = col.get("name", "")
            col_type = col.get("type", "unknown")
            schema["columns"][col_name] = col_type
            schema["data_types"][col_type] = schema["data_types"].get(col_type, 0) + 1
        
        # Generate key metrics based on column types
        numeric_cols = [name for name, type in schema["columns"].items() if type == "numeric"]
        categorical_cols = [name for name, type in schema["columns"].items() if type == "categorical"]
        
        for col in numeric_cols:
            schema["key_metrics"].append(f"sum({col})")
            schema["key_metrics"].append(f"mean({col})")
        
        return schema

    async def _get_conversation_history(self, conv_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Fetch conversation history from database."""
        try:
            conversation = await self.db.conversations.find_one({
                "_id": ObjectId(conv_id), 
                "user_id": user_id
            })
            if conversation:
                return conversation.get("messages", [])
        except Exception as e:
            logger.warning(f"Failed to fetch conversation history: {e}")
        return []

    def _generate_id(self) -> str:
        """Generate unique ID for conversations."""
        import uuid
        return str(uuid.uuid4())

    # Legacy method - keeping for backward compatibility but enhanced
    async def process_chat_message(self, query: str, dataset_id: str, user_id: str, conversation_id: Optional[str] = None, mode: str = "learning") -> Dict[str, Any]:
        """Main chat processing method - simplified version for stability."""
        try:
            # Load conversation and append user message
            conversation = await self._load_or_create_conversation(conversation_id, user_id, dataset_id)
            messages = conversation.get("messages", [])
            messages.append({"role": "user", "content": query})

                # Fetch dataset
            try:
                db_query = {"_id": ObjectId(dataset_id), "user_id": user_id}
            except Exception:
                db_query = {"_id": dataset_id, "user_id": user_id}
            
            dataset_doc = await self.db.datasets.find_one(db_query)
            if not dataset_doc or not dataset_doc.get("metadata"):
                raise HTTPException(status_code=409, detail="Dataset is still being processed. Please wait.")

            # Create simple prompt using the legacy method
            prompt = self._create_conversational_prompt(messages, dataset_doc["metadata"])
            
            # Call LLM
            llm_response = await self._call_ollama(prompt, "chart_engine", expect_json=True)
            
            # Handle response
            if isinstance(llm_response, dict) and "error" in llm_response:
                # Provide fallback response instead of raising error
                error_type = llm_response.get("error", "unknown")
                if error_type == "model_timeout":
                    ai_content = "I'm experiencing some delays processing your request. The AI model is currently overloaded. Please try again in a moment with a simpler query, or I can help you with basic data analysis in the meantime."
                elif error_type == "model_unavailable":
                    ai_content = "I'm temporarily unable to connect to the AI model. Please try again in a few moments, or I can help you with basic data analysis."
                else:
                    ai_content = "I encountered an issue processing your request. Please try again, or I can help you with basic data analysis."
                chart_config = None
            else:
                # Extract response
                ai_content = llm_response.get("response_text", "I was unable to process your request.")
                chart_config = llm_response.get("chart_config")

                # Echo Detection - Check if model copied template text
                if ("Your analysis and insights about the data trends" in ai_content and "150-200 words" in ai_content) or "[ORIGINAL" in ai_content:
                    logger.warning("Echo detected in LLM response, retrying with simplified prompt")
                    # Retry with a simplified prompt
                    simple_prompt = f"""
                    Analyze the dataset and answer: {query}
                    
                    Dataset Schema: {json.dumps(self._extract_schema(dataset_doc), indent=2)}
                    
                    Provide a JSON response with:
                    {{
                        "response_text": "Your analysis and insights about the data trends",
                        "chart_config": null,
                        "confidence": "High|Med|Low"
                    }}
                    """
                    llm_response = await self._call_ollama(simple_prompt, "chart_engine", expect_json=True)
                    if isinstance(llm_response, dict) and "error" not in llm_response:
                        ai_content = llm_response.get("response_text", "I was unable to process your request.")
                        chart_config = llm_response.get("chart_config")

                # Create response
                response = {
                    "response": ai_content,
                    "chart_config": chart_config,
                    "conversation_id": conversation_id or str(conversation["_id"])
                }

                # Save conversation
                await self._save_conversation(conversation["_id"], messages + [{"role": "ai", "content": ai_content}])

                return response

        except Exception as e:
            logger.error(f"Chat processing error: {e}")
            raise HTTPException(500, "Chat processing failed")

    async def process_chat_message_legacy(self, query: str, dataset_id: str, user_id: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Legacy chat processing method for backward compatibility."""
        return await self.process_chat_message(query, dataset_id, user_id, conversation_id, mode="learning")

        
    async def generate_quis_insights(self, dataset_metadata: Dict, dataset_name: str) -> Dict[str, Any]:
        """Generates simpler, proactive insights using the QUIS methodology."""
        insight_cards = []
        for analysis_type, questions in self.quis_question_templates.items():
            for question in questions:
                answer = await self._generate_llm_answer(question, dataset_metadata, dataset_name)
                insight_cards.append({
                    'question': question,
                    'answer': answer,
                    'analysis_type': analysis_type,
                    'confidence': self._calculate_question_confidence(analysis_type, dataset_metadata)
                })
        
        insight_cards.sort(key=lambda x: x['confidence'], reverse=True)
        return {'insight_cards': insight_cards}

    # =================================================================================
    # == 3. PRIVATE HELPER & UTILITY METHODS
    # =================================================================================

    def _create_conversational_prompt(self, messages: List[Dict], dataset_metadata: Dict) -> str:
        dataset_context = self._create_llm_context_string(dataset_metadata)
        chart_options = [chart['id'] for chart in self.chart_definitions.values()]
        
        # Extract schema from dataset metadata
        schema = self._extract_schema_from_metadata(dataset_metadata)
        
        factory = PromptFactory(dataset_context=dataset_context, schema=schema)
        return factory.get_prompt(PromptType.CONVERSATIONAL, history=messages, chart_options=chart_options)
    
    def _extract_schema_from_metadata(self, dataset_metadata: Dict) -> Dict:
        """Extract schema information from dataset metadata."""
        columns = dataset_metadata.get('column_metadata', [])
        schema = {
            "columns": {},
            "key_metrics": [],
            "data_types": {}
        }
        
        for col in columns:
            col_name = col.get("name", "")
            col_type = col.get("type", "unknown")
            schema["columns"][col_name] = col_type
            schema["data_types"][col_type] = schema["data_types"].get(col_type, 0) + 1
        
        return schema
        
    async def _load_or_create_conversation(self, conv_id: Optional[str], user_id: str, dataset_id: str) -> Dict:
        if conv_id:
            try:
                conversation = await self.db.conversations.find_one({"_id": ObjectId(conv_id), "user_id": user_id})
                if conversation:
                    return conversation
            except Exception:
                pass
        
        new_conv = {"user_id": user_id, "dataset_id": dataset_id, "created_at": datetime.utcnow(), "messages": []}
        result = await self.db.conversations.insert_one(new_conv)
        new_conv["_id"] = result.inserted_id
        return new_conv

    async def _save_conversation(self, conv_id: ObjectId, messages: List[Dict]):
        await self.db.conversations.update_one({"_id": conv_id}, {"$set": {"messages": messages}})
    
    async def get_user_conversations(self, user_id: str) -> List[Dict]:
        """Get all conversations for a user"""
        try:
            conversations = await self.db.conversations.find(
                {"user_id": user_id}
            ).sort("created_at", -1).to_list(length=100)
            
            # Convert ObjectId to string for JSON serialization
            for conv in conversations:
                conv["_id"] = str(conv["_id"])
                # Get dataset name for each conversation
                try:
                    dataset = await self.db.datasets.find_one({"_id": conv["dataset_id"], "user_id": user_id})
                    conv["dataset_name"] = dataset.get("name", "Unknown Dataset") if dataset else "Unknown Dataset"
                except Exception:
                    conv["dataset_name"] = "Unknown Dataset"
            
            return conversations
        except Exception as e:
            logger.error(f"Failed to get user conversations: {e}")
            return []
    
    async def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Dict]:
        """Get a specific conversation by ID"""
        try:
            conversation = await self.db.conversations.find_one({
                "_id": ObjectId(conversation_id), 
                "user_id": user_id
            })
            if conversation:
                conversation["_id"] = str(conversation["_id"])
                # Get dataset name
                try:
                    dataset = await self.db.datasets.find_one({"_id": conversation["dataset_id"], "user_id": user_id})
                    conversation["dataset_name"] = dataset.get("name", "Unknown Dataset") if dataset else "Unknown Dataset"
                except Exception:
                    conversation["dataset_name"] = "Unknown Dataset"
            return conversation
        except Exception as e:
            logger.error(f"Failed to get conversation {conversation_id}: {e}")
            return None
    
    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Delete a specific conversation"""
        try:
            result = await self.db.conversations.delete_one({
                "_id": ObjectId(conversation_id), 
                "user_id": user_id
            })
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete conversation {conversation_id}: {e}")
            return False

    def _create_llm_context_string(self, dataset_metadata: Dict) -> str:
        overview = dataset_metadata.get('dataset_overview', {})
        columns = dataset_metadata.get('column_metadata', [])
        statistical_findings = dataset_metadata.get('statistical_findings', {})
        
        col_strings = []
        for c in columns[:15]:
            col_name = c.get('name', 'Unknown')
            col_type = c.get('type', 'Unknown')
            null_count = c.get('null_count', 0)
            col_strings.append(f"{col_name} ({col_type}, {null_count} nulls)")
        
        context_parts = [
            f"Dataset Overview: {overview.get('total_rows', 'N/A')} rows, {overview.get('total_columns', 'N/A')} columns.",
            f"Column Details: {', '.join(col_strings)}"
        ]
        
        if statistical_findings:
            context_parts.append("\nStatistical Insights:")
            
            if 'data_types' in statistical_findings:
                data_types = statistical_findings['data_types']
                type_summary = []
                for dtype, count in data_types.items():
                    type_summary.append(f"{dtype}: {count} columns")
                context_parts.append(f"Data Types: {', '.join(type_summary)}")
            
            if 'numeric_columns' in statistical_findings:
                numeric_cols = statistical_findings['numeric_columns']
                if numeric_cols:
                    context_parts.append(f"Numeric Columns: {', '.join(numeric_cols[:5])}")
            
            if 'categorical_columns' in statistical_findings:
                categorical_cols = statistical_findings['categorical_columns']
                if categorical_cols:
                    context_parts.append(f"Categorical Columns: {', '.join(categorical_cols[:5])}")
            
            if 'temporal_columns' in statistical_findings:
                temporal_cols = statistical_findings['temporal_columns']
                if temporal_cols:
                    context_parts.append(f"Date/Time Columns: {', '.join(temporal_cols)}")
        
        if len(columns) > 15: 
            context_parts.append(f"... and {len(columns) - 15} more columns")
        
        return "\n".join(context_parts)

    def _create_enhanced_llm_context(self, dataset_metadata: Dict, file_path: str) -> str:
        """Creates enhanced context with actual data samples for better AI understanding."""
        basic_context = self._create_llm_context_string(dataset_metadata)
        
        try:
            file_extension = file_path.split('.')[-1].lower()
            
            if file_extension in ['xlsx', 'xls']:
                df = pl.read_excel(file_path)
                logger.info(f"Successfully loaded Excel file for context: {file_path}")
            elif file_extension == 'csv':
                encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                df = None
                for encoding in encodings_to_try:
                    try:
                        df = pl.read_csv(
                            file_path, 
                            encoding=encoding,
                            truncate_ragged_lines=True,
                            ignore_errors=True
                        )
                        logger.info(f"Successfully loaded CSV with encoding: {encoding}")
                        break
                    except UnicodeDecodeError as e:
                        logger.warning(f"Failed to load CSV with encoding '{encoding}': {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Unexpected error loading CSV with '{encoding}': {e}")
                        continue
                
                if df is None:
                    logger.error("Could not load CSV with any encoding. Skipping data samples.")
                    return basic_context
            elif file_extension == 'json':
                df = pl.read_json(file_path)
                logger.info(f"Successfully loaded JSON file for context: {file_path}")
            else:
                logger.warning(f"Unsupported file format for context: {file_extension}")
                return basic_context
            sample_rows = []
            if len(df) > 0:
                try:
                    sample_data = df.head(3)
                    for i, row in enumerate(sample_data.iter_rows(named=True)):
                        row_data = []
                        for col, value in row.items():
                            try:
                                if value is None:
                                    str_value = "null"
                                else:
                                    str_value = str(value)
                                    if isinstance(str_value, bytes):
                                        str_value = str_value.decode('utf-8', errors='replace')
                                    if len(str_value) > 50:
                                        str_value = str_value[:47] + "..."
                                row_data.append(f"{col}: {str_value}")
                            except Exception as e:
                                row_data.append(f"{col}: [encoding_error]")
                        sample_rows.append(f"Row {i+1}: {', '.join(row_data[:5])}")
                except Exception as e:
                    logger.warning(f"Could not extract sample rows: {e}")
            
            column_examples = []
            try:
                for col in df.columns[:10]:
                    try:
                        unique_values = df[col].unique().head(5).to_list()
                        if unique_values:
                            examples = []
                            for v in unique_values:
                                if v is not None:
                                    try:
                                        str_v = str(v)
                                        if isinstance(str_v, bytes):
                                            str_v = str_v.decode('utf-8', errors='replace')
                                        examples.append(str_v[:20])
                                    except Exception:
                                        examples.append("[encoding_error]")
                            if examples:
                                column_examples.append(f"{col}: {', '.join(examples)}")
                    except Exception as e:
                        column_examples.append(f"{col}: [error_reading_values]")
            except Exception as e:
                logger.warning(f"Could not extract column examples: {e}")
            
            enhanced_parts = [basic_context]
            
            # Add column type information for better AI understanding
            column_info = []
            try:
                for col in df.columns:
                    col_type = str(df[col].dtype)
                    if col_type in ['Int64', 'Float64', 'Int32', 'Float32']:
                        column_info.append(f"NUMERIC: {col} ({col_type})")
                    elif col_type in ['Utf8', 'Categorical']:
                        column_info.append(f"CATEGORICAL: {col} ({col_type})")
                    elif col_type in ['Date', 'Datetime']:
                        column_info.append(f"TEMPORAL: {col} ({col_type})")
                    else:
                        column_info.append(f"OTHER: {col} ({col_type})")
            except Exception as e:
                logger.warning(f"Could not extract column types: {e}")
            
            if column_info:
                enhanced_parts.append("\nCOLUMN TYPES (use these exact names in dashboard):")
                enhanced_parts.extend(column_info)
            
            if sample_rows:
                enhanced_parts.append("\nData Samples:")
                enhanced_parts.extend(sample_rows)
            
            if column_examples:
                enhanced_parts.append("\nColumn Value Examples:")
                enhanced_parts.extend(column_examples)
            
            return "\n".join(enhanced_parts)
            
        except Exception as e:
            logger.warning(f"Could not read data samples for context: {e}")
            return basic_context + "\n\nNote: Could not read data samples due to encoding issues, using metadata only."

    def _find_safe_column_name(self, df: pl.DataFrame, requested_name: str) -> Optional[str]:
        """Finds the actual column name in a DataFrame, ignoring case, spaces, and underscores."""
        if not requested_name: return None
        df_cols_map = {c.lower().replace("_", "").replace(" ", ""): c for c in df.columns}
        clean_requested_name = requested_name.lower().replace("_", "").replace(" ", "")
        result = df_cols_map.get(clean_requested_name)
        logger.info(f"Column mapping: '{requested_name}' -> '{clean_requested_name}' -> '{result}'")
        return result

    async def _load_dataset_for_analysis(self, file_path: str) -> pl.DataFrame:
        """Load dataset for QUIS analysis"""
        try:
            file_extension = file_path.split('.')[-1].lower()
            
            if file_extension in ['xlsx', 'xls']:
                df = pl.read_excel(file_path)
                logger.info(f"Successfully loaded Excel file for QUIS analysis: {file_path}")
            elif file_extension == 'csv':
                encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                df = None
                for encoding in encodings_to_try:
                    try:
                        df = pl.read_csv(
                            file_path, 
                            encoding=encoding,
                            truncate_ragged_lines=True,
                            ignore_errors=True
                        )
                        logger.info(f"Successfully loaded CSV with encoding: {encoding}")
                        break
                    except UnicodeDecodeError as e:
                        logger.warning(f"Failed to load CSV with encoding '{encoding}': {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Unexpected error loading CSV with '{encoding}': {e}")
                        continue
                
                if df is None:
                    raise Exception("Could not read CSV file with any supported encoding.")
            elif file_extension == 'json':
                df = pl.read_json(file_path)
                logger.info(f"Successfully loaded JSON file for QUIS analysis: {file_path}")
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
            
            logger.info(f"Loaded dataset with {len(df)} rows and {len(df.columns)} columns for QUIS analysis")
            return df
            
        except Exception as e:
            logger.error(f"Failed to load dataset for analysis: {e}")
            raise e

    def _create_dual_layer_response(self, ai_content: str, query: str, dataset_doc: Dict) -> Dict[str, str]:
        """Creates a dual-layer response with simple summary and technical details."""
        try:
            # Generate simple summary using a prompt
            summary_prompt = f"""
            Convert this technical AI response into a simple, user-friendly summary:
            
            Original Response: {ai_content}
            
            Requirements:
            - Use everyday language, avoid jargon
            - Focus on key takeaways (2-3 main points)
            - Keep it under 100 words
            - Make it actionable and clear
            - Remove technical details and statistics
            
            Simple Summary:
            """
            
            # Create specific summary and contextual technical details
            summary = self._extract_simple_summary(ai_content, query)
            technical_details = self._create_contextual_technical_details(ai_content, query, dataset_doc)
            
            return {
                "summary": summary,
                "technical_details": technical_details
            }
            
        except Exception as e:
            logger.error(f"Failed to create dual-layer response: {e}")
            # Fallback to original content
            return {
                "summary": ai_content,
                "technical_details": ai_content
            }
    
    def _extract_simple_summary(self, ai_content: str, query: str) -> str:
        """Extracts a specific, actionable summary from the technical AI response."""
        query_lower = query.lower()
        content_lower = ai_content.lower()
        
        # For analytical queries, provide specific, actionable insights
        if any(keyword in query_lower for keyword in ["analyze", "insights", "patterns", "trends"]):
            if "correlation" in content_lower and "balls" in content_lower:
                # Neutral summary for correlation mentions that reference 'balls' to avoid sports-specific framing
                return "The analysis indicates a positive relationship between the referenced variables; inspect the original columns for practical implications."
            elif "distribution" in content_lower and "skewed" in content_lower:
                return "Your data distribution appears skewed, with a few extreme values affecting the mean. Consider using median or inspecting outliers to better understand typical behavior."
            elif "null" in content_lower or "missing" in content_lower:
                return "I found some missing data that could affect your analysis. Consider cleaning the dataset or checking data quality before making important decisions."
            elif "outliers" in content_lower:
                return "There are some unusual data points that might be errors or exceptional cases. Review these outliers to ensure your analysis is based on reliable data."
            else:
                return "I found specific patterns in your data that can guide better decision-making. The insights show clear relationships you can use to improve performance."
        
        # For chart requests, provide specific explanation
        elif any(keyword in query_lower for keyword in ["chart", "graph", "visualization", "show"]):
            if "bar" in content_lower:
                return "I've created a bar chart showing the key comparisons in your data. Use this to identify which categories perform best and focus your efforts there."
            elif "line" in content_lower:
                return "I've created a line chart showing trends over time. This helps you see if performance is improving, declining, or staying consistent."
            elif "pie" in content_lower:
                return "I've created a pie chart showing how your data is distributed across categories. This helps you understand the relative importance of each segment."
            else:
                return "I've created a visualization that clearly shows the key relationships in your data. Use this chart to make informed decisions."
        
        # For specific data questions - provide direct answers
        elif "least" in query_lower and "runs" in query_lower:
            # Look for the minimum runs value in the content
            import re
            min_runs_match = re.search(r'(\d+\.?\d*)\s*runs?', content_lower)
            if min_runs_match:
                min_runs = min_runs_match.group(1)
                return f"The least amount of runs is {min_runs}. This represents a very brief innings, likely an early dismissal or a quick single."
            else:
                return "The least amount of runs is very low (close to 0), indicating some batsmen had very brief innings."
        
        elif "most" in query_lower and "runs" in query_lower:
            # Look for the maximum runs value
            import re
            max_runs_match = re.search(r'(\d+\.?\d*)\s*runs?', content_lower)
            if max_runs_match:
                max_runs = max_runs_match.group(1)
                return f"The highest runs scored is {max_runs}. This represents an exceptional batting performance."
            else:
                return "The highest runs scored is quite high, showing some exceptional batting performances."
        
        elif "average" in query_lower and "runs" in query_lower:
            # Look for average runs
            import re
            avg_match = re.search(r'average.*?(\d+\.?\d*)', content_lower)
            if avg_match:
                avg_runs = avg_match.group(1)
                return f"The average runs per batsman is {avg_runs}. This gives you a baseline for typical performance."
            else:
                return "The average runs per batsman varies, with most players scoring in a typical range."
        
        elif "runs" in query_lower and "batsman" in query_lower:
            return "The content highlights relationships related to individual performance metrics; review the specific columns mentioned for actionable insights."
        elif "average" in query_lower and "strike" in query_lower:
            return "The analysis suggests a relationship between average-style metrics and rate-style metrics; validate these findings against the original columns for practical significance."
        
        # Default: try to extract the main answer from the content
        else:
            # Clean the content of any HTML markup that might be present
            import re
            clean_content = re.sub(r'<[^>]+>', '', ai_content)  # Remove HTML tags
            clean_content_lower = clean_content.lower()
            
            # Look for specific numbers or facts in the clean content
            numbers = re.findall(r'(\d+\.?\d*)', clean_content_lower)
            if numbers:
                return f"Based on your data, the key numbers are: {', '.join(numbers[:3])}. These represent the main values in your dataset."
            else:
                return "I've analyzed your data and found some interesting insights. The patterns show clear relationships that can help with decision-making."
    
    def _create_contextual_technical_details(self, ai_content: str, query: str, dataset_doc: Dict) -> str:
        """Creates contextual technical details that supplement the simple summary."""
        # Clean HTML markup from the AI content
        import re
        clean_ai_content = re.sub(r'<[^>]+>', '', ai_content)  # Remove HTML tags
        
        query_lower = query.lower()
        content_lower = clean_ai_content.lower()
        
        # Get dataset context
        dataset_name = dataset_doc.get("name", "your dataset")
        column_metadata = dataset_doc.get("metadata", {}).get("column_metadata", [])
        available_columns = [col.get("name", "") for col in column_metadata if col.get("name")]
        
        # For analytical queries, provide contextual technical details
        if any(keyword in query_lower for keyword in ["analyze", "insights", "patterns", "trends"]):
            if "null" in content_lower or "missing" in content_lower:
                # Extract specific numbers if mentioned
                null_matches = re.findall(r'(\d+)\s*(?:null|missing)', content_lower)
                null_count = null_matches[0] if null_matches else "some"
                
                return f"""Technical Analysis:
We found {null_count} missing records in your dataset. This could affect the accuracy of your analysis, especially for averages and correlations. 

Recommendation: Review the data collection process or clean the dataset before making important decisions. Consider using median instead of mean for calculations when dealing with missing values.

Dataset Context: {dataset_name} contains {len(available_columns)} columns: {', '.join(available_columns[:5])}{'...' if len(available_columns) > 5 else ''}"""
            
            elif "correlation" in content_lower and "balls" in content_lower:
                return f"""Technical Analysis:
The correlation analysis references two variables that appear together in the content, suggesting a potential predictive relationship. Validate the relationship using the original dataset columns and consider domain context when interpreting the result.

Dataset Context: {dataset_name} contains {len(available_columns)} columns: {', '.join(available_columns[:5])}{'...' if len(available_columns) > 5 else ''}"""
            
            elif "distribution" in content_lower and "skewed" in content_lower:
                return f"""Technical Analysis:
The data distribution shows a right-skewed pattern, meaning there are a few exceptional high performers and many average performers. This is common in sports performance data.

Impact: The outliers (top performers) significantly influence the average, so consider using median values for more representative insights.

Dataset Context: {dataset_name} contains {len(available_columns)} columns: {', '.join(available_columns[:5])}{'...' if len(available_columns) > 5 else ''}"""
            
            else:
                return f"""Technical Analysis:
{clean_ai_content}

Dataset Context: {dataset_name} contains {len(available_columns)} columns: {', '.join(available_columns[:5])}{'...' if len(available_columns) > 5 else ''}"""
        
        # For chart requests, provide technical context
        elif any(keyword in query_lower for keyword in ["chart", "graph", "visualization", "show"]):
            return f"""Technical Analysis:
{clean_ai_content}

Visualization Context: The chart uses data from {dataset_name} with {len(available_columns)} columns. The visualization method was selected based on the data types and relationships present in your dataset."""
        
        # Default technical response with context
        else:
            return f"""Technical Analysis:
{clean_ai_content}

Dataset Context: {dataset_name} contains {len(available_columns)} columns: {', '.join(available_columns[:5])}{'...' if len(available_columns) > 5 else ''}"""

    def _generate_quis_response(self, quis_results: Dict, query: str) -> str:
        """Generate AI response based on QUIS analysis results"""
        try:
            basic_insights = quis_results.get("basic_insights", [])
            deep_insights = quis_results.get("deep_insights", [])
            
            if not deep_insights and not basic_insights:
                return "I analyzed your data but didn't find any significant patterns that vary across segments. The data appears to be relatively uniform across different categories and regions."
            
            response_parts = []
            
            if "patterns stronger in specific segments" in query.lower():
                response_parts.append("Based on my subspace analysis, I found several patterns that become much stronger in specific segments:")
            elif "hidden patterns" in query.lower():
                response_parts.append("I discovered several hidden patterns in your data:")
            else:
                response_parts.append("Here are the key insights from my analysis:")
            
            if deep_insights:
                for i, insight in enumerate(deep_insights[:3], 1):
                    insight_type = insight.get("type", "unknown")
                    description = insight.get("description", "")
                    
                    if insight_type == "subspace_correlation":
                        subspace = insight.get("subspace", {})
                        original_corr = insight.get("original_correlation", 0)
                        subspace_corr = insight.get("subspace_correlation", 0)
                        improvement = insight.get("strength_improvement", "")
                        
                        subspace_str = " and ".join([f"{k}={v}" for k, v in subspace.items()])
                        response_parts.append(
                            f"{i}. **Subspace Correlation**: The correlation between variables is {original_corr:.2f} overall, "
                            f"but becomes {subspace_corr:.2f} ({improvement}) in the {subspace_str} segment, "
                            f"suggesting significant regional/category effects."
                        )
                    
                    elif insight_type == "category_specific_pattern":
                        category = insight.get("category", {})
                        pattern_desc = insight.get("pattern_description", "")
                        response_parts.append(
                            f"{i}. **Category-Specific Pattern**: {pattern_desc}"
                        )
                    
                    elif insight_type == "temporal_subspace_trend":
                        subspace = insight.get("subspace", {})
                        trend_strength = insight.get("trend_strength", 0)
                        response_parts.append(
                            f"{i}. **Temporal Pattern**: {trend_strength:.2f}x stronger trends found in {subspace} segment."
                        )
            
            elif basic_insights:
                for i, insight in enumerate(basic_insights[:2], 1):
                    insight_type = insight.get("type", "unknown")
                    if insight_type == "correlation":
                        columns = insight.get("columns", [])
                        value = insight.get("value", 0)
                        if len(columns) >= 2:
                            response_parts.append(
                                f"{i}. **Correlation**: {columns[0]} and {columns[1]} show {value:.2f} correlation."
                            )
            
            if deep_insights:
                response_parts.append(
                    "\n**Strategic Implications**: These subspace insights reveal hidden opportunities - "
                    "focus on the segments showing stronger patterns for competitive advantage."
                )
            
            return "\n".join(response_parts)
            
        except Exception as e:
            logger.error(f"Failed to generate QUIS response: {e}")
            return "I found some interesting patterns in your data, but encountered an error formatting the detailed insights. Please try asking about specific aspects of the analysis."

    def _smart_chart_selection(self, column_metadata: List[Dict], query_lower: str) -> str:
        """Intelligently selects the most appropriate chart type based on dataset structure and query context."""
        
        numeric_cols = [col for col in column_metadata if col.get("type") == "numeric"]
        categorical_cols = [col for col in column_metadata if col.get("type") == "categorical"]
        date_cols = [col for col in column_metadata if "date" in col.get("name", "").lower() or "time" in col.get("name", "").lower()]
        
        has_important_keywords = any(word in query_lower for word in ["important", "useful", "best", "most", "key", "insight"])
        has_multiple_keywords = any(word in query_lower for word in ["different", "various", "multiple", "all", "other", "alternative", "types"])
        has_exploration_keywords = any(word in query_lower for word in ["can", "generate", "create", "show", "visualize"])
        
        avoid_bar = "other than bar" in query_lower or "not bar" in query_lower or "alternative to bar" in query_lower
        avoid_pie = "other than pie" in query_lower or "not pie" in query_lower or "alternative to pie" in query_lower
        
        logger.info(f"Smart selection: {len(numeric_cols)} numeric, {len(categorical_cols)} categorical, {len(date_cols)} date cols")
        logger.info(f"Query context: important={has_important_keywords}, multiple={has_multiple_keywords}, exploration={has_exploration_keywords}")
        logger.info(f"Avoid preferences: bar={avoid_bar}, pie={avoid_pie}")
        
        if has_important_keywords or has_multiple_keywords or has_exploration_keywords:
            if len(date_cols) > 0 and len(numeric_cols) > 0:
                return "line"
            elif len(categorical_cols) > 0 and len(numeric_cols) > 0:
                if avoid_bar:
                    return "line" if len(date_cols) > 0 else "scatter" if len(numeric_cols) > 1 else "histogram"
                return "bar"
            elif len(numeric_cols) > 1:
                return "scatter"
            elif len(numeric_cols) > 0:
                return "histogram"
            else:
                if avoid_pie:
                    return "bar" if len(categorical_cols) > 0 else "line"
                return "pie"
        
        if len(date_cols) > 0 and len(numeric_cols) > 0:
            return "line"
        elif len(categorical_cols) > 0 and len(numeric_cols) > 0:
            return "bar"
        elif len(numeric_cols) > 1:
            return "scatter"
        elif len(numeric_cols) > 0:
            return "histogram"
        else:
            return "pie"
        
    async def generate_ai_dashboard(self, dataset_id: str, user_id: str, force_regenerate: bool = False) -> Dict[str, Any]:
        """Orchestrates DYNAMIC AI dashboard generation with SERVER-SIDE data hydration."""
        try:
            query = {"_id": dataset_id, "user_id": user_id}
            dataset_doc = await self.db.datasets.find_one(query)
            if not dataset_doc or not dataset_doc.get("metadata"):
                raise HTTPException(status_code=404, detail="Dataset not ready.")
        except Exception:
            raise HTTPException(status_code=404, detail="Dataset not found.")

        context_str = self._create_enhanced_llm_context(dataset_doc["metadata"], dataset_doc["file_path"])
        chart_ids = [chart['id'] for chart in self.chart_definitions.values()]
        factory = PromptFactory(dataset_context=context_str)
        prompt = factory.get_prompt(PromptType.DASHBOARD_DESIGNER, chart_options=chart_ids)
        
        layout_response = await self._call_ollama(prompt, model_role="visualization_engine", expect_json=True)

        if "error" in layout_response or "dashboard" not in layout_response:
            raise HTTPException(status_code=500, detail="AI failed to generate a valid dashboard layout.")
        
        blueprint = layout_response["dashboard"]
        if "components" not in blueprint:
            raise HTTPException(status_code=500, detail="AI-generated dashboard is missing 'components'.")

        df = await self._load_dataset_for_analysis(dataset_doc["file_path"])
        
        hydrated_components = []
        for component in blueprint.get("components", []):
            if not isinstance(component, dict):
                logger.warning(f"Skipping component because it's not a dict: {repr(component)[:200]}")
                continue
            try:
                hydrated_component = component.copy()
                config = component.get("config", {})
                ctype = component.get("type")
                if ctype == "kpi":
                    hydrated_component["value"] = self._hydrate_kpi_data(df, config)
                elif ctype == "chart":
                    hydrated_component["chart_data"] = self._hydrate_chart_data(df, config)
                elif ctype == "table":
                    hydrated_component["table_data"] = self._hydrate_table_data(df, config)

                hydrated_components.append(hydrated_component)
            except Exception as e:
                title = component.get('title') if isinstance(component, dict) else None
                logger.warning(f"Could not populate component '{title}'. Error: {e}")

        return {"layout_grid": blueprint.get("layout_grid", "repeat(4, 1fr)"), "components": hydrated_components}


    def _hydrate_kpi_data(self, df: pl.DataFrame, config: Dict) -> Any:
        requested_col = config.get("column")
        agg = config.get("aggregation")
        if not agg: return "N/A"
        if agg == "count": return len(df)

        safe_col = self._find_safe_column_name(df, requested_col)
        if not safe_col:
            logger.warning(f"KPI hydration failed: Could not find column like '{requested_col}'.")
            return "N/A"

        if agg in ["sum", "mean"] and df[safe_col].dtype not in pl.NUMERIC_DTYPES:
            logger.warning(f"KPI hydration failed: Column '{safe_col}' is not numeric for '{agg}'.")
            return "N/A"
            
        if agg == "sum": value = df.select(pl.sum(safe_col)).item()
        elif agg == "mean": value = df.select(pl.mean(safe_col)).item()
        elif agg == "nunique": value = df.select(pl.n_unique(safe_col)).item()
        else: value = "N/A"

        if isinstance(value, (int, float)):
            # Format based on column context - no currency symbols for cricket data
            if value >= 1000: 
                return f"{value:,.0f}"
            return round(value, 1)
        return value

    def _hydrate_chart_data(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """
        Robustly generates Plotly-ready chart traces based on a chart config.
        Supports: bar, line, scatter, pie, histogram, box_plot, grouped_bar_chart, treemap, heatmap
        """
        if not config:
            logger.warning("No chart config provided")
            return []

        chart_type = config.get("chart_type", "bar")
        aggregation = config.get("aggregation") or "none"
        columns = config.get("columns") or []
        group_by_raw = config.get("group_by")

        chart_type_mapping = {
            "bar_chart": "bar",
            "line_chart": "line", 
            "pie_chart": "pie",
            "scatter_plot": "scatter",
            "box_plot": "box_plot",
            "grouped_bar_chart": "grouped_bar_chart",
            "histogram": "histogram"
        }
        chart_type = chart_type_mapping.get(chart_type, chart_type)

        logger.info(f"Chart type: {chart_type}, Columns: {columns}, Aggregation: {aggregation}")

        safe_columns = [self._find_safe_column_name(df, c) for c in columns if c]
        safe_columns = [c for c in safe_columns if c]
        
        logger.info(f"Safe columns found: {safe_columns}")

        if chart_type in ["bar", "line", "scatter"] and len(safe_columns) < 2:
            logger.warning(f"Not enough columns for {chart_type} chart. Need 2, got {len(safe_columns)}")
            return []
        elif chart_type == "pie" and len(safe_columns) < 1:
            logger.warning(f"Not enough columns for {chart_type} chart. Need at least 1, got {len(safe_columns)}")
            return []

        def aggregate_data(x_col, y_col, agg_method="none"):
            logger.info(f"Aggregating data: x_col={x_col}, y_col={y_col}, agg_method={agg_method}")
            
            if x_col not in df.columns or y_col not in df.columns:
                logger.error(f"Columns not found: x_col={x_col}, y_col={y_col}. Available columns: {df.columns}")
                return []
            
            x_null_count = df[x_col].null_count()
            y_null_count = df[y_col].null_count()
            logger.info(f"Null values - {x_col}: {x_null_count}, {y_col}: {y_null_count}")
            
            filtered_df = df.filter(pl.col(x_col).is_not_null() & pl.col(y_col).is_not_null())
            logger.info(f"After filtering nulls: {len(filtered_df)} rows")
            
            if len(filtered_df) == 0:
                logger.warning("No data after filtering null values")
                return []
            
            x_dtype = filtered_df[x_col].dtype
            y_dtype = filtered_df[y_col].dtype
            logger.info(f"Data types - {x_col}: {x_dtype}, {y_col}: {y_dtype}")
            
            # handle line charts differently for time series
            if chart_type == "line" and x_dtype in [pl.Date, pl.Datetime, pl.Utf8]:
                logger.info("Time series detected, preserving individual time points")
                if agg_method == "none":
                    result = filtered_df.select([x_col, y_col]).sort(x_col).to_dicts()
                else:
                    if agg_method == "sum":
                        result = filtered_df.group_by(x_col).agg(pl.sum(y_col).alias("y")).rename({x_col: "x"}).sort("x").to_dicts()
                    elif agg_method == "mean":
                        result = filtered_df.group_by(x_col).agg(pl.mean(y_col).alias("y")).rename({x_col: "x"}).sort("x").to_dicts()
                    elif agg_method == "count":
                        result = filtered_df.group_by(x_col).agg(pl.count().alias("y")).rename({x_col: "x"}).sort("x").to_dicts()
                    else:
                        result = filtered_df.group_by(x_col).agg(pl.sum(y_col).alias("y")).rename({x_col: "x"}).sort("x").to_dicts()
            else:
                if agg_method == "sum":
                    result = filtered_df.group_by(x_col).agg(pl.sum(y_col).alias("y")).rename({x_col: "x"}).sort("y", descending=True).to_dicts()
                elif agg_method == "mean":
                    result = filtered_df.group_by(x_col).agg(pl.mean(y_col).alias("y")).rename({x_col: "x"}).sort("y", descending=True).to_dicts()
                elif agg_method == "count":
                    result = filtered_df.group_by(x_col).agg(pl.count().alias("y")).rename({x_col: "x"}).sort("y", descending=True).to_dicts()
                else:
                    logger.info(f"No aggregation specified, defaulting to sum by {x_col}")
                    result = filtered_df.group_by(x_col).agg(pl.sum(y_col).alias("y")).rename({x_col: "x"}).sort("y", descending=True).to_dicts()
            
            logger.info(f"Aggregation result: {len(result)} rows")
            if result:
                logger.info(f"Sample data: {result[:3]}")
            
            return result

        traces = []

        if chart_type == "pie":
            if len(safe_columns) == 1:
                logger.info(f"Pie chart with single column: counting occurrences of {safe_columns[0]}")
                rows = df.group_by(safe_columns[0]).agg(pl.count().alias("count")).sort("count", descending=True).to_dicts()
                trace = {"labels": [r[safe_columns[0]] for r in rows], "values": [r["count"] for r in rows], "type": "pie"}
                logger.info(f"Pie chart data: {len(rows)} categories")
            elif len(safe_columns) >= 2:
                rows = aggregate_data(safe_columns[0], safe_columns[1], aggregation)
                trace = {"labels": [r["x"] for r in rows], "values": [r["y"] for r in rows], "type": "pie"}
                logger.info(f"Pie chart data: {len(rows)} categories using columns {safe_columns[0]} and {safe_columns[1]}")
            else:
                logger.warning("Not enough columns for pie chart")
                return []
            
            traces.append(trace)

        elif chart_type in ["bar", "line", "scatter"]:
            if len(safe_columns) >= 2:
                rows = aggregate_data(safe_columns[0], safe_columns[1], aggregation)
            else:
                logger.warning(f"Not enough columns for {chart_type} chart")
                return []
            logger.info(f"Generated {len(rows)} rows for {chart_type} chart")
            
            if rows:
                trace_type = "bar" if chart_type == "bar" else "scatter"
                mode = "lines+markers" if chart_type == "line" else "markers"
                trace = {"x": [r["x"] for r in rows], "y": [r["y"] for r in rows], "type": trace_type}
                if chart_type in ["line", "scatter"]:
                    trace["mode"] = mode
                logger.info(f"Created trace: {trace_type} with {len(trace['x'])} data points")
                traces.append(trace)
            else:
                logger.warning(f"No data rows generated for {chart_type} chart")

        elif chart_type == "histogram":
            numeric_col = next((c for c in safe_columns if df[c].dtype in pl.NUMERIC_DTYPES), None)
            if numeric_col:
                traces.append({"x": df[numeric_col].to_list(), "type": "histogram"})
        elif chart_type == "box_plot":
            traces = []
            cat_col = next((c for c in safe_columns if df[c].dtype in pl.CATEGORICAL_DTYPES), None)
            num_col = next((c for c in safe_columns if df[c].dtype in pl.NUMERIC_DTYPES), None)
            print("cat_col:", cat_col)
            print("num_col:", num_col)

            if cat_col and num_col:
                categories = df[cat_col].unique().to_list()
                print("Unique Categories:", categories[:10])
                for cat in categories:
                    traces.append({
                        "y": df.filter(pl.col(cat_col) == cat)[num_col].to_list(),
                        "type": "box",
                        "name": str(cat)
                    })
            return traces

        elif chart_type == "grouped_bar_chart":
            if group_by_raw:
                group_by_cols = [group_by_raw] if isinstance(group_by_raw, str) else group_by_raw
                safe_group_by = [self._find_safe_column_name(df, c) for c in group_by_cols if c]
                safe_group_by = [c for c in safe_group_by if c]
                if len(safe_group_by) >= 2 and len(safe_columns) >= 1:
                    pivot = df.pivot(index=safe_group_by[0], columns=safe_group_by[1], values=safe_columns[0], aggregate_function="sum").fill_null(0)
                    for col in pivot.columns[1:]:
                        traces.append({"x": pivot[pivot.columns[0]].to_list(), "y": pivot[col].to_list(), "type": "bar", "name": col})


        return traces


    def _hydrate_table_data(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Robustly populates table data based on LLM config."""
        columns = config.get("columns", [])
        if not columns: return []
        safe_columns = [self._find_safe_column_name(df, c) for c in columns if c]
        safe_columns = [c for c in safe_columns if c]
        if not safe_columns: return []
        return df.select(safe_columns).head(10).to_dicts()

    def _calculate_question_confidence(self, analysis_type: str, dataset_metadata: Dict) -> float:
            """Calculates a confidence score for a QUIS question based on data characteristics."""
            base_confidence = 0.40
            data_quality = dataset_metadata.get('data_quality', {})
            completeness = data_quality.get('completeness', 100)
            quality_factor = (completeness / 100.0) * 0.1

            overview = dataset_metadata.get('dataset_overview', {})
            total_rows = overview.get('total_rows', 0)
            size_factor = min(1.0, total_rows / 10000) * 0.1

            column_metadata = dataset_metadata.get('column_metadata', [])
            typed_cols = [self._determine_data_type_from_meta(col) for col in column_metadata]
            
            num_numeric = sum(1 for c in typed_cols if c['type'] == DataType.NUMERIC)
            num_categorical = sum(1 for c in typed_cols if c['type'] == DataType.CATEGORICAL)
            num_temporal = sum(1 for c in typed_cols if c['type'] == DataType.TEMPORAL)

            type_factor = 0.0
            if analysis_type == 'correlation_analysis' and num_numeric >= 2:
                type_factor = 0.4
            elif analysis_type in ['performance_analysis', 'distribution_analysis'] and num_categorical >= 1 and num_numeric >= 1:
                type_factor = 0.3
            elif analysis_type == 'pattern_analysis':
                if num_temporal >= 1 and num_numeric >= 1:
                    type_factor = 0.35
                elif num_numeric >= 1:
                    type_factor = 0.2
            elif analysis_type == 'quality_analysis':
                type_factor = 0.4

            final_confidence = base_confidence + quality_factor + size_factor + type_factor
            return round(max(0.1, min(0.95, final_confidence)), 2)

    async def _generate_llm_answer(self, question: str, dataset_metadata: Dict, dataset_name: str) -> str:
        context = self._create_llm_context_string(dataset_metadata)
        
        factory = PromptFactory(dataset_context=context)
        prompt = factory.get_prompt(PromptType.QUIS_ANSWER, question=question)
        return await self._call_ollama(prompt, model_role="summary_engine")



ai_service = AIService()