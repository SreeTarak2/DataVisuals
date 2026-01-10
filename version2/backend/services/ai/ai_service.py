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

from typing import Any, Dict, Optional, AsyncGenerator
from fastapi import HTTPException
import logging
import json
import re
import polars as pl

from db.database import get_database
from services.llm_router import llm_router
from services.datasets.dataset_loader import load_dataset, create_context_string
from services.datasets.faiss_vector_service import faiss_vector_service
from services.rag.chunk_service import chunk_service
from services.rag.reranker_service import reranker_service
from services.charts.hydrate import hydrate_chart, hydrate_kpi, hydrate_table
from services.charts.column_matcher import column_matcher
from services.conversations.conversation_service import load_or_create_conversation, save_conversation
from core.prompts import PromptFactory, PromptType
from core.prompt_sanitizer import sanitize_user_input, is_data_related_query
from services.ai.query_rewrite import rewrite_query

logger = logging.getLogger(__name__)


# -----------------------------------------------------------
# QUERY COMPLEXITY ANALYZER (ChatGPT/Grok Parity)
# -----------------------------------------------------------
class QueryComplexityAnalyzer:
    """
    Analyze query complexity to determine appropriate response format.
    Returns 'simple', 'moderate', or 'complex' to guide LLM formatting.
    """
    
    # Patterns that indicate simple, direct questions
    SIMPLE_PATTERNS = [
        r"^what is the (total|sum|average|mean|max|min|count)",
        r"^what's the (total|sum|average|mean|max|min|count)",
        r"^how many",
        r"^how much",
        r"^show me the (top|bottom) \d+",
        r"^what (is|was) the .+ (in|for|of|on)",
        r"^give me the",
        r"^tell me the",
    ]
    
    # Patterns that indicate complex, analytical questions
    COMPLEX_PATTERNS = [
        r"(compare|versus|vs\.?|difference between)",
        r"(why|explain|analyze|breakdown|break down)",
        r"(trend|trends|forecast|predict|projection|over time)",
        r"(correlation|relationship|impact|affect|influence)",
        r"(top|bottom) \d+ .* (by|with|and|across)",
        r"(performance|analysis|overview|summary|report)",
        r"(all|every|each) .* (by|across|per)",
        r"(segment|segmentation|breakdown by)",
    ]
    
    @classmethod
    def classify(cls, query: str) -> str:
        """
        Classify query complexity.
        
        Returns:
            'simple' - Direct factual questions (1-2 sentence answer)
            'moderate' - Analytical questions (structured bullet response)
            'complex' - Multi-part questions (full headers and sections)
        """
        if not query:
            return "simple"
            
        query_lower = query.lower().strip()
        
        # Check for simple patterns first
        for pattern in cls.SIMPLE_PATTERNS:
            if re.match(pattern, query_lower):
                # But if it also contains complex indicators, upgrade
                complex_score = sum(
                    1 for p in cls.COMPLEX_PATTERNS 
                    if re.search(p, query_lower)
                )
                if complex_score == 0:
                    return "simple"
        
        # Count complex pattern matches
        complex_score = sum(
            1 for pattern in cls.COMPLEX_PATTERNS 
            if re.search(pattern, query_lower)
        )
        
        if complex_score >= 2:
            return "complex"
        elif complex_score == 1:
            return "moderate"
        
        # Fallback: use query length as indicator
        word_count = len(query_lower.split())
        question_count = query_lower.count("?")
        
        # Multiple questions = complex
        if question_count >= 2:
            return "complex"
        
        # Length-based heuristics
        if word_count <= 8:
            return "simple"
        elif word_count <= 20:
            return "moderate"
        else:
            return "complex"
    
    @classmethod
    def get_all(cls, query: str) -> Dict[str, Any]:
        """
        Get full complexity analysis including score breakdown.
        
        Useful for debugging and logging.
        """
        query_lower = query.lower().strip()
        
        simple_matches = [
            p for p in cls.SIMPLE_PATTERNS 
            if re.match(p, query_lower)
        ]
        complex_matches = [
            p for p in cls.COMPLEX_PATTERNS 
            if re.search(p, query_lower)
        ]
        
        return {
            "complexity": cls.classify(query),
            "simple_matches": len(simple_matches),
            "complex_matches": len(complex_matches),
            "word_count": len(query_lower.split()),
            "question_count": query_lower.count("?")
        }



