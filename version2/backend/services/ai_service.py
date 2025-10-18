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
        # self.ollama_url = settings.OLLAMA_BASE_URL.rstrip('/')
        self.http_client = httpx.AsyncClient(timeout=90.0, follow_redirects=True)
        
        self.chart_definitions = {chart['id']: chart for chart in CHART_DEFINITIONS}
        self.quis_question_templates = {
            'pattern_analysis': ["What are the main patterns or trends in this dataset?"],
            'performance_analysis': ["Which categories show the highest or lowest performance?"],
            'correlation_analysis': ["What are the most significant relationships between variables?"],
        }

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
        """A centralized router for calling Ollama that selects the correct specialized model."""
        model_info = settings.MODELS.get(model_role)
        if not model_info:
            raise ValueError(f"Invalid model role specified: {model_role}")
        
        model_name = model_info["model"]
        base_url = model_info["base_url"].rstrip('/')

        logger.info(f"Routing request to model '{model_name}' at '{base_url}' for role '{model_role}'.")

        payload = {"model": model_name, "prompt": prompt, "stream": False}
        if expect_json:
            payload["format"] = "json"

        try:
            response = await self.http_client.post(f"{base_url}/api/generate", json=payload)
            response.raise_for_status()
            response_data = response.json()
            
            if expect_json:
                json_string = response_data.get("response", "{}")
                # FIXED: Robust JSON parsing with fallback for LLM hallucinations
                try:
                    return json.loads(json_string)
                except json.JSONDecodeError as e:
                    logger.error(f"LLM '{model_name}' returned invalid JSON for role '{model_role}'. Response: {json_string[:200]}.... Error: {e}")
                    return {"error": "llm_json_parse_failed", "raw": json_string[:500], "fallback": True}  # Truncated raw for debugging
            else:
                return response_data.get("response", "").strip()
        except json.JSONDecodeError as e:
            logger.error(f"LLM '{model_name}' returned invalid JSON for role '{model_role}'. Response: {json_string}. Error: {e}")
            return {"response_text": "I had a trouble formatting my response."} if expect_json else "I had a formatting error."
        except httpx.RequestError as e:
            logger.error(f"Ollama request to model '{model_name}' failed: {e}")
            if expect_json:
                return {
                    "response_text": f"My '{model_role}' engine is currently unavailable. Please try again later or check your AI service configuration.",
                    "error": "ai_service_unavailable",
                    "fallback": True
                }
            else:
                return f"My '{model_role}' engine is currently unavailable. Please try again later or check your AI service configuration."
            
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
            
            layout_response = await self._call_ollama(prompt, model_role="layout_designer", expect_json=True)
            blueprint = layout_response.get("dashboard")
            if not blueprint or "components" not in blueprint:
                logger.error(f"AI dashboard generation failed. Response: {layout_response}")
                raise HTTPException(status_code=500, detail="AI failed to design a valid dashboard layout.")

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
            try:
                hydrated_component = component.copy()
                if component["type"] == "kpi":
                    hydrated_component["value"] = self._hydrate_kpi_data(df, component["config"])
                elif component["type"] == "chart":
                    hydrated_component["chart_data"] = self._hydrate_chart_data(df, component["config"])
                elif component["type"] == "table":
                    hydrated_component["table_data"] = self._hydrate_table_data(df, component["config"])
                
                if hydrated_component.get("value") is not None or hydrated_component.get("chart_data") or hydrated_component.get("table_data"):
                    hydrated_components.append(hydrated_component)
            except Exception as e:
                logger.warning(f"Could not populate dashboard component '{component.get('title')}'. Error: {e}", exc_info=True)

        return {"layout_grid": blueprint.get("layout_grid", "repeat(1, 1fr)"), "components": hydrated_components}

    # async def process_chat_message(self, query: str, dataset_id: str, user_id: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
    #     """Orchestrates a full conversational turn using the specialized chat_engine model."""
    #     conversation = await self._load_or_create_conversation(conversation_id, user_id, dataset_id)
    #     messages = conversation.get("messages", [])
    #     messages.append({"role": "user", "content": query})

    #     dataset_doc = await self.db.datasets.find_one({"_id": dataset_id, "user_id": user_id})
    #     if not dataset_doc or not dataset_doc.get("metadata"):
    #         raise HTTPException(status_code=409, detail="Dataset is still being processed. Please wait.")
        
    #     prompt = self._create_conversational_prompt(messages, dataset_doc["metadata"])
    #     llm_response = await self._call_ollama(prompt, model_role="chat_engine", expect_json=True)
        
    #     ai_content = llm_response.get("response_text", "I was unable to process your request.")
    #     chart_config = llm_response.get("chart_config")

    #     if chart_config:
    #         try:
    #             df = pl.read_csv(dataset_doc["file_path"])
    #             hydrated_data = self._hydrate_chart_data(df, chart_config)
    #             chart_config["data"] = hydrated_data
    #         except Exception as e:
    #             logger.error(f"Failed to hydrate chart data: {e}")
    #             ai_content += " (But I had trouble generating the data for the suggested chart.)"
    #             chart_config = None

    #     await self._save_conversation(conversation["_id"], messages + [{"role": "ai", "content": ai_content, "chart_config": chart_config}])
    #     return {"response": ai_content, "conversation_id": str(conversation["_id"]), "chart_config": chart_config}
    async def process_chat_message(self, query: str, dataset_id: str, user_id: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Processes a user query, including chart requests in natural language."""
        conversation = await self._load_or_create_conversation(conversation_id, user_id, dataset_id)
        messages = conversation.get("messages", [])
        messages.append({"role": "user", "content": query})

        # Handle both ObjectId and UUID formats
        try:
            # Try ObjectId format first
            db_query = {"_id": ObjectId(dataset_id), "user_id": user_id}
        except Exception:
            # If ObjectId fails, treat as string (UUID format)
            db_query = {"_id": dataset_id, "user_id": user_id}
        
        dataset_doc = await self.db.datasets.find_one(db_query)
        if not dataset_doc or not dataset_doc.get("metadata"):
            raise HTTPException(status_code=409, detail="Dataset is still being processed. Please wait.")

        # Check if this is an analytical query that should trigger QUIS
        query_lower = query.lower()
        analytical_keywords = [
            "patterns stronger in specific segments",
            "hidden patterns", "deep insights",
            "relationships between variables",
            "correlations that become stronger",
            "unusual statistical properties",
            "insights that emerge when we filter",
            "patterns in specific categories",
            "patterns in specific regions",
            "what drives performance differences"
        ]
        
        is_analytical_query = any(keyword in query_lower for keyword in analytical_keywords)
        
        if is_analytical_query:
            # Run QUIS analysis for analytical queries
            logger.info("Detected analytical query, running QUIS analysis...")
            try:
                df = await self._load_dataset_for_analysis(dataset_doc["file_path"])
                quis_results = analysis_service.run_quis_analysis(df)
                
                # Generate AI response based on QUIS results
                ai_content = self._generate_quis_response(quis_results, query)
                chart_config = None  # No chart for analytical responses
                
            except Exception as e:
                logger.error(f"QUIS analysis failed: {e}")
                ai_content = "I encountered an error while analyzing patterns in your data. Please try again."
                chart_config = None
        else:
            # Regular chart generation for visualization queries
            prompt = self._create_conversational_prompt(messages, dataset_doc["metadata"])
            llm_response = await self._call_ollama(prompt, model_role="chat_engine", expect_json=True)
            
            ai_content = llm_response.get("response_text", "I was unable to process your request.")
            chart_config = llm_response.get("chart_config")

        # ---------------------------
        # Enhanced chart detection logic
        # ---------------------------
        chart_keywords = {
            # Specific chart types
            "bar chart": "bar", 
            "bar graph": "bar",
            "pie chart": "pie",
            "line chart": "line",
            "line graph": "line",
            "scatter plot": "scatter",
            "histogram": "histogram",
            "box plot": "box_plot",
            "grouped bar chart": "grouped_bar_chart",
            
            # General terms - be more intelligent
            "chart": None,  # Will trigger smart selection
            "visualization": None,  # Will trigger smart selection
            "graph": None,  # Will trigger smart selection
            "plot": None,  # Will trigger smart selection
            
            # Analysis types
            "distribution": "histogram",
            "trend": "line",
            "comparison": "bar",
            "correlation": "scatter",
            "proportion": "pie",
            "breakdown": "bar",
            "outliers": "box_plot"
        }
        
        if not chart_config:
            # Check for chart-related keywords in the query
            query_lower = query.lower()
            detected_chart_type = None
            
            # Look for specific chart types
            for keyword, chart_type in chart_keywords.items():
                if keyword in query_lower:
                    detected_chart_type = chart_type
                    break
            
            # If we detected a chart request, create a basic config
            if detected_chart_type is not None:  # Allow None to trigger smart selection
                # Get available columns from dataset metadata
                column_metadata = dataset_doc.get("metadata", {}).get("column_metadata", [])
                available_columns = [col.get("name", "") for col in column_metadata if col.get("name")]
                
                # If detected_chart_type is None, use smart selection
                if detected_chart_type is None:
                    detected_chart_type = self._smart_chart_selection(column_metadata, query_lower)
                
                # Try to find appropriate columns for the chart type
                if detected_chart_type == "pie":
                    # For pie charts, prefer categorical columns
                    categorical_columns = [col.get("name", "") for col in column_metadata if col.get("type") == "categorical"]
                    if categorical_columns:
                        chart_config = {
                            "chart_type": "pie",
                            "columns": [categorical_columns[0]]  # Use first categorical column
                        }
                    else:
                        # Fallback to first available column
                        chart_config = {
                            "chart_type": "pie",
                            "columns": [available_columns[0]] if available_columns else []
                        }
                elif detected_chart_type in ["bar", "line", "scatter"]:
                    # For basic charts, use first two columns
                    chart_config = {
                        "chart_type": detected_chart_type,
                        "columns": available_columns[:2] if len(available_columns) >= 2 else available_columns,
                        "aggregation": "mean" if "average" in query_lower else "sum"
                    }
                elif detected_chart_type == "histogram":
                    # For histogram, find first numeric column
                    numeric_columns = [col.get("name", "") for col in column_metadata if col.get("type") == "numeric"]
                    if numeric_columns:
                        chart_config = {
                            "chart_type": "histogram",
                            "columns": [numeric_columns[0]]
                        }
                elif detected_chart_type == "box_plot":
                    # For box plot, find one categorical and one numeric column
                    categorical_columns = [col.get("name", "") for col in column_metadata if col.get("type") == "categorical"]
                    numeric_columns = [col.get("name", "") for col in column_metadata if col.get("type") == "numeric"]
                    if categorical_columns and numeric_columns:
                        chart_config = {
                            "chart_type": "box_plot",
                            "columns": [categorical_columns[0], numeric_columns[0]]
                        }
                
                # Log the detected chart configuration
                if chart_config:
                    logger.info(f"Auto-detected chart request: {chart_config}")
        
        # Additional fallback: if no chart was detected but the response mentions creating a chart
        if not chart_config and any(word in ai_content.lower() for word in ["chart", "graph", "visualization", "plot", "diagram"]):
            logger.info("Response mentions chart but no config provided, attempting fallback detection")
            # Try to create a simple bar chart as fallback
            column_metadata = dataset_doc.get("metadata", {}).get("column_metadata", [])
            available_columns = [col.get("name", "") for col in column_metadata if col.get("name")]
            if len(available_columns) >= 2:
                chart_config = {
                    "chart_type": "bar",
                    "columns": available_columns[:2],
                    "aggregation": "mean"
                }
                logger.info(f"Created fallback chart config: {chart_config}")

        # ---------------------------
        # Hydrate chart data
        # ---------------------------
        if chart_config:
            try:
                logger.info(f"Processing chart config: {chart_config}")
                df = pl.read_csv(dataset_doc["file_path"])
                logger.info(f"Loaded dataset with {len(df)} rows and {len(df.columns)} columns")
                logger.info(f"Dataset columns: {df.columns}")
                
                hydrated_data = self._hydrate_chart_data(df, chart_config)
                logger.info(f"Generated chart data with {len(hydrated_data)} traces")
                
                if hydrated_data:
                    chart_config["data"] = hydrated_data
                    logger.info(f"Successfully generated chart: {chart_config.get('chart_type')} with data")
                else:
                    logger.warning("Chart hydration returned empty data")
                    ai_content += " (I tried to generate a chart but couldn't find suitable data.)"
                    chart_config = None
            except Exception as e:
                logger.error(f"Failed to hydrate chart data: {e}", exc_info=True)
                ai_content += " (But I had trouble generating the data for the suggested chart.)"
                chart_config = None

        await self._save_conversation(conversation["_id"], messages + [{"role": "ai", "content": ai_content, "chart_config": chart_config}])
        return {"response": ai_content, "conversation_id": str(conversation["_id"]), "chart_config": chart_config}


    async def generate_hybrid_insights(self, dataset_id: str, user_id: str) -> Dict[str, Any]:
        """Runs statistical analysis and uses the specialized summary_engine model for interpretation."""
        # Handle both ObjectId and UUID formats
        try:
            # Try ObjectId format first
            query = {"_id": ObjectId(dataset_id), "user_id": user_id}
        except Exception:
            # If ObjectId fails, treat as string (UUID format)
            query = {"_id": dataset_id, "user_id": user_id}
        
        dataset_doc = await self.db.datasets.find_one(query)
        if not dataset_doc or not dataset_doc.get("file_path"):
            raise HTTPException(status_code=404, detail="Dataset file not found.")

        df = pl.read_csv(dataset_doc["file_path"])
        statistical_findings = analysis_service.run_all_statistical_checks(df)
        if not statistical_findings:
            return {"summary": "No significant statistical patterns were automatically detected.", "findings": []}

        context_str = self._create_llm_context_string(dataset_doc.get("metadata", {}))
        
        # Use the new PromptFactory for enhanced functionality
        factory = PromptFactory(dataset_context=context_str)
        prompt = factory.get_prompt(PromptType.INSIGHT_SUMMARIZER, statistical_findings=statistical_findings)

        summary_json = await self._call_ollama(prompt, model_role="summary_engine", expect_json=True)
        return {"summary": summary_json, "findings": statistical_findings}
        
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
        
        # Use the new PromptFactory for enhanced functionality
        factory = PromptFactory(dataset_context=dataset_context)
        return factory.get_prompt(PromptType.CONVERSATIONAL, history=messages, chart_options=chart_options)
        
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

    def _create_llm_context_string(self, dataset_metadata: Dict) -> str:
        overview = dataset_metadata.get('dataset_overview', {})
        columns = dataset_metadata.get('column_metadata', [])
        statistical_findings = dataset_metadata.get('statistical_findings', {})
        
        # Enhanced column descriptions with sample values
        col_strings = []
        for c in columns[:15]:  # Limit to first 15 columns for context
            col_name = c.get('name', 'Unknown')
            col_type = c.get('type', 'Unknown')
            null_count = c.get('null_count', 0)
            col_strings.append(f"{col_name} ({col_type}, {null_count} nulls)")
        
        # Build comprehensive context
        context_parts = [
            f"Dataset Overview: {overview.get('total_rows', 'N/A')} rows, {overview.get('total_columns', 'N/A')} columns.",
            f"Column Details: {', '.join(col_strings)}"
        ]
        
        # Add statistical insights if available
        if statistical_findings:
            context_parts.append("\nStatistical Insights:")
            
            # Add data type distribution
            if 'data_types' in statistical_findings:
                data_types = statistical_findings['data_types']
                type_summary = []
                for dtype, count in data_types.items():
                    type_summary.append(f"{dtype}: {count} columns")
                context_parts.append(f"Data Types: {', '.join(type_summary)}")
            
            # Add key statistics for numeric columns
            if 'numeric_columns' in statistical_findings:
                numeric_cols = statistical_findings['numeric_columns']
                if numeric_cols:
                    context_parts.append(f"Numeric Columns: {', '.join(numeric_cols[:5])}")  # First 5 numeric columns
            
            # Add categorical columns
            if 'categorical_columns' in statistical_findings:
                categorical_cols = statistical_findings['categorical_columns']
                if categorical_cols:
                    context_parts.append(f"Categorical Columns: {', '.join(categorical_cols[:5])}")  # First 5 categorical columns
            
            # Add temporal columns
            if 'temporal_columns' in statistical_findings:
                temporal_cols = statistical_findings['temporal_columns']
                if temporal_cols:
                    context_parts.append(f"Date/Time Columns: {', '.join(temporal_cols)}")
        
        if len(columns) > 15: 
            context_parts.append(f"... and {len(columns) - 15} more columns")
        
        return "\n".join(context_parts)

    def _create_enhanced_llm_context(self, dataset_metadata: Dict, file_path: str) -> str:
        """Creates enhanced context with actual data samples for better AI understanding."""
        # Start with basic context
        basic_context = self._create_llm_context_string(dataset_metadata)
        
        try:
            # Detect file format and load accordingly
            file_extension = file_path.split('.')[-1].lower()
            
            if file_extension in ['xlsx', 'xls']:
                # Handle Excel files
                df = pl.read_excel(file_path)
                logger.info(f"Successfully loaded Excel file for context: {file_path}")
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
                    logger.error("Could not load CSV with any encoding. Skipping data samples.")
                    return basic_context
            elif file_extension == 'json':
                # Handle JSON files
                df = pl.read_json(file_path)
                logger.info(f"Successfully loaded JSON file for context: {file_path}")
            else:
                logger.warning(f"Unsupported file format for context: {file_extension}")
                return basic_context
            # Add data samples with safe string conversion
            sample_rows = []
            if len(df) > 0:
                try:
                    # Get first 3 rows as samples
                    sample_data = df.head(3)
                    for i, row in enumerate(sample_data.iter_rows(named=True)):
                        row_data = []
                        for col, value in row.items():
                            try:
                                # Safe string conversion with encoding handling
                                if value is None:
                                    str_value = "null"
                                else:
                                    str_value = str(value)
                                    # Handle encoding issues
                                    if isinstance(str_value, bytes):
                                        str_value = str_value.decode('utf-8', errors='replace')
                                    # Truncate long values
                                    if len(str_value) > 50:
                                        str_value = str_value[:47] + "..."
                                row_data.append(f"{col}: {str_value}")
                            except Exception as e:
                                row_data.append(f"{col}: [encoding_error]")
                        sample_rows.append(f"Row {i+1}: {', '.join(row_data[:5])}")  # Limit to first 5 columns
                except Exception as e:
                    logger.warning(f"Could not extract sample rows: {e}")
            
            # Add column value examples with safe handling
            column_examples = []
            try:
                for col in df.columns[:10]:  # First 10 columns
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
            
            # Combine all context
            enhanced_parts = [basic_context]
            
            if sample_rows:
                enhanced_parts.append("\nData Samples:")
                enhanced_parts.extend(sample_rows)
            
            if column_examples:
                enhanced_parts.append("\nColumn Value Examples:")
                enhanced_parts.extend(column_examples)
            
            return "\n".join(enhanced_parts)
            
        except Exception as e:
            logger.warning(f"Could not read data samples for context: {e}")
            # Return basic context with a note about the issue
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
            if file_extension == 'csv':
                df = pl.read_csv(file_path)
            elif file_extension in ['xlsx', 'xls']:
                df = pl.read_excel(file_path)
            elif file_extension == 'json':
                df = pl.read_json(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
            
            logger.info(f"Loaded dataset with {len(df)} rows and {len(df.columns)} columns for QUIS analysis")
            return df
            
        except Exception as e:
            logger.error(f"Failed to load dataset for analysis: {e}")
            raise e

    def _generate_quis_response(self, quis_results: Dict, query: str) -> str:
        """Generate AI response based on QUIS analysis results"""
        try:
            basic_insights = quis_results.get("basic_insights", [])
            deep_insights = quis_results.get("deep_insights", [])
            
            if not deep_insights and not basic_insights:
                return "I analyzed your data but didn't find any significant patterns that vary across segments. The data appears to be relatively uniform across different categories and regions."
            
            response_parts = []
            
            # Start with context
            if "patterns stronger in specific segments" in query.lower():
                response_parts.append("Based on my subspace analysis, I found several patterns that become much stronger in specific segments:")
            elif "hidden patterns" in query.lower():
                response_parts.append("I discovered several hidden patterns in your data:")
            else:
                response_parts.append("Here are the key insights from my analysis:")
            
            # Add deep insights (subspace findings)
            if deep_insights:
                for i, insight in enumerate(deep_insights[:3], 1):  # Top 3 insights
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
            
            # Add basic insights if no deep insights
            elif basic_insights:
                for i, insight in enumerate(basic_insights[:2], 1):
                    insight_type = insight.get("type", "unknown")
                    if insight_type == "correlation":
                        columns = insight.get("columns", [])
                        value = insight.get("value", 0)
                        response_parts.append(
                            f"{i}. **Correlation**: {columns[0]} and {columns[1]} show {value:.2f} correlation."
                        )
            
            # Add strategic recommendations
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
        
        # Analyze column types
        numeric_cols = [col for col in column_metadata if col.get("type") == "numeric"]
        categorical_cols = [col for col in column_metadata if col.get("type") == "categorical"]
        date_cols = [col for col in column_metadata if "date" in col.get("name", "").lower() or "time" in col.get("name", "").lower()]
        
        # Query context analysis
        has_important_keywords = any(word in query_lower for word in ["important", "useful", "best", "most", "key", "insight"])
        has_multiple_keywords = any(word in query_lower for word in ["different", "various", "multiple", "all", "other", "alternative", "types"])
        has_exploration_keywords = any(word in query_lower for word in ["can", "generate", "create", "show", "visualize"])
        
        # Check if user wants to avoid certain chart types
        avoid_bar = "other than bar" in query_lower or "not bar" in query_lower or "alternative to bar" in query_lower
        avoid_pie = "other than pie" in query_lower or "not pie" in query_lower or "alternative to pie" in query_lower
        
        logger.info(f"Smart selection: {len(numeric_cols)} numeric, {len(categorical_cols)} categorical, {len(date_cols)} date cols")
        logger.info(f"Query context: important={has_important_keywords}, multiple={has_multiple_keywords}, exploration={has_exploration_keywords}")
        logger.info(f"Avoid preferences: bar={avoid_bar}, pie={avoid_pie}")
        
        # Smart selection logic
        if has_important_keywords or has_multiple_keywords or has_exploration_keywords:
            # For important/useful queries, prioritize the most insightful chart type
            if len(date_cols) > 0 and len(numeric_cols) > 0:
                return "line"  # Time series analysis is often most valuable
            elif len(categorical_cols) > 0 and len(numeric_cols) > 0:
                if avoid_bar:
                    return "line" if len(date_cols) > 0 else "scatter" if len(numeric_cols) > 1 else "histogram"
                return "bar"  # Categorical comparison is very useful
            elif len(numeric_cols) > 1:
                return "scatter"  # Correlation analysis
            elif len(numeric_cols) > 0:
                return "histogram"  # Distribution analysis
            else:
                if avoid_pie:
                    return "bar" if len(categorical_cols) > 0 else "line"
                return "pie"  # Categorical breakdown
        
        # Default selection based on data structure
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
            if value >= 1000: return f"{value:,.0f}"
            return round(value, 1)
        return value

    # def _hydrate_chart_data(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
    #     """Robustly populates chart data based on LLM config."""
    #     aggregation = config.get("aggregation", "none")
    #     columns = config.get("columns", [])
    #     group_by_raw = config.get("group_by")
    #     chart_type = config.get("chart_type")
        
    #     if not isinstance(columns, list) or not columns: return []
        
    #     safe_columns = [self._find_safe_column_name(df, c) for c in columns if c]
    #     safe_columns = [c for c in safe_columns if c]
    #     if len(safe_columns) < len(columns):
    #         logger.warning(f"Chart hydration: Could not find all requested columns. Requested: {columns}, Found: {safe_columns}")
    #     rows = []
    #     if aggregation == "none":
    #         if len(safe_columns) < 2: return []
    #         x_col, y_col = safe_columns[0], safe_columns[1]
    #         rows = df.select([pl.col(x_col).alias("x"), pl.col(y_col).alias("y")]).drop_nulls().to_dicts()
    #     else:
    #         group_by_list = [group_by_raw] if isinstance(group_by_raw, str) else group_by_raw
    #         if not group_by_list: return []
            
    #         safe_group_by = [self._find_safe_column_name(df, c) for c in group_by_list if c]
    #         safe_group_by = [c for c in safe_group_by if c]
    #         if not safe_group_by: return []
    #         group_by_col = safe_group_by[0]
            
    #         if aggregation == "count":
    #             agg_df = df.group_by(group_by_col).agg(pl.count().alias("value"))
    #         else:
    #             numeric_col = next((c for c in safe_columns if c != group_by_col and df[c].dtype in pl.NUMERIC_DTYPES), None)
    #             if not numeric_col: return []
    #             if aggregation == "sum": agg_df = df.group_by(group_by_col).agg(pl.sum(numeric_col).alias("value"))
    #             else: agg_df = df.group_by(group_by_col).agg(pl.mean(numeric_col).alias("value"))
    #         rows =  agg_df.rename({group_by_col: "x", "value": "y"}).sort("y", descending=True).head(20).to_dicts()

    #     if not rows:
    #         return []

    #     trace = {
    #         "x": [r["x"] for r in rows],
    #         "y": [r["y"] for r in rows],
    #         "type": chart_type
    #     }
    #     print("Plotly trace data:", trace)
    #     return [trace]
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

        # Normalize chart type (handle variations like "bar_chart" -> "bar")
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

        # Validate columns
        safe_columns = [self._find_safe_column_name(df, c) for c in columns if c]
        safe_columns = [c for c in safe_columns if c]
        
        logger.info(f"Safe columns found: {safe_columns}")

        if chart_type in ["bar", "line", "scatter"] and len(safe_columns) < 2:
            logger.warning(f"Not enough columns for {chart_type} chart. Need 2, got {len(safe_columns)}")
            return []
        elif chart_type == "pie" and len(safe_columns) < 1:
            logger.warning(f"Not enough columns for {chart_type} chart. Need at least 1, got {len(safe_columns)}")
            return []

        # --- Helper to aggregate data if needed ---
        def aggregate_data(x_col, y_col, agg_method="none"):
            logger.info(f"Aggregating data: x_col={x_col}, y_col={y_col}, agg_method={agg_method}")
            
            if agg_method == "sum":
                result = df.group_by(x_col).agg(pl.sum(y_col).alias("y")).rename({x_col: "x"}).sort("y", descending=True).to_dicts()
            elif agg_method == "mean":
                result = df.group_by(x_col).agg(pl.mean(y_col).alias("y")).rename({x_col: "x"}).sort("y", descending=True).to_dicts()
            elif agg_method == "count":
                result = df.group_by(x_col).agg(pl.count().alias("y")).rename({x_col: "x"}).sort("y", descending=True).to_dicts()
            else:
                # For "none" aggregation, we need to sum by x_col since we have multiple rows per region
                logger.info(f"No aggregation specified, defaulting to sum by {x_col}")
                result = df.group_by(x_col).agg(pl.sum(y_col).alias("y")).rename({x_col: "x"}).sort("y", descending=True).to_dicts()
            
            logger.info(f"Aggregation result: {len(result)} rows")
            if result:
                logger.info(f"Sample data: {result[:3]}")
            return result

        traces = []

        # --------------------------
        # Pie Chart
        # --------------------------
        if chart_type == "pie":
            if len(safe_columns) == 1:
                # Single categorical column - count occurrences
                logger.info(f"Pie chart with single column: counting occurrences of {safe_columns[0]}")
                rows = df.group_by(safe_columns[0]).agg(pl.count().alias("count")).sort("count", descending=True).to_dicts()
                trace = {"labels": [r[safe_columns[0]] for r in rows], "values": [r["count"] for r in rows], "type": "pie"}
                logger.info(f"Pie chart data: {len(rows)} categories")
            elif len(safe_columns) >= 2:
                # Two columns - use first as labels, second as values
                rows = aggregate_data(safe_columns[0], safe_columns[1], aggregation)
                trace = {"labels": [r["x"] for r in rows], "values": [r["y"] for r in rows], "type": "pie"}
                logger.info(f"Pie chart data: {len(rows)} categories using columns {safe_columns[0]} and {safe_columns[1]}")
            else:
                logger.warning("Not enough columns for pie chart")
                return []
            
            traces.append(trace)

        # --------------------------
        # Bar / Line / Scatter
        # --------------------------
        elif chart_type in ["bar", "line", "scatter"]:
            rows = aggregate_data(safe_columns[0], safe_columns[1], aggregation)
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

        # --------------------------
        # Histogram
        # --------------------------
        elif chart_type == "histogram":
            numeric_col = next((c for c in safe_columns if df[c].dtype in pl.NUMERIC_DTYPES), None)
            if numeric_col:
                traces.append({"x": df[numeric_col].to_list(), "type": "histogram"})
        # --------------------------
        # Box Plot
        # --------------------------
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

        # --------------------------
        # Grouped Bar Chart
        # --------------------------
        elif chart_type == "grouped_bar_chart":
            if group_by_raw:
                group_by_cols = [group_by_raw] if isinstance(group_by_raw, str) else group_by_raw
                safe_group_by = [self._find_safe_column_name(df, c) for c in group_by_cols if c]
                safe_group_by = [c for c in safe_group_by if c]
                if len(safe_group_by) >= 2:
                    pivot = df.pivot(index=safe_group_by[0], columns=safe_group_by[1], values=safe_columns[0], aggregate_function="sum").fill_null(0)
                    for col in pivot.columns[1:]:
                        traces.append({"x": pivot[pivot.columns[0]].to_list(), "y": pivot[col].to_list(), "type": "bar", "name": col})

        # --------------------------
        # TODO: Treemap / Heatmap
        # --------------------------
        # These require more complex aggregation. Add later if needed.

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
        
        # Use the new PromptFactory for enhanced functionality
        factory = PromptFactory(dataset_context=context)
        prompt = factory.get_prompt(PromptType.QUIS_ANSWER, question=question)
        return await self._call_ollama(prompt, model_role="summary_engine") # Use the summary engine for this

    # =================================================================================
    # == NEW STORYTELLING AND CHART EXPLANATION METHODS
    # =================================================================================

    async def generate_data_story(self, dataset_id: str, user_id: str, story_type: str = "business_impact") -> Dict[str, Any]:
        """
        Generates compelling data narratives using the new storytelling capabilities.
        """
        try:
            # Get dataset metadata
            dataset_doc = await self.db.datasets.find_one({"_id": ObjectId(dataset_id), "user_id": user_id})
            if not dataset_doc or not dataset_doc.get("metadata"):
                raise HTTPException(status_code=404, detail="Dataset not found or not processed yet.")
            
            # Perform comprehensive analysis
            analysis_results = await self._perform_comprehensive_analysis(dataset_doc["metadata"])
            
            # Generate story using the new storytelling prompt
            prompt_factory = PromptFactory(
                dataset_context=json.dumps(dataset_doc["metadata"], indent=2),
                user_preferences={"prefers_stories": True, "story_depth": "detailed"}
            )
            
            prompt = prompt_factory.get_prompt(
                PromptType.DATA_STORYTELLER,
                data_insights=analysis_results,
                story_type=story_type,
                target_audience="business_stakeholder"
            )
            
            llm_response = await self._call_ollama(prompt, model_role="story_engine", expect_json=True)
            
            if llm_response.get("fallback"):
                return self._generate_fallback_story(dataset_doc["metadata"], story_type)
            
            return {
                "story": llm_response.get("story", {}),
                "story_type": story_type,
                "confidence": llm_response.get("confidence", "Medium"),
                "generated_at": datetime.utcnow().isoformat(),
                "dataset_name": dataset_doc.get("name", "Unknown Dataset")
            }
            
        except Exception as e:
            logger.error(f"Error generating data story: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate data story.")

    async def explain_chart(self, dataset_id: str, user_id: str, chart_config: Dict[str, Any], chart_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Provides comprehensive explanations of charts and visualizations.
        """
        try:
            # Get dataset metadata
            dataset_doc = await self.db.datasets.find_one({"_id": ObjectId(dataset_id), "user_id": user_id})
            if not dataset_doc or not dataset_doc.get("metadata"):
                raise HTTPException(status_code=404, detail="Dataset not found or not processed yet.")
            
            # Generate chart explanation using the new explainer prompt
            prompt_factory = PromptFactory(
                dataset_context=json.dumps(dataset_doc["metadata"], indent=2),
                user_preferences={"prefers_detailed_explanations": True}
            )
            
            prompt = prompt_factory.get_prompt(
                PromptType.CHART_EXPLAINER,
                chart_config=chart_config,
                chart_data=chart_data,
                explanation_depth="detailed"
            )
            
            llm_response = await self._call_ollama(prompt, model_role="explainer_engine", expect_json=True)
            
            if llm_response.get("fallback"):
                return self._generate_fallback_chart_explanation(chart_config)
            
            return {
                "explanation": llm_response.get("explanation", {}),
                "confidence": llm_response.get("confidence", "Medium"),
                "suggested_follow_ups": llm_response.get("suggested_follow_ups", []),
                "generated_at": datetime.utcnow().isoformat(),
                "chart_type": chart_config.get("chart_type", "unknown")
            }
            
        except Exception as e:
            logger.error(f"Error explaining chart: {e}")
            raise HTTPException(status_code=500, detail="Failed to explain chart.")

    async def generate_business_insights(self, dataset_id: str, user_id: str, business_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates business-focused insights with actionable recommendations.
        """
        try:
            # Get dataset metadata
            dataset_doc = await self.db.datasets.find_one({"_id": ObjectId(dataset_id), "user_id": user_id})
            if not dataset_doc or not dataset_doc.get("metadata"):
                raise HTTPException(status_code=404, detail="Dataset not found or not processed yet.")
            
            # Perform comprehensive analysis
            analysis_results = await self._perform_comprehensive_analysis(dataset_doc["metadata"])
            
            # Generate business insights using the new business insights prompt
            prompt_factory = PromptFactory(
                dataset_context=json.dumps(dataset_doc["metadata"], indent=2),
                user_preferences={"prefers_business_focus": True, "analysis_depth": "strategic"}
            )
            
            prompt = prompt_factory.get_prompt(
                PromptType.BUSINESS_INSIGHTS,
                analysis_results=analysis_results,
                business_context=business_context
            )
            
            llm_response = await self._call_ollama(prompt, model_role="business_engine", expect_json=True)
            
            if llm_response.get("fallback"):
                return self._generate_fallback_business_insights(dataset_doc["metadata"], business_context)
            
            return {
                "business_insights": llm_response.get("business_insights", {}),
                "confidence": llm_response.get("confidence", "Medium"),
                "next_analysis": llm_response.get("next_analysis", ""),
                "generated_at": datetime.utcnow().isoformat(),
                "dataset_name": dataset_doc.get("name", "Unknown Dataset")
            }
            
        except Exception as e:
            logger.error(f"Error generating business insights: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate business insights.")

    def _generate_fallback_story(self, dataset_metadata: Dict[str, Any], story_type: str) -> Dict[str, Any]:
        """Fallback story generation when LLM fails."""
        overview = dataset_metadata.get('dataset_overview', {})
        total_rows = overview.get('total_rows', 0)
        column_count = overview.get('column_count', 0)
        
        return {
            "story": {
                "title": f"Data Overview: {story_type.title()} Analysis",
                "hook": f"Your dataset contains {total_rows:,} records across {column_count} dimensions, revealing several key insights.",
                "narrative": f"This dataset represents a substantial collection of {total_rows:,} data points across {column_count} different variables. The data structure suggests opportunities for pattern analysis and trend identification. Key areas of interest include data quality assessment, correlation analysis, and performance metrics evaluation.",
                "key_metrics": [f"{total_rows:,} total records", f"{column_count} data dimensions", "Multiple analysis opportunities"],
                "business_impact": "This dataset provides a solid foundation for data-driven decision making and strategic planning.",
                "recommendations": ["Explore data quality metrics", "Analyze correlations between variables", "Identify performance patterns"]
            },
            "story_type": story_type,
            "confidence": "Medium"
        }

    def _generate_fallback_chart_explanation(self, chart_config: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback chart explanation when LLM fails."""
        chart_type = chart_config.get("chart_type", "unknown")
        
        return {
            "explanation": {
                "purpose": f"This {chart_type} chart visualizes the selected data dimensions to reveal patterns and relationships.",
                "data_structure": "The chart organizes data according to the specified configuration, with axes and segments representing different data categories.",
                "key_patterns": ["Data distribution patterns", "Trend indicators", "Comparative relationships"],
                "statistical_insights": "The visualization reveals the underlying data structure and key statistical relationships.",
                "business_meaning": "This chart provides insights that can inform business decisions and strategic planning.",
                "limitations": "Consider data quality and sample size when interpreting results.",
                "next_steps": "Explore additional chart types or drill down into specific data segments."
            },
            "confidence": "Medium",
            "suggested_follow_ups": ["Try a different chart type", "Analyze specific data segments", "Explore correlations"]
        }

    def _generate_fallback_business_insights(self, dataset_metadata: Dict[str, Any], business_context: Optional[str]) -> Dict[str, Any]:
        """Fallback business insights when LLM fails."""
        overview = dataset_metadata.get('dataset_overview', {})
        total_rows = overview.get('total_rows', 0)
        
        return {
            "business_insights": {
                "executive_summary": f"Analysis of {total_rows:,} data points reveals opportunities for data-driven decision making and strategic optimization.",
                "opportunities": [
                    {
                        "title": "Data Quality Optimization",
                        "description": "Improve data completeness and accuracy for better insights",
                        "potential_impact": "High",
                        "effort_required": "Medium",
                        "recommended_action": "Implement data validation processes"
                    }
                ],
                "risks": [
                    {
                        "title": "Data Quality Concerns",
                        "description": "Potential gaps in data completeness may affect analysis reliability",
                        "severity": "Medium",
                        "mitigation_strategy": "Regular data quality audits and validation"
                    }
                ],
                "key_metrics": {
                    "primary_kpi": "Data completeness and accuracy",
                    "benchmark": "Industry standard data quality metrics",
                    "trend": "Stable"
                },
                "strategic_recommendations": [
                    {
                        "priority": "High",
                        "action": "Establish regular data quality monitoring",
                        "timeline": "Immediate",
                        "expected_outcome": "Improved data reliability and analysis accuracy"
                    }
                ]
            },
            "confidence": "Medium",
            "next_analysis": "Deep dive into specific data segments and correlations"
        }

# =================================================================================
# == SINGLETON INSTANCE
# =================================================================================
ai_service = AIService()