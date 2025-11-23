"""
AIService — Clean Orchestrator Layer
------------------------------------
Responsibilities:
✓ Chat orchestration (messages → LLM → response)
✓ Dashboard generation (LLM → layout → hydration)
✓ Uses external modules for:
    - dataset loading
    - chart hydration
    - conversation management
    - LLM routing
"""

from typing import Any, Dict, Optional
from fastapi import HTTPException
import logging
import json

from db.database import get_database

from services.llm_router import llm_router

# UPDATED imports for new folder structure
from services.datasets.dataset_loader import load_dataset, create_context_string
from services.charts.hydrate import hydrate_chart, hydrate_kpi, hydrate_table
from services.conversations.conversation_service import load_or_create_conversation, save_conversation

from core.prompts import PromptFactory, PromptType

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        self._db = None

    @property
    def db(self):
        """Lazy database initialization to avoid None during startup"""
        if self._db is None:
            self._db = get_database()
        return self._db

    # -----------------------------------------------------------
    # CHAT PROCESSING PIPELINE
    # -----------------------------------------------------------
    async def process_chat_message(
        self,
        query: str,
        dataset_id: str,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:

        # 1. Load or create conversation
        conv = await load_or_create_conversation(conversation_id, user_id, dataset_id)
        messages = conv.get("messages", [])
        messages.append({"role": "user", "content": query})

        # 2. Fetch dataset metadata
        dataset_doc = await self.db.datasets.find_one({"_id": dataset_id, "user_id": user_id})
        if not dataset_doc:
            raise HTTPException(404, "Dataset not found.")

        metadata = dataset_doc.get("metadata")
        if not metadata:
            raise HTTPException(409, "Dataset is still being processed.")

        # 3. Build dataset context for LLM
        dataset_context = create_context_string(metadata)

        # 4. Build prompt using PromptFactory
        factory = PromptFactory(dataset_context=dataset_context, schema=metadata)
        prompt = factory.get_prompt(PromptType.CONVERSATIONAL, history=messages)

        # 5. Send to LLM (through router with fallback)
        llm_response = await llm_router.call(prompt, model_role="chart_engine", expect_json=True)

        # Debug: Log the exact response structure
        logger.info(f"LLM Response structure: {json.dumps(llm_response, indent=2)[:1000]}")
        logger.info(f"LLM Response keys: {list(llm_response.keys()) if isinstance(llm_response, dict) else 'Not a dict'}")

        # 6. Handle LLM error responses
        if isinstance(llm_response, dict) and llm_response.get("error"):
            logger.error(f"Chat LLM error: {llm_response}")
            raise HTTPException(status_code=502, detail="AI model unavailable.")

        # 7. Extract response text - simplified and robust
        ai_text = ""
        if isinstance(llm_response, dict):
            # Try multiple possible keys
            ai_text = (
                llm_response.get("response_text") or 
                llm_response.get("response") or 
                llm_response.get("text") or 
                llm_response.get("answer") or
                llm_response.get("content") or
                ""
            )
        else:
            # Fallback to string conversion
            ai_text = str(llm_response)
        
        # Ensure we have content
        if not ai_text or not ai_text.strip():
            logger.error(f"Empty response from LLM. Full response: {llm_response}")
            raise HTTPException(status_code=500, detail="AI returned empty response")
        
        # Clean up escaped newlines and extra whitespace
        ai_text = ai_text.replace("\\n", " ").replace("\n", " ")
        ai_text = " ".join(ai_text.split())  # Remove extra whitespace
        
        logger.info(f"Extracted ai_text ({len(ai_text)} chars): {ai_text[:200]}...")
        
        # Extract chart config
        chart_config_raw = llm_response.get("chart_config") if isinstance(llm_response, dict) else None
        
        # 8. Hydrate chart if requested
        chart_data = None
        if chart_config_raw:
            logger.info(f"Chart config received: {json.dumps(chart_config_raw)[:200]}")
            try:
                # Load dataset file path from database
                file_path = dataset_doc.get("file_path")
                if not file_path:
                    raise ValueError("Dataset file path not found")
                
                # Load dataset for hydration (async!)
                df = await load_dataset(file_path)
                
                # Convert LLM chart config to ChartConfig model
                from db.schemas_dashboard import ChartConfig, ChartType, AggregationType
                
                # Map LLM chart type to our ChartType enum
                chart_type_map = {
                    "bar": ChartType.BAR,
                    "line": ChartType.LINE,
                    "pie": ChartType.PIE,
                    "scatter": ChartType.SCATTER,
                    "histogram": ChartType.HISTOGRAM,
                    "heatmap": ChartType.HEATMAP,
                    "box": ChartType.BOX_PLOT,  # Fixed: box → BOX_PLOT
                    "box_plot": ChartType.BOX_PLOT,
                    "treemap": ChartType.TREEMAP,
                    "grouped_bar": ChartType.GROUPED_BAR,
                    "area": ChartType.AREA
                }
                
                chart_type = chart_type_map.get(chart_config_raw.get("type", "bar").lower(), ChartType.BAR)
                
                # Build columns list from x and y
                columns = []
                if "x" in chart_config_raw:
                    columns.append(chart_config_raw["x"])
                if "y" in chart_config_raw:
                    columns.append(chart_config_raw["y"])
                
                # Extract title (required field)
                chart_title = chart_config_raw.get("title", "Chart Visualization")
                
                # For hydration, we need to pass enums as enum objects (not strings)
                # Pydantic's use_enum_values=True converts enums to strings, but
                # hydrate_chart expects the actual enum to call .value on it
                # So we create a simple config object that preserves enum types
                class HydrationConfig:
                    def __init__(self, chart_type, columns, aggregation):
                        self.chart_type = chart_type  # Keep as ChartType enum
                        self.columns = columns.copy()  # Mutable, so copy
                        self.aggregation = aggregation  # Keep as AggregationType enum
                        self.group_by = None
                
                hydration_config = HydrationConfig(
                    chart_type=chart_type,
                    columns=columns,
                    aggregation=AggregationType.SUM
                )
                
                # Hydrate chart (convert config + data → Plotly traces)
                chart_traces = hydrate_chart(df, hydration_config)
                
                # Build Plotly-ready data structure
                chart_data = {
                    "data": chart_traces,
                    "layout": {
                        "title": chart_config_raw.get("title", ""),
                        "xaxis": chart_config_raw.get("xaxis", {"title": chart_config_raw.get("x", "X")}),
                        "yaxis": chart_config_raw.get("yaxis", {"title": chart_config_raw.get("y", "Y")}),
                        "paper_bgcolor": "rgba(0,0,0,0)",
                        "plot_bgcolor": "rgba(0,0,0,0)",
                        "font": {"color": "#e2e8f0"},
                        "height": 400,
                        "margin": {"t": 50, "b": 50, "l": 60, "r": 20}
                    }
                }
                logger.info(f"Chart hydrated successfully with {len(chart_traces)} trace(s)")
                logger.info(f"First trace sample: {json.dumps(chart_traces[0] if chart_traces else {})[:500]}")
            except Exception as e:
                logger.error(f"Chart hydration failed: {e}", exc_info=True)
                # Don't fail the whole request, just don't include chart
                chart_data = None

        # 9. Save conversation with chart data
        ai_message = {
            "role": "ai", 
            "content": ai_text
        }
        # Include chart_config in saved message if available
        if chart_data:
            # Ensure chart_data is JSON-serializable for MongoDB
            try:
                import json
                json.dumps(chart_data)  # Test serialization
                ai_message["chart_config"] = chart_data
                logger.info(f"Saving message with chart_config to database (data traces: {len(chart_data.get('data', []))})")
            except (TypeError, ValueError) as e:
                logger.error(f"Chart data not JSON-serializable: {e}")
                ai_message["chart_config"] = None
        
        messages.append(ai_message)
        await save_conversation(conv["_id"], messages)

        # 10. Return response with hydrated chart
        response_data = {
            "response": ai_text,
            "chart_config": chart_data,  # Now contains hydrated data!
            "conversation_id": str(conv["_id"])
        }
        
        # Debug logging for frontend
        if chart_data:
            logger.info(f"Returning chart_config with {len(chart_data.get('data', []))} trace(s)")
            logger.info(f"Sample trace structure: {chart_data.get('data', [{}])[0].keys() if chart_data.get('data') else 'No data'}")
        else:
            logger.info("No chart_config in response")
        
        return response_data

    # -----------------------------------------------------------
    # DASHBOARD GENERATION PIPELINE
    # -----------------------------------------------------------
    async def generate_ai_dashboard(
        self,
        dataset_id: str,
        user_id: str,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:

        # 1. Load dataset document
        dataset_doc = await self.db.datasets.find_one({"_id": dataset_id, "user_id": user_id})
        if not dataset_doc:
            raise HTTPException(404, "Dataset not found.")

        metadata = dataset_doc.get("metadata")
        if not metadata:
            raise HTTPException(409, "Dataset is still being processed.")

        # 2. Create LLM dataset context
        dataset_context = create_context_string(metadata)

        # 3. Build dashboard prompt
        factory = PromptFactory(dataset_context=dataset_context)
        prompt = factory.get_prompt(PromptType.DASHBOARD_DESIGNER)

        # 4. Request layout from LLM
        layout = await llm_router.call(prompt, model_role="visualization_engine", expect_json=True)

        if not layout or "dashboard" not in layout:
            raise HTTPException(500, "AI failed to generate dashboard.")

        blueprint = layout["dashboard"]
        components = blueprint.get("components", [])
        layout_grid = blueprint.get("layout_grid", "repeat(4, 1fr)")

        # 5. Load dataset file (Polars DF)
        df = await load_dataset(dataset_doc["file_path"])

        # 6. Hydrate all components
        hydrated = []
        for comp in components:
            ctype = comp.get("type")
            cfg = comp.get("config", {})

            if ctype == "kpi":
                comp["value"] = hydrate_kpi(df, cfg.get("column"), cfg.get("aggregation"))

            elif ctype == "chart":
                comp["chart_data"] = hydrate_chart(df, cfg)

            elif ctype == "table":
                comp["table_data"] = hydrate_table(df, cfg.get("columns", []))

            hydrated.append(comp)

        # 7. Return final dashboard structure
        return {
            "layout_grid": layout_grid,
            "components": hydrated
        }

    # -----------------------------------------------------------
    # CONVERSATION MANAGEMENT
    # -----------------------------------------------------------
    async def get_user_conversations(self, user_id: str):
        """Get all conversations for a user"""
        try:
            conversations = await self.db.conversations.find(
                {"user_id": user_id}
            ).sort("updated_at", -1).to_list(length=100)
            
            # Convert ObjectId to string for JSON serialization
            for conv in conversations:
                conv["_id"] = str(conv["_id"])
            
            return {"conversations": conversations}
        except Exception as e:
            logger.error(f"Error fetching conversations: {e}")
            return {"conversations": []}

    async def get_conversation(self, conversation_id: str, user_id: str):
        """Get a specific conversation"""
        try:
            from bson import ObjectId
            conversation = await self.db.conversations.find_one({
                "_id": ObjectId(conversation_id),
                "user_id": user_id
            })
            
            if conversation:
                conversation["_id"] = str(conversation["_id"])
            
            return conversation
        except Exception as e:
            logger.error(f"Error fetching conversation {conversation_id}: {e}")
            return None

    async def delete_conversation(self, conversation_id: str, user_id: str):
        """Delete a conversation"""
        try:
            from bson import ObjectId
            result = await self.db.conversations.delete_one({
                "_id": ObjectId(conversation_id),
                "user_id": user_id
            })
            
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting conversation {conversation_id}: {e}")
            return False

    async def process_chat_message_enhanced(
        self,
        query: str,
        dataset_id: str,
        user_id: str,
        conversation_id: str = None,
        mode: str = "learning"
    ):
        """
        Process chat message with enhanced features.
        Simplified version that uses the LLM router.
        """
        try:
            # Use the existing process_chat_message method
            return await self.process_chat_message(
                query=query,
                dataset_id=dataset_id,
                user_id=user_id,
                conversation_id=conversation_id
            )
        except Exception as e:
            logger.error(f"Error in enhanced chat processing: {e}")
            raise


# Singleton instance
ai_service = AIService()
