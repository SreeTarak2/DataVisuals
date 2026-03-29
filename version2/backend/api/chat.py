# backend/api/chat.py

import logging
import json
import os
import time
import asyncio
from pathlib import Path
from uuid import uuid4
from typing import Dict, Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)

# --- Chat Image Upload Configuration ---
CHAT_UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads" / "chat_images"
CHAT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_CHAT_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}

# --- Application Modules ---
from db.schemas import ChatRequest
from services.auth_service import auth_service, get_current_user
from services.ai.ai_service import ai_service
from services.audit_service import audit_service
from core.rate_limiter import limiter, RateLimits

# --- Configuration ---
logger = logging.getLogger(__name__)
router = APIRouter()


# --- JSON Serialization Helper ---
def ensure_json_serializable(obj):
    """
    Recursively convert non-JSON-serializable objects to serializable equivalents.
    Handles None, dict, list, and other types.
    """
    if obj is None:
        return None
    elif isinstance(obj, dict):
        return {k: ensure_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [ensure_json_serializable(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    else:
        # Convert other types to string representation
        return str(obj)


# --- Redis Connection (for WebSocket tracking) ---
_redis_client = None
_redis_failed = False  # Circuit breaker flag


def _get_redis():
    """Get Redis client for WebSocket connection/rate tracking."""
    global _redis_client, _redis_failed
    if _redis_failed:
        return None  # Circuit breaker open - don't retry
    if _redis_client is None:
        try:
            import redis

            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            _redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_keepalive=True,
            )
            _redis_client.ping()  # Test connection
            logger.info("Redis connected for WebSocket tracking")
        except Exception as e:
            logger.warning(
                f"Redis unavailable for WS tracking, falling back to memory: {e}"
            )
            _redis_failed = True  # Open circuit breaker
            _redis_client = None
    return _redis_client


# --- Fallback In-Memory Tracking (single-process only) ---
import time as _time

_memory_connections: Dict[str, int] = {}
_memory_message_counts: Dict[str, list] = {}  # user_id -> list of timestamps
_memory_last_activity: Dict[str, float] = {}  # user_id -> last activity timestamp

_MEMORY_CLEANUP_INTERVAL = 3600  # 1 hour - clean up inactive users


def _cleanup_inactive_users():
    """Remove users with no activity for > cleanup_interval seconds."""
    global _memory_connections, _memory_message_counts, _memory_last_activity
    now = _time.time()
    expired_users = [
        uid
        for uid, ts in list(_memory_last_activity.items())
        if now - ts > _MEMORY_CLEANUP_INTERVAL
    ]
    for uid in expired_users:
        _memory_connections.pop(uid, None)
        _memory_message_counts.pop(uid, None)
        _memory_last_activity.pop(uid, None)
    if expired_users:
        logger.info(
            f"Cleaned up {len(expired_users)} inactive user entries from memory tracking"
        )


# --- WebSocket Configuration ---
MAX_WS_CONNECTIONS_PER_USER = 5
MAX_WS_MESSAGES_PER_MINUTE = 30  # Rate limit for WebSocket messages
WS_RATE_WINDOW_SECONDS = 60


class WebSocketRateLimiter:
    """
    Redis-backed rate limiter for WebSocket messages.
    Falls back to in-memory tracking if Redis unavailable.
    """

    @staticmethod
    def check_connection_limit(user_id: str) -> bool:
        """
        Check if user can open a new WebSocket connection.
        Returns True if allowed, False if limit exceeded.
        """
        redis = _get_redis()
        if redis:
            try:
                key = f"ws:conn:{user_id}"
                count = redis.get(key)
                current = int(count) if count else 0
                return current < MAX_WS_CONNECTIONS_PER_USER
            except Exception as e:
                logger.warning(f"Redis connection check failed: {e}")

        # Fallback to memory
        return _memory_connections.get(user_id, 0) < MAX_WS_CONNECTIONS_PER_USER

    @staticmethod
    def increment_connection(user_id: str) -> int:
        """Increment connection count for user. Returns new count."""
        redis = _get_redis()
        if redis:
            try:
                key = f"ws:conn:{user_id}"
                pipe = redis.pipeline()
                pipe.incr(key)
                pipe.expire(key, 3600)  # 1 hour TTL as safety
                result = pipe.execute()
                # Update activity
                redis.set(f"ws:activity:{user_id}", time.time(), ex=7200)
                return result[0]
            except Exception as e:
                logger.warning(f"Redis increment failed: {e}")

        # Fallback to memory
        _memory_connections[user_id] = _memory_connections.get(user_id, 0) + 1
        _memory_last_activity[user_id] = time.time()
        return _memory_connections[user_id]

    @staticmethod
    def decrement_connection(user_id: str) -> int:
        """Decrement connection count for user. Returns new count."""
        redis = _get_redis()
        if redis:
            try:
                key = f"ws:conn:{user_id}"
                new_count = redis.decr(key)
                if new_count <= 0:
                    redis.delete(key)
                    return 0
                return new_count
            except Exception as e:
                logger.warning(f"Redis decrement failed: {e}")

        # Fallback to memory
        if user_id in _memory_connections:
            _memory_connections[user_id] = max(0, _memory_connections[user_id] - 1)
            if _memory_connections[user_id] == 0:
                del _memory_connections[user_id]
            return _memory_connections.get(user_id, 0)
        return 0

    @staticmethod
    def check_message_rate(user_id: str) -> tuple[bool, int]:
        """
        Check if user can send another message.
        Returns (allowed: bool, remaining: int).
        """
        redis = _get_redis()
        now = time.time()
        window_start = now - WS_RATE_WINDOW_SECONDS

        if redis:
            try:
                key = f"ws:msg:{user_id}"
                pipe = redis.pipeline()
                # Remove old entries
                pipe.zremrangebyscore(key, 0, window_start)
                # Count current entries
                pipe.zcard(key)
                # Add new entry
                pipe.zadd(key, {str(now): now})
                # Set expiry
                pipe.expire(key, WS_RATE_WINDOW_SECONDS * 2)
                results = pipe.execute()

                count = results[1]
                remaining = MAX_WS_MESSAGES_PER_MINUTE - count
                # Update activity timestamp
                redis.set(f"ws:activity:{user_id}", now, ex=7200)
                return count < MAX_WS_MESSAGES_PER_MINUTE, max(0, remaining)
            except Exception as e:
                logger.warning(f"Redis rate check failed: {e}")

        # Fallback to memory - trigger periodic cleanup
        if len(_memory_last_activity) > 100:
            _cleanup_inactive_users()

        if user_id not in _memory_message_counts:
            _memory_message_counts[user_id] = []

        # Clean old timestamps
        _memory_message_counts[user_id] = [
            ts for ts in _memory_message_counts[user_id] if ts > window_start
        ]

        count = len(_memory_message_counts[user_id])
        if count < MAX_WS_MESSAGES_PER_MINUTE:
            _memory_message_counts[user_id].append(now)
            _memory_last_activity[user_id] = now
            return True, MAX_WS_MESSAGES_PER_MINUTE - count - 1

        return False, 0

    @staticmethod
    def get_connection_count(user_id: str) -> int:
        """Get current connection count for user."""
        redis = _get_redis()
        if redis:
            try:
                count = redis.get(f"ws:conn:{user_id}")
                return int(count) if count else 0
            except Exception:
                pass
        return _memory_connections.get(user_id, 0)


# --- HTTP Chat Endpoints ---


@router.post("/datasets/{dataset_id}/chat")
@limiter.limit(RateLimits.CHAT_MESSAGE)
async def process_chat(
    request: Request,
    dataset_id: str,
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    mode: str = Query(
        "learning", description="Chat mode: learning, quick, deep, or forecast"
    ),
):
    """
    Processes a user's chat message via a standard HTTP request.

    Modes:
    - "learning": Enhanced pedagogical approach with analogies.
    - "quick": Fast responses for simple queries.
    - "deep": Comprehensive analysis for complex queries.
    - "forecast": Predictive analysis mode.

    Enterprise Features:
    - GDPR-compliant audit logging
    - Latency tracking for monitoring
    - Error tracking for reliability
    """
    valid_modes = ["learning", "quick", "deep", "forecast"]
    if mode not in valid_modes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}",
        )

    start_time = time.time()

    try:
        response = await ai_service.process_chat_message_enhanced(
            query=chat_request.message,
            dataset_id=dataset_id,
            user_id=current_user["id"],
            conversation_id=chat_request.conversation_id,
            mode=mode,
        )

        # Ensure response is JSON serializable
        response = ensure_json_serializable(response)

        logger.info(
            f"Response after serialization: {json.dumps(response, default=str)[:500]}"
        )

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Log successful interaction (async, non-blocking)
        await audit_service.log_chat_interaction(
            user_id=current_user["id"],
            dataset_id=dataset_id,
            conversation_id=response.get("conversation_id"),
            query=chat_request.message,
            response=response.get("response", response.get("response_text", "")),
            latency_ms=latency_ms,
            success=True,
            chart_generated=response.get("chart_config") is not None,
            analysis_type=mode,
        )

        return response

    except HTTPException as e:
        # Log HTTP errors
        latency_ms = (time.time() - start_time) * 1000
        await audit_service.log_chat_interaction(
            user_id=current_user["id"],
            dataset_id=dataset_id,
            conversation_id=chat_request.conversation_id,
            query=chat_request.message,
            response=str(e.detail),
            latency_ms=latency_ms,
            success=False,
            analysis_type=mode,
        )
        raise

    except Exception as e:
        # Log unexpected errors
        latency_ms = (time.time() - start_time) * 1000
        await audit_service.log_error(
            user_id=current_user["id"],
            error_type="chat_processing",
            error_message=str(e),
            context={"dataset_id": dataset_id, "mode": mode, "latency_ms": latency_ms},
        )
        logger.error(f"Chat processing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# --- Deep Analysis Endpoint (LangGraph QUIS) ---
# Import BaseModel for the request schema

from pydantic import BaseModel


class DeepAnalysisRequest(BaseModel):
    """Request schema for deep analysis."""

    query: Optional[str] = None
    novelty_threshold: Optional[float] = 0.35

    class Config:
        extra = "forbid"


class QueryExecutionRequest(BaseModel):
    """Request schema for direct SQL query execution."""

    query: str
    return_raw: bool = False  # If True, return raw data instead of interpretation

    class Config:
        extra = "forbid"


@router.post("/datasets/{dataset_id}/query")
@limiter.limit(RateLimits.CHAT_MESSAGE)
async def execute_natural_language_query(
    request: Request,
    dataset_id: str,
    query_request: QueryExecutionRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Execute a natural language query against a dataset using DuckDB.

    This endpoint converts natural language to SQL and executes it against
    the actual data, ensuring NO HALLUCINATIONS in the response.

    Flow:
    1. Natural language → SQL generation (LLM)
    2. SQL validation (safety checks)
    3. DuckDB execution (against real data)
    4. Result interpretation (LLM)

    Returns:
    - response: Natural language answer
    - sql: The generated SQL query (for transparency)
    - data: Query result data (limited to 100 rows)
    - row_count: Total rows returned
    - execution_time_ms: Query execution time

    Example queries:
    - "What is the total sales by region?"
    - "Show me the top 10 products by revenue"
    - "Average order value for customers in California"
    - "How many orders were placed last month?"
    """
    from services.query_executor import query_executor
    from services.datasets.dataset_loader import load_dataset

    start_time = time.time()

    try:
        # Get dataset
        db = auth_service._get_db()
        dataset_doc = await db.uploads.find_one(
            {"_id": dataset_id, "user_id": current_user["id"]}
        )

        if not dataset_doc:
            raise HTTPException(404, "Dataset not found.")

        if not dataset_doc.get("metadata"):
            raise HTTPException(409, "Dataset is still being processed.")

        file_path = dataset_doc.get("file_path")
        if not file_path:
            raise HTTPException(500, "Dataset file path not found.")

        # Load dataset
        df = await load_dataset(file_path)

        # Execute query
        result = await query_executor.execute_query(
            query=query_request.query,
            df=df,
            dataset_id=dataset_id,
            return_raw=query_request.return_raw,
        )

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Log interaction
        await audit_service.log_chat_interaction(
            user_id=current_user["id"],
            dataset_id=dataset_id,
            conversation_id=None,
            query=query_request.query,
            response=result.get("response", ""),
            latency_ms=latency_ms,
            success=result.get("success", False),
            chart_generated=False,
            analysis_type="sql_execution",
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query execution error: {e}", exc_info=True)
        await audit_service.log_error(
            user_id=current_user["id"],
            error_type="query_execution_error",
            error_message=str(e),
            context={"dataset_id": dataset_id, "query": query_request.query},
        )
        raise HTTPException(500, f"Query execution failed: {str(e)}")


@router.post("/datasets/{dataset_id}/analyze")
@limiter.limit(RateLimits.AI_INSIGHTS)
async def trigger_deep_analysis(
    request: Request,
    dataset_id: str,
    analysis_request: DeepAnalysisRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Trigger deep statistical analysis using LangGraph QUIS pipeline.

    This endpoint provides comprehensive dataset analysis including:
    - Correlation analysis between numeric columns
    - Group comparisons across categorical variables
    - Trend detection for temporal data
    - Anomaly identification
    - Simpson's Paradox detection
    - Novelty filtering based on user's prior knowledge

    The analysis generates:
    - Statistically validated insights with p-values and effect sizes
    - Automatically generated Plotly visualizations
    - Markdown-formatted summary suitable for chat display

    Enterprise Features:
    - Deep analysis audit logging
    - Performance metrics tracking

    Args:
        dataset_id: MongoDB ObjectId of the dataset to analyze
        analysis_request: Optional query to focus analysis, novelty threshold

    Returns:
        - response: Markdown-formatted analysis summary
        - charts: List of Plotly chart configurations
        - insights: List of approved insight objects
        - boring_filtered: Count of insights filtered as not novel
        - stats: Execution statistics
    """
    start_time = time.time()

    try:
        from services.agents.quis_graph import run_quis_analysis

        result = await run_quis_analysis(
            dataset_id=dataset_id,
            user_id=current_user["id"],
            query=analysis_request.query,
            novelty_threshold=analysis_request.novelty_threshold or 0.35,
        )

        # Log deep analysis
        latency_ms = (time.time() - start_time) * 1000
        await audit_service.log_deep_analysis(
            user_id=current_user["id"],
            dataset_id=dataset_id,
            query=analysis_request.query,
            insights_generated=len(result.get("insights", [])),
            charts_generated=len(result.get("charts", [])),
            latency_ms=latency_ms,
            success=True,
            stats=result.get("stats"),
        )

        return result

    except HTTPException:
        raise
    except ImportError as e:
        logger.warning(f"LangGraph not installed: {e}")
        return {
            "response": "Deep analysis requires additional dependencies. Please contact support.",
            "charts": [],
            "insights": [],
            "stats": {"error": "dependencies_missing"},
            "analysis_type": "error",
        }
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        await audit_service.log_deep_analysis(
            user_id=current_user["id"],
            dataset_id=dataset_id,
            query=analysis_request.query,
            insights_generated=0,
            charts_generated=0,
            latency_ms=latency_ms,
            success=False,
            stats={"error": str(e)},
        )
        logger.error(f"Deep analysis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}",
        )


# --- Conversation History Management Endpoints ---


@router.get("/conversations")
async def get_chat_conversations(current_user: dict = Depends(get_current_user)):
    """
    Retrieves all chat conversations for the current user.
    """
    return await ai_service.get_user_conversations(current_user["id"])


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=10, le=200, description="Messages per page"),
    include_archived: bool = Query(False, description="Include archived messages"),
):
    """
    Retrieves a specific chat conversation by its ID.

    Enterprise Features:
    - Pagination for large conversations
    - Optional archived message retrieval
    - Performance-optimized for scale
    """
    from services.conversations.conversation_service import get_conversation_page

    # Use paginated version for efficiency
    conversation = await get_conversation_page(
        conversation_id=conversation_id,
        user_id=current_user["id"],
        page=page,
        page_size=page_size,
        include_archived=include_archived,
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )

    return conversation


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Deletes a specific chat conversation.
    """
    success = await ai_service.delete_conversation(conversation_id, current_user["id"])
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return {"message": "Conversation deleted successfully"}


# --- Enterprise: User Analytics Endpoints ---


@router.get("/stats/user")
async def get_user_usage_stats(
    current_user: dict = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Days to include in stats"),
):
    """
    Get usage statistics for the current user.

    Returns:
    - total_queries: Number of chat queries
    - successful_queries: Number of successful queries
    - avg_latency_ms: Average response time
    - charts_generated: Number of charts created
    - success_rate: Percentage of successful queries
    """
    stats = await audit_service.get_user_stats(user_id=current_user["id"], days=days)
    return stats


@router.get("/stats/system")
async def get_system_health(
    current_user: dict = Depends(get_current_user),
    hours: int = Query(24, ge=1, le=168, description="Hours to include in stats"),
):
    """
    Get system health metrics (admin only in production).

    Returns:
    - total_requests: Total requests in time window
    - error_rate: Percentage of failed requests
    - avg_latency_ms: Average response time
    - p95_latency_ms: 95th percentile latency
    - active_users: Unique users in period
    """
    if not current_user.get("is_admin") and current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to view system health metrics.",
        )
    health = await audit_service.get_system_health(hours=hours)
    return health


@router.post("/data/export")
@limiter.limit("5/minute")
async def export_user_data(
    request: Request, current_user: dict = Depends(get_current_user)
):
    """
    GDPR: Export all user data.

    Allows users to download all their audit data
    as required by GDPR right to data portability.
    """
    data = await audit_service.export_user_data(user_id=current_user["id"])
    return {
        "user_id": current_user["id"],
        "export_date": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "record_count": len(data),
        "data": data,
    }


# --- WebSocket Chat Endpoint ---


@router.websocket("/ws/chat")
async def chat_socket(websocket: WebSocket):
    """
    Handles real-time, stateful chat communication over a WebSocket connection.
    Now supports token-by-token streaming for live typing effect.
    Authenticates the user via a token in the query parameters.

    Security features:
    - Connection limits: Max 5 concurrent WebSocket connections per user
    - Message rate limiting: Max 30 messages per minute per user
    - Redis-backed tracking for multi-worker deployments
    """
    user_id = None  # Track for cleanup in finally block
    connection_tracked = False  # Only decrement if we actually incremented

    # Accept the WebSocket connection first so the browser gets proper close frames
    await websocket.accept()

    # --- WebSocket Authentication ---
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
        token = auth_msg.get("token")
    except (asyncio.TimeoutError, Exception):
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Auth timeout or invalid format"
        )
        return

    if not token:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Missing authorization token"
        )
        return

    try:
        user_claims = auth_service.decode_token(token)
    except Exception as e:
        logger.warning(f"WebSocket token decode failed: {e}")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token"
        )
        return

    if not user_claims or not user_claims.get("id"):
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token"
        )
        return

    user = await auth_service.get_user_by_id(user_claims["id"])
    if not user:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="User not found"
        )
        return

    user_id = user["id"]

    # --- Connection Limit Check (Redis-backed) ---
    if not WebSocketRateLimiter.check_connection_limit(user_id):
        logger.warning(
            f"User {user_id} exceeded max WebSocket connections ({MAX_WS_CONNECTIONS_PER_USER})"
        )
        # Use 4008 custom close code so the client knows NOT to auto-reconnect
        await websocket.close(
            code=4008,
            reason=f"Too many connections. Maximum {MAX_WS_CONNECTIONS_PER_USER} allowed. Retry after closing other tabs.",
        )
        return

    # Track connection (Redis-backed) — only after limit check passes
    connection_count = WebSocketRateLimiter.increment_connection(user_id)
    connection_tracked = True
    logger.info(
        f"WebSocket connection established for user {user_id} (active: {connection_count})"
    )

    try:
        await websocket.send_json({"type": "auth_success"})
    except Exception as e:
        logger.warning(f"Failed to send auth_success: {e}")
        return

    async def safe_send(data: dict) -> bool:
        """Send JSON to WebSocket, returning False if the connection is closed."""
        try:
            await websocket.send_json(data)
            return True
        except (WebSocketDisconnect, RuntimeError) as e:
            logger.info(f"WebSocket send failed (client disconnected): {e}")
            return False

    try:
        while True:
            try:
                message_text = await websocket.receive_text()
                payload = json.loads(message_text)
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected by client for user {user['id']}")
                break
            except json.JSONDecodeError:
                await safe_send({"type": "error", "detail": "Invalid JSON payload"})
                continue

            # --- Message Rate Limiting ---
            rate_allowed, remaining = WebSocketRateLimiter.check_message_rate(user_id)
            if not rate_allowed:
                logger.warning(f"User {user_id} exceeded WebSocket message rate limit")
                await safe_send(
                    {
                        "type": "error",
                        "detail": f"Rate limit exceeded. Maximum {MAX_WS_MESSAGES_PER_MINUTE} messages per minute.",
                        "retry_after_seconds": WS_RATE_WINDOW_SECONDS,
                    }
                )
                continue

            # --- Cancel Message Handling ---
            if payload.get("type") == "cancel":
                client_message_id = payload.get("clientMessageId")
                logger.info(f"Cancel requested for message: {client_message_id}")
                # Send acknowledgment back to client
                await safe_send(
                    {
                        "type": "cancel_ack",
                        "clientMessageId": client_message_id,
                        "status": "cancelled",
                    }
                )
                continue

            # --- Message Processing ---
            client_message_id = payload.get("clientMessageId")
            use_streaming = payload.get("streaming", True)
            if not await safe_send(
                {
                    "type": "status",
                    "status": "processing",
                    "clientMessageId": client_message_id,
                    "rate_limit_remaining": remaining,
                }
            ):
                break  # Client disconnected

            try:
                if use_streaming:
                    # --- STREAMING MODE ---
                    # Stream tokens as they arrive from LLM
                    client_disconnected = False
                    async for chunk in ai_service.process_chat_message_streaming(
                        query=payload.get("message", "").strip(),
                        dataset_id=payload.get("datasetId"),
                        user_id=user["id"],
                        conversation_id=payload.get("conversationId"),
                    ):
                        if chunk["type"] == "token":
                            # Send each token as it arrives
                            if not await safe_send(
                                {
                                    "type": "token",
                                    "clientMessageId": client_message_id,
                                    "content": chunk["content"],
                                }
                            ):
                                client_disconnected = True
                                break

                        elif chunk["type"] == "response_complete":
                            if not await safe_send(
                                {
                                    "type": "response_complete",
                                    "clientMessageId": client_message_id,
                                    "fullResponse": chunk.get(
                                        "full_response", chunk.get("content", "")
                                    ),
                                }
                            ):
                                client_disconnected = True
                                break

                        elif chunk["type"] == "chart":
                            # Chart data ready
                            if not await safe_send(
                                {
                                    "type": "chart",
                                    "clientMessageId": client_message_id,
                                    "chartConfig": chunk["chart_config"],
                                }
                            ):
                                client_disconnected = True
                                break

                        elif chunk["type"] == "error":
                            if not await safe_send(
                                {
                                    "type": "error",
                                    "clientMessageId": client_message_id,
                                    "detail": chunk["content"],
                                }
                            ):
                                client_disconnected = True
                                break

                        elif chunk["type"] == "thinking_step":
                            if not await safe_send(
                                {
                                    "type": "thinking_step",
                                    "clientMessageId": client_message_id,
                                    "label": chunk["label"],
                                    "step": chunk.get("step", 0),
                                }
                            ):
                                client_disconnected = True
                                break

                        elif chunk["type"] == "done":
                            # Final message with conversation ID (and optional sql when from SQL execution path)
                            await safe_send(
                                {
                                    "type": "done",
                                    "clientMessageId": client_message_id,
                                    "conversationId": chunk["conversation_id"],
                                    "chartConfig": chunk.get("chart_config"),
                                    "sql": chunk.get("sql"),
                                    "insights": chunk.get("insights", []),
                                    "data_summary": chunk.get("data_summary", ""),
                                    "follow_up_suggestions": chunk.get("follow_up_suggestions", []),
                                    "rate_limit_remaining": remaining,
                                }
                            )

                    if client_disconnected:
                        logger.info(
                            f"Client disconnected mid-stream for user {user_id}, exiting loop"
                        )
                        break

                else:
                    # --- NON-STREAMING MODE (fallback) ---
                    response = await ai_service.process_chat_message_enhanced(
                        query=payload.get("message", "").strip(),
                        dataset_id=payload.get("datasetId"),
                        user_id=user["id"],
                        conversation_id=payload.get("conversationId"),
                        mode=payload.get("mode", "learning"),
                    )

                    if not await safe_send(
                        {
                            "type": "assistant_message",
                            "clientMessageId": client_message_id,
                            "conversationId": response.get("conversation_id"),
                            "message": response.get("response"),
                            "chartConfig": response.get("chart_config"),
                            "technicalDetails": response.get("technical_details"),
                            "insights": response.get("insights", []),
                            "data_summary": response.get("data_summary", ""),
                        }
                    ):
                        break

            except HTTPException as exc:
                await safe_send(
                    {
                        "type": "error",
                        "clientMessageId": client_message_id,
                        "detail": exc.detail,
                    }
                )
            except Exception as exc:
                logger.error(f"WebSocket chat processing failed: {exc}", exc_info=True)
                await safe_send(
                    {
                        "type": "error",
                        "clientMessageId": client_message_id,
                        "detail": "An internal error occurred during chat processing.",
                    }
                )

    except Exception as exc:
        logger.error(
            f"Unexpected WebSocket error for user {user_id}: {exc}", exc_info=True
        )
        if websocket.client_state.name == "CONNECTED":
            await websocket.close(
                code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error"
            )

    finally:
        # Clean up connection tracking (Redis-backed) — only if we incremented
        if user_id and connection_tracked:
            try:
                remaining_count = WebSocketRateLimiter.decrement_connection(user_id)
                logger.info(
                    f"WebSocket connection closed for user {user_id} (remaining: {remaining_count})"
                )
            except Exception as cleanup_error:
                logger.error(
                    f"Failed to decrement connection for {user_id}: {cleanup_error}",
                    exc_info=True,
                )
                # Emergency cleanup - ensure memory state is consistent
                try:
                    _memory_connections[user_id] = max(
                        0, _memory_connections.get(user_id, 0) - 1
                    )
                    if _memory_connections.get(user_id, 0) == 0:
                        _memory_connections.pop(user_id, None)
                except Exception as emergency_error:
                    logger.error(f"Emergency cleanup failed: {emergency_error}")


# ─────────────────────────────────────────────────────────────────────────────
# Chat Image Upload
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/attachments")
async def upload_chat_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload an image for display inside chat messages.
    Returns the public URL that the frontend embeds as markdown `![](url)`.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Only image uploads are allowed. Got: {file.content_type}",
        )

    contents = await file.read()
    if len(contents) > MAX_CHAT_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large. Maximum size is {MAX_CHAT_IMAGE_SIZE // (1024 * 1024)} MB.",
        )

    ext = Path(file.filename).suffix if file.filename else ".png"
    filename = f"{uuid4().hex}{ext}"
    dest = CHAT_UPLOAD_DIR / filename
    dest.write_bytes(contents)

    url = f"/static/chat-images/{filename}"
    logger.info(f"Chat image uploaded by user {current_user.get('id')}: {filename}")
    return {"url": url}
