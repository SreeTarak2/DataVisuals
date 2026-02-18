# backend/api/chat.py

import logging
import json
import os
import time
from typing import Dict, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)

# --- Application Modules ---
from db.schemas import ChatRequest
from services.auth_service import auth_service, get_current_user
from services.ai.ai_service import ai_service
from core.rate_limiter import limiter, RateLimits

# --- Configuration ---
logger = logging.getLogger(__name__)
router = APIRouter()

# --- Redis Connection (for WebSocket tracking) ---
_redis_client = None

def _get_redis():
    """Get Redis client for WebSocket connection/rate tracking."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            _redis_client = redis.from_url(redis_url, decode_responses=True)
            _redis_client.ping()  # Test connection
            logger.info("Redis connected for WebSocket tracking")
        except Exception as e:
            logger.warning(f"Redis unavailable for WS tracking, falling back to memory: {e}")
            _redis_client = None
    return _redis_client

# --- Fallback In-Memory Tracking (single-process only) ---
_memory_connections: Dict[str, int] = {}
_memory_message_counts: Dict[str, list] = {}  # user_id -> list of timestamps

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
                return result[0]
            except Exception as e:
                logger.warning(f"Redis increment failed: {e}")
        
        # Fallback to memory
        _memory_connections[user_id] = _memory_connections.get(user_id, 0) + 1
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
                return count < MAX_WS_MESSAGES_PER_MINUTE, max(0, remaining)
            except Exception as e:
                logger.warning(f"Redis rate check failed: {e}")
        
        # Fallback to memory
        if user_id not in _memory_message_counts:
            _memory_message_counts[user_id] = []
        
        # Clean old timestamps
        _memory_message_counts[user_id] = [
            ts for ts in _memory_message_counts[user_id] if ts > window_start
        ]
        
        count = len(_memory_message_counts[user_id])
        if count < MAX_WS_MESSAGES_PER_MINUTE:
            _memory_message_counts[user_id].append(now)
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
    mode: str = Query("learning", description="Chat mode: learning, quick, deep, or forecast")
):
    """
    Processes a user's chat message via a standard HTTP request.
    
    Modes:
    - "learning": Enhanced pedagogical approach with analogies.
    - "quick": Fast responses for simple queries.
    - "deep": Comprehensive analysis for complex queries.
    - "forecast": Predictive analysis mode.
    """
    valid_modes = ["learning", "quick", "deep", "forecast"]
    if mode not in valid_modes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}"
        )

    try:
        response = await ai_service.process_chat_message_enhanced(
            query=chat_request.message,
            dataset_id=dataset_id,
            user_id=current_user["id"],
            conversation_id=chat_request.conversation_id,
            mode=mode,
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat processing error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Import BaseModel for the request schema
from pydantic import BaseModel
from typing import Optional as OptionalType

# --- Deep Analysis Endpoint (LangGraph QUIS) ---

class DeepAnalysisRequest(BaseModel):
    """Request schema for deep analysis."""
    query: Optional[str] = None
    novelty_threshold: Optional[float] = 0.35
    
    class Config:
        extra = "forbid"

@router.post("/datasets/{dataset_id}/analyze")
@limiter.limit(RateLimits.AI_INSIGHTS)
async def trigger_deep_analysis(
    request: Request,
    dataset_id: str,
    analysis_request: DeepAnalysisRequest,
    current_user: dict = Depends(get_current_user)
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
    try:
        from services.agents.quis_graph import run_quis_analysis
        
        result = await run_quis_analysis(
            dataset_id=dataset_id,
            user_id=current_user["id"],
            query=analysis_request.query,
            novelty_threshold=analysis_request.novelty_threshold or 0.35
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
            "analysis_type": "error"
        }
    except Exception as e:
        logger.error(f"Deep analysis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
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
    conversation_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Retrieves a specific chat conversation by its ID.
    """
    conversation = await ai_service.get_conversation(conversation_id, current_user["id"])
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"message": "Conversation deleted successfully"}


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
    
    # Accept the WebSocket connection first so the browser gets proper close frames
    await websocket.accept()
    
    # --- WebSocket Authentication ---
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authorization token")
        return

    try:
        user_claims = auth_service.decode_token(token)
    except Exception as e:
        logger.warning(f"WebSocket token decode failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")
        return
        
    if not user_claims or not user_claims.get("id"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")
        return

    user = await auth_service.get_user_by_id(user_claims["id"])
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
        return
    
    user_id = user["id"]
    
    # --- Connection Limit Check (Redis-backed) ---
    if not WebSocketRateLimiter.check_connection_limit(user_id):
        logger.warning(f"User {user_id} exceeded max WebSocket connections ({MAX_WS_CONNECTIONS_PER_USER})")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, 
            reason=f"Too many connections. Maximum {MAX_WS_CONNECTIONS_PER_USER} allowed."
        )
        return
    
    # Track connection (Redis-backed)
    connection_count = WebSocketRateLimiter.increment_connection(user_id)
    logger.info(f"WebSocket connection established for user {user_id} (active: {connection_count})")

    try:
        while True:
            try:
                message_text = await websocket.receive_text()
                payload = json.loads(message_text)
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected by client for user {user['id']}")
                break
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON payload"})
                continue

            # --- Message Rate Limiting ---
            rate_allowed, remaining = WebSocketRateLimiter.check_message_rate(user_id)
            if not rate_allowed:
                logger.warning(f"User {user_id} exceeded WebSocket message rate limit")
                await websocket.send_json({
                    "type": "error",
                    "detail": f"Rate limit exceeded. Maximum {MAX_WS_MESSAGES_PER_MINUTE} messages per minute.",
                    "retry_after_seconds": WS_RATE_WINDOW_SECONDS
                })
                continue

            # --- Message Processing ---
            client_message_id = payload.get("clientMessageId")
            use_streaming = payload.get("streaming", True) 
            await websocket.send_json({
                "type": "status",
                "status": "processing",
                "clientMessageId": client_message_id,
                "rate_limit_remaining": remaining,
            })

            try:
                if use_streaming:
                    # --- STREAMING MODE ---
                    # Stream tokens as they arrive from LLM
                    async for chunk in ai_service.process_chat_message_streaming(
                        query=payload.get("message", "").strip(),
                        dataset_id=payload.get("datasetId"),
                        user_id=user["id"],
                        conversation_id=payload.get("conversationId"),
                    ):
                        if chunk["type"] == "token":
                            # Send each token as it arrives
                            await websocket.send_json({
                                "type": "token",
                                "clientMessageId": client_message_id,
                                "content": chunk["content"]
                            })
                            
                        elif chunk["type"] == "response_complete":
                            await websocket.send_json({
                                "type": "response_complete",
                                "clientMessageId": client_message_id,
                                "fullResponse": chunk.get("full_response", chunk.get("content", ""))
                            })
                            
                        elif chunk["type"] == "chart":
                            # Chart data ready
                            await websocket.send_json({
                                "type": "chart",
                                "clientMessageId": client_message_id,
                                "chartConfig": chunk["chart_config"]
                            })
                            
                        elif chunk["type"] == "error":
                            await websocket.send_json({
                                "type": "error",
                                "clientMessageId": client_message_id,
                                "detail": chunk["content"]
                            })
                            
                        elif chunk["type"] == "done":
                            # Final message with conversation ID
                            await websocket.send_json({
                                "type": "done",
                                "clientMessageId": client_message_id,
                                "conversationId": chunk["conversation_id"],
                                "chartConfig": chunk.get("chart_config")
                            })
                else:
                    # --- NON-STREAMING MODE (fallback) ---
                    response = await ai_service.process_chat_message_enhanced(
                        query=payload.get("message", "").strip(),
                        dataset_id=payload.get("datasetId"),
                        user_id=user["id"],
                        conversation_id=payload.get("conversationId"),
                        mode=payload.get("mode", "learning"),
                    )

                    await websocket.send_json({
                        "type": "assistant_message",
                        "clientMessageId": client_message_id,
                        "conversationId": response.get("conversation_id"),
                        "message": response.get("response"),
                        "chartConfig": response.get("chart_config"),
                        "technicalDetails": response.get("technical_details"),
                    })

            except HTTPException as exc:
                await websocket.send_json({
                    "type": "error",
                    "clientMessageId": client_message_id,
                    "detail": exc.detail,
                })
            except Exception as exc:
                logger.error(f"WebSocket chat processing failed: {exc}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "clientMessageId": client_message_id,
                    "detail": "An internal error occurred during chat processing."
                })

    except Exception as exc:
        logger.error(f"Unexpected WebSocket error for user {user_id}: {exc}", exc_info=True)
        if websocket.client_state.name == 'CONNECTED':
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
    
    finally:
        # Clean up connection tracking (Redis-backed)
        if user_id:
            remaining_count = WebSocketRateLimiter.decrement_connection(user_id)
            logger.info(f"WebSocket connection closed for user {user_id} (remaining: {remaining_count})")