class AIService:
    """
    Core orchestration layer for AI-driven data analytics operations.
    
    Responsibilities:
    - Chat message processing with intent guardrails
    - Dashboard generation from datasets
    - Conversation lifecycle management
    - LLM routing and response hydration
    
    All methods integrate with:
    - LLM router for multi-model fallbacks
    - Dataset loader for async data access
    - Chart hydration engine for Plotly generation
    - Conversation service for message persistence
    """
    
    def __init__(self):
        self._db = None

    @property
    def db(self):
        """Lazy database initialization to avoid None during startup"""
        if self._db is None:
            self._db = get_database()
        return self._db

    # -----------------------------------------------------------
    # RAG CONTEXT RETRIEVAL
    # -----------------------------------------------------------
    async def _get_rag_context(
        self, 
        query: str, 
        dataset_id: str, 
        user_id: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """
        Get context for LLM using RAG vector retrieval.
        Falls back to full context string if vector search unavailable.
        
        Args:
            query: User's query for semantic matching
            dataset_id: Dataset to search in
            user_id: User for access control
            metadata: Full dataset metadata for fallback
            
        Returns:
            Context string for LLM prompt
        """
        try:
            # Try vector retrieval
            if faiss_vector_service.enable_vector_search:
                chunks = await faiss_vector_service.search_relevant_chunks(
                    query=query,
                    dataset_id=dataset_id,
                    user_id=user_id,
                    k=10,  # Retrieve more for re-ranking
                    score_threshold=0.3  # Lower threshold, reranker will filter
                )
                
                if chunks:
                    # Apply re-ranking for better relevance
                    reranked_chunks = reranker_service.rerank(
                        query=query,
                        chunks=chunks,
                        top_k=5,
                        score_threshold=0.4,
                        use_diversity=True
                    )
                    
                    if reranked_chunks:
                        context = faiss_vector_service.assemble_context_from_chunks(
                            reranked_chunks, 
                            max_tokens=2000
                        )
                        logger.info(f"RAG: Retrieved {len(chunks)} -> reranked to {len(reranked_chunks)} chunks")
                        return context
                    
                logger.debug("RAG: No chunks after re-ranking, falling back to full context")
            
            # Fallback to full context
            return create_context_string(metadata)
            
        except Exception as e:
            logger.warning(f"RAG retrieval failed, using fallback: {e}")
            return create_context_string(metadata)

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
        """
        Process a user query into a data-driven response with optional chart.
        
        Pipeline:
        1. Intent guardrail: Rejects off-topic queries without LLM calls
        2. Conversation loading: Retrieves or creates conversation context
        3. Dataset validation: Ensures dataset exists and is processed
        4. Query rewriting: Enhances query clarity with dataset context
        5. LLM invocation: Routes to chart_engine via llm_router
        6. Response extraction: Robust parsing of response_text and chart_config
        7. Chart hydration: Converts chart config + data into Plotly format
        8. Persistence: Saves AI response to conversation history
        
        Args:
            query: User's natural language question about the data
            dataset_id: MongoDB ObjectId of target dataset
            user_id: User's authentication identifier
            conversation_id: Optional ID to continue existing conversation
            
        Returns:
            Dict with keys:
            - response: AI-generated text explanation
            - chart_config: Hydrated Plotly chart data (null if not requested)
            - conversation_id: Database ID of conversation thread
            
        Raises:
            HTTPException(404): Dataset not found
            HTTPException(409): Dataset still processing
            HTTPException(502): LLM unavailable
            HTTPException(500): LLM returned empty response
        """
        query_lower = query.strip().lower()

        # --- SECURITY: Sanitize user input to prevent prompt injection ---
        try:
            sanitized_query = sanitize_user_input(query)
        except ValueError as e:
            return {
                "response_text": f"Invalid query: {str(e)}",
                "chart_config": None,
                "conversation_id": conversation_id
            }
        
        # Use sanitized query for processing
        query = sanitized_query
        query_lower = query.lower()

        # Load or create conversation
        messages = conv.get("messages", [])
        messages.append({"role": "user", "content": query})

        dataset_doc = await self.db.datasets.find_one({"_id": dataset_id, "user_id": user_id})
        if not dataset_doc:
            raise HTTPException(404, "Dataset not found.")

        metadata = dataset_doc.get("metadata")
        if not metadata:
            raise HTTPException(409, "Dataset is still being processed.")

        # RAG: Try vector retrieval first, fallback to full context
        dataset_context = await self._get_rag_context(query, dataset_id, user_id, metadata)

        enhanced_query = await rewrite_query(query, dataset_context)
        if enhanced_query != query:
            logger.info(f"Query rewritten: '{query[:50]}...' → '{enhanced_query[:50]}...'")
        messages[-1]["content"] = enhanced_query

        factory = PromptFactory(dataset_metadata=metadata)
        prompt = factory.get_prompt(PromptType.CONVERSATIONAL, user_message=enhanced_query, history=messages)

        llm_response = await llm_router.call(prompt, model_role="chart_engine", expect_json=True)

        logger.info(f"LLM Response structure: {json.dumps(llm_response, indent=2)[:1000]}")
        logger.info(f"LLM Response keys: {list(llm_response.keys()) if isinstance(llm_response, dict) else 'Not a dict'}")

        if isinstance(llm_response, dict) and llm_response.get("error"):
            logger.error(f"Chat LLM error: {llm_response}")
            raise HTTPException(status_code=502, detail="AI model unavailable.")

        ai_text = ""
        if isinstance(llm_response, dict):
            ai_text = (
                llm_response.get("response_text") or 
                llm_response.get("response") or 
                llm_response.get("text") or 
                llm_response.get("answer") or
                llm_response.get("content") or
                ""
            )
        else:
            ai_text = str(llm_response)
        
        if not ai_text or not ai_text.strip():
            logger.error(f"Empty response from LLM. Full response: {llm_response}")
            raise HTTPException(status_code=500, detail="AI returned empty response")
        
        ai_text = ai_text.replace("\\n", " ").replace("\n", " ")
        ai_text = " ".join(ai_text.split())
        
        logger.info(f"Extracted ai_text ({len(ai_text)} chars): {ai_text[:200]}...")
        
        chart_config_raw = llm_response.get("chart_config") if isinstance(llm_response, dict) else None
        
        chart_data = None
        if chart_config_raw:
            logger.info(f"Chart config received: {json.dumps(chart_config_raw)[:200]}")
            try:
                file_path = dataset_doc.get("file_path")
                if not file_path:
                    raise ValueError("Dataset file path not found")
                
                df = await load_dataset(file_path)
                
                # --- COLUMN VALIDATION: Auto-fix LLM column references ---
                available_columns = list(df.columns)
                chart_config_raw, corrections = column_matcher.validate_and_fix_chart_config(
                    chart_config_raw, 
                    available_columns,
                    threshold=0.6
                )
                if corrections:
                    logger.info(f"Chart columns auto-corrected: {corrections}")
                
                from db.schemas_dashboard import ChartConfig, ChartType, AggregationType
                
                chart_type_map = {
                    "bar": ChartType.BAR,
                    "line": ChartType.LINE,
                    "pie": ChartType.PIE,
                    "scatter": ChartType.SCATTER,
                    "histogram": ChartType.HISTOGRAM,
                    "heatmap": ChartType.HEATMAP,
                    "box": ChartType.BOX_PLOT,
                    "box_plot": ChartType.BOX_PLOT,
                    "treemap": ChartType.TREEMAP,
                    "grouped_bar": ChartType.GROUPED_BAR,
                    "area": ChartType.AREA
                }
                
                chart_type = chart_type_map.get(chart_config_raw.get("type", "bar").lower(), ChartType.BAR)
                
                columns = []
                
                if chart_type == ChartType.PIE:
                    if "labels" in chart_config_raw:
                        columns.append(chart_config_raw["labels"])
                    if "values" in chart_config_raw and chart_config_raw["values"] not in ["count", "count of each model"]:
                        columns.append(chart_config_raw["values"])
                    elif "x" in chart_config_raw:
                        columns.append(chart_config_raw["x"])
                    
                    if len(columns) == 1:
                        numeric_cols = [col for col in df.columns if df[col].dtype in [pl.Int64, pl.Int32, pl.Float64, pl.Float32]]
                        if numeric_cols and columns[0] not in numeric_cols:
                            columns.append(numeric_cols[0])
                        elif len(df.columns) >= 2:
                            for col in df.columns:
                                if col != columns[0]:
                                    columns.append(col)
                                    break
                else:
                    if "x" in chart_config_raw:
                        columns.append(chart_config_raw["x"])
                    if "y" in chart_config_raw:
                        columns.append(chart_config_raw["y"])
                
                chart_title = chart_config_raw.get("title", "Chart Visualization")
                
                class HydrationConfig:
                    def __init__(self, chart_type, columns, aggregation):
                        self.chart_type = chart_type
                        self.columns = columns.copy()
                        self.aggregation = aggregation
                        self.group_by = None
                
                hydration_config = HydrationConfig(
                    chart_type=chart_type,
                    columns=columns,
                    aggregation=AggregationType.SUM
                )
                
                chart_traces = hydrate_chart(df, hydration_config)
                
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
                chart_data = None

        ai_message = {
            "role": "ai", 
            "content": ai_text
        }
        if chart_data:
            try:
                json.dumps(chart_data)
                ai_message["chart_config"] = chart_data
                logger.info(f"Saving message with chart_config to database (data traces: {len(chart_data.get('data', []))})")
            except (TypeError, ValueError) as e:
                logger.error(f"Chart data not JSON-serializable: {e}")
                ai_message["chart_config"] = None
        
        messages.append(ai_message)
        await save_conversation(conv["_id"], messages)

        response_data = {
            "response": ai_text,
            "chart_config": chart_data,
            "conversation_id": str(conv["_id"])
        }
        
        if chart_data:
            logger.info(f"Returning chart_config with {len(chart_data.get('data', []))} trace(s)")
            first_trace = chart_data.get('data', [{}])[0] if chart_data.get('data') else None
            if first_trace and isinstance(first_trace, dict):
                logger.info(f"Sample trace structure: {first_trace.keys()}")
            else:
                logger.info(f"Sample trace type: {type(first_trace)}")
        else:
            logger.info("No chart_config in response")
        
        return response_data

    async def generate_ai_dashboard(
        self,
        dataset_id: str,
        user_id: str,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive dashboard layout with hydrated components.
        
        Pipeline:
        1. Dataset validation: Loads dataset metadata and configuration
        2. Context building: Creates comprehensive dataset summary for LLM
        3. LLM invocation: Routes to visualization_engine for layout design
        4. Component specification: Extracts KPI, chart, and table configs
        5. Data loading: Asynchronously loads dataset into memory
        6. Hydration: Converts configs + data into Plotly/table formats
        7. Assembly: Returns complete dashboard structure
        
        Args:
            dataset_id: MongoDB ObjectId of target dataset
            user_id: User's authentication identifier
            force_regenerate: Bypass cached layouts and regenerate
            
        Returns:
            Dict with keys:
            - layout_grid: CSS Grid template string (e.g., "repeat(4, 1fr)")
            - components: List of hydrated dashboard components
                Each component contains:
                - type: "kpi" | "chart" | "table"
                - config: Original configuration from LLM
                - value/chart_data/table_data: Hydrated data
                
        Raises:
            HTTPException(404): Dataset not found
            HTTPException(409): Dataset still processing
            HTTPException(500): Dashboard generation failed
        """
        dataset_doc = await self.db.datasets.find_one({"_id": dataset_id, "user_id": user_id})
        if not dataset_doc:
            raise HTTPException(404, "Dataset not found.")

        metadata = dataset_doc.get("metadata")
        if not metadata:
            raise HTTPException(409, "Dataset is still being processed.")

        dataset_context = create_context_string(metadata)

        factory = PromptFactory(dataset_metadata=metadata)
        prompt = factory.get_prompt(PromptType.DASHBOARD_DESIGNER)

        layout = await llm_router.call(prompt, model_role="visualization_engine", expect_json=True)

        if not layout or "dashboard" not in layout:
            raise HTTPException(500, "AI failed to generate dashboard.")

        blueprint = layout["dashboard"]
        components = blueprint.get("components", [])
        layout_grid = blueprint.get("layout_grid", "repeat(4, 1fr)")

        df = await load_dataset(dataset_doc["file_path"])

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

        return {
            "layout_grid": layout_grid,
            "components": hydrated
        }

    async def get_user_conversations(self, user_id: str):
        """
        Retrieve all conversation threads for a user.
        
        Args:
            user_id: User's authentication identifier
            
        Returns:
            Dict with key "conversations": sorted list of conversation objects
            Returns empty list on error
        """
        try:
            conversations = await self.db.conversations.find(
                {"user_id": user_id}
            ).sort("updated_at", -1).to_list(length=100)
            
            for conv in conversations:
                conv["_id"] = str(conv["_id"])
            
            return {"conversations": conversations}
        except Exception as e:
            logger.error(f"Error fetching conversations: {e}")
            return {"conversations": []}

    async def get_conversation(self, conversation_id: str, user_id: str):
        """
        Retrieve a specific conversation thread.
        
        Args:
            conversation_id: Database ID of conversation
            user_id: User's authentication identifier for access control
            
        Returns:
            Conversation object with _id converted to string, or None if not found
        """
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
        """
        Delete a conversation thread.
        
        Args:
            conversation_id: Database ID of conversation
            user_id: User's authentication identifier for access control
            
        Returns:
            Boolean indicating successful deletion
        """
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
        Enhanced chat processing with additional context features.
        
        Currently delegates to process_chat_message() for core functionality.
        Future expansion point for:
        - Learning mode persistence
        - Multi-modal context enrichment
        - Advanced reasoning chains
        
        Args:
            query: User's natural language question
            dataset_id: Target dataset identifier
            user_id: User's authentication identifier
            conversation_id: Optional conversation context
            mode: Processing mode ("learning" or "inference")
            
        Returns:
            Response from process_chat_message()
            
        Raises:
            Exception: Propagates from core process_chat_message()
        """
        try:
            return await self.process_chat_message(
                query=query,
                dataset_id=dataset_id,
                user_id=user_id,
                conversation_id=conversation_id
            )
        except Exception as e:
            logger.error(f"Error in enhanced chat processing: {e}")
            raise

    async def process_chat_message_streaming(
        self,
        query: str,
        dataset_id: str,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat response tokens as an async generator.
        
        Pipeline:
        1. Intent guardrail: Checks for off-topic queries
        2. Conversation loading: Retrieves or creates context
        3. Dataset validation: Ensures dataset availability
        4. Query rewriting: Enhances clarity with dataset context
        5. Token streaming: Yields tokens from LLM in real-time
        6. Chart inference: Optionally generates chart if appropriate
        7. Persistence: Saves complete response to conversation history
        
        Yields:
            Dict with type field:
            - "token": {"content": str} - Text token to display
            - "response_complete": {"full_response": str} - Complete response text
            - "chart": {"chart_config": dict} - Hydrated chart data
            - "error": {"content": str} - Error message
            - "done": {"conversation_id": str, "chart_config": dict|null} - Final event
            
        Args:
            query: User's natural language question
            dataset_id: MongoDB ObjectId of target dataset
            user_id: User's authentication identifier
            conversation_id: Optional ID to continue existing conversation
        """
        query_lower = query.strip().lower()

        off_topic_triggers = [
            "hello", "hi ", "hey ", "good morning", "good evening", "how are you",
            "thank you", "thanks", "who is", "what is the capital", "prime minister",
            "president", "weather", "joke", "tell me a", "what time", "news", "stock",
            "who are you", "what can you do", "help me", "how do i", "bye", "goodbye"
        ]

        if any(trigger in query_lower for trigger in off_topic_triggers) or len(query_lower) < 5:
            guardrail_response = (
                "I'm a specialized data analytics assistant. I can help with trends, charts, "
                "forecasts, correlations, or insights from your dataset.\n\n"
                "Try asking: \"Show top products by revenue\" or \"What is the sales trend over time?\""
            )
            yield {"type": "token", "content": guardrail_response}
            yield {"type": "response_complete", "full_response": guardrail_response}
            yield {"type": "done", "conversation_id": conversation_id, "chart_config": None}
            return

        conv = await load_or_create_conversation(conversation_id, user_id, dataset_id)
        messages = conv.get("messages", [])
        messages.append({"role": "user", "content": query})

        dataset_doc = await self.db.datasets.find_one({"_id": dataset_id, "user_id": user_id})
        if not dataset_doc:
            yield {"type": "error", "content": "Dataset not found"}
            return

        metadata = dataset_doc.get("metadata")
        if not metadata:
            yield {"type": "error", "content": "Dataset is still being processed"}
            return

        dataset_context = create_context_string(metadata)

        enhanced_query = await rewrite_query(query, dataset_context)
        if enhanced_query != query:
            logger.info(f"Query rewritten: '{query[:50]}...' → '{enhanced_query[:50]}...'")
        
        messages[-1]["content"] = enhanced_query

        factory = PromptFactory(dataset_metadata=metadata)
        prompt = factory.get_prompt(PromptType.CONVERSATIONAL, user_message=enhanced_query, history=messages)

        # Analyze query complexity for adaptive formatting
        query_complexity = QueryComplexityAnalyzer.classify(query)
        logger.info(f"Query complexity: {query_complexity} for query: '{query[:50]}...'")

        full_response = ""
        
        try:
            async for chunk in llm_router.call_streaming(
                prompt, 
                model_role="chat_streaming",
                is_conversational=True,
                query_complexity=query_complexity
            ):
                if chunk["type"] == "token":
                    full_response += chunk["content"]
                    yield {"type": "token", "content": chunk["content"]}
                    
                elif chunk["type"] == "error":
                    yield {"type": "error", "content": chunk["content"]}
                    return
                    
                elif chunk["type"] == "done":
                    yield {"type": "response_complete", "full_response": full_response}
                    
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield {"type": "error", "content": str(e)}
            return

        chart_data = None
        chart_keywords = ["chart", "histogram", "bar", "pie", "scatter", "line", "plot", "visualization"]
        should_generate_chart = any(kw in full_response.lower() for kw in chart_keywords)
        
        if should_generate_chart:
            try:
                chart_prompt = f"""Based on this response: "{full_response[:500]}"
                
Generate a chart configuration JSON for the dataset with columns: {metadata.get('column_names', [])[:10]}

Return ONLY valid JSON with this structure:
{{"chart_config": {{"type": "bar|line|pie|histogram|scatter", "x": "column_name", "y": "column_name", "title": "Chart Title"}}}}"""

                chart_response = await llm_router.call(
                    chart_prompt, 
                    model_role="chart_engine", 
                    expect_json=True,
                    max_tokens=500
                )
                
                if isinstance(chart_response, dict) and chart_response.get("chart_config"):
                    chart_config_raw = chart_response["chart_config"]
                    
                    file_path = dataset_doc.get("file_path")
                    if file_path:
                        df = await load_dataset(file_path)
                        
                        # --- COLUMN VALIDATION: Auto-fix LLM column references ---
                        available_columns = list(df.columns)
                        chart_config_raw, corrections = column_matcher.validate_and_fix_chart_config(
                            chart_config_raw, 
                            available_columns,
                            threshold=0.6
                        )
                        if corrections:
                            logger.info(f"Streaming chart columns auto-corrected: {corrections}")
                        
                        from db.schemas_dashboard import ChartConfig, ChartType, AggregationType
                        
                        chart_type_map = {
                            "bar": ChartType.BAR,
                            "line": ChartType.LINE,
                            "pie": ChartType.PIE,
                            "scatter": ChartType.SCATTER,
                            "histogram": ChartType.HISTOGRAM,
                        }
                        
                        chart_type = chart_type_map.get(
                            chart_config_raw.get("type", "bar").lower(), 
                            ChartType.BAR
                        )
                        
                        columns = []
                        if "x" in chart_config_raw:
                            columns.append(chart_config_raw["x"])
                        if "y" in chart_config_raw:
                            columns.append(chart_config_raw["y"])
                        
                        class HydrationConfig:
                            def __init__(self, chart_type, columns, aggregation):
                                self.chart_type = chart_type
                                self.columns = columns.copy()
                                self.aggregation = aggregation
                                self.group_by = None
                        
                        from services.charts.hydrate import hydrate_chart
                        hydration_config = HydrationConfig(
                            chart_type=chart_type,
                            columns=columns,
                            aggregation=AggregationType.SUM
                        )
                        
                        chart_traces = hydrate_chart(df, hydration_config)
                        
                        chart_data = {
                            "data": chart_traces,
                            "layout": {
                                "title": chart_config_raw.get("title", ""),
                                "xaxis": {"title": chart_config_raw.get("x", "X")},
                                "yaxis": {"title": chart_config_raw.get("y", "Y")},
                                "paper_bgcolor": "rgba(0,0,0,0)",
                                "plot_bgcolor": "rgba(0,0,0,0)",
                                "font": {"color": "#e2e8f0"},
                                "height": 400,
                                "margin": {"t": 50, "b": 50, "l": 60, "r": 20}
                            }
                        }
                        
                        yield {"type": "chart", "chart_config": chart_data}
                        
            except Exception as e:
                logger.warning(f"Chart generation failed during streaming: {e}")

        ai_message = {
            "role": "ai",
            "content": full_response
        }
        if chart_data:
            ai_message["chart_config"] = chart_data
            
        messages.append(ai_message)
        await save_conversation(conv["_id"], messages)

        yield {
            "type": "done",
            "conversation_id": str(conv["_id"]),
            "chart_config": chart_data
        }


# Singleton instance
ai_service = AIService()
