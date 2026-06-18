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
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db.schemas import ChatRequest
from services.auth_service import auth_service, get_current_user
from services.ai.ai_service import ai_service
from services.audit_service import audit_service
from services.feedback.event_logger import event_logger
from services.feedback.user_memory import user_memory_service
from services.feedback.signal_classifier import signal_classifier
from core.rate_limiter import limiter, RateLimits

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

CHAT_UPLOAD_DIR = (
    Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / "chat_images"
)
CHAT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_CHAT_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def ensure_json_serializable(obj):
    if obj is None:
        return None
    elif isinstance(obj, dict):
        return {k: ensure_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [ensure_json_serializable(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    else:
        return str(obj)


class WebSocketRateLimiter:
    """Per-user WebSocket connection limiter with Redis persistence.

    Uses Redis INCR/DECR for atomic connection counting across workers.
    Falls back to in-memory dict when Redis is unavailable.
    Connections auto-expire after 2 hours to prevent stale counts
    if a worker crashes without decrementing.
    """
    _CONNECTION_TTL = 7200  # 2 hours — auto-cleanup on worker crash
    _memory_connections: Dict[str, int] = {}
    _redis_client = None
    _redis_available = False

    @classmethod
    def _get_redis_key(cls, user_id: str) -> str:
        return f"ws:connections:{user_id}"

    @classmethod
    def _init_redis(cls):
        """Lazily initialize Redis client from environment."""
        if cls._redis_client is not None:
            return
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            logger.info("WebSocketRateLimiter: REDIS_URL not set, using in-memory")
            cls._redis_client = None
            cls._redis_available = False
            return
        try:
            import redis as redis_lib
            client = redis_lib.from_url(redis_url, decode_responses=True)
            client.ping()
            cls._redis_client = client
            cls._redis_available = True
            logger.info(f"WebSocketRateLimiter: Connected to Redis at {redis_url}")
        except Exception as e:
            logger.warning(f"WebSocketRateLimiter: Redis unavailable ({e}), using in-memory")
            cls._redis_client = None
            cls._redis_available = False

    @classmethod
    def increment_connection(cls, user_id: str) -> int:
        cls._init_redis()
        if cls._redis_available and cls._redis_client is not None:
            try:
                key = cls._get_redis_key(user_id)
                count = cls._redis_client.incr(key)
                cls._redis_client.expire(key, cls._CONNECTION_TTL)
                return count
            except Exception as e:
                logger.warning(f"WebSocketRateLimiter: Redis INCR failed ({e}), falling back to memory")
                cls._redis_client = None
                cls._redis_available = False

        # In-memory fallback
        current = cls._memory_connections.get(user_id, 0)
        cls._memory_connections[user_id] = current + 1
        return cls._memory_connections[user_id]

    @classmethod
    def decrement_connection(cls, user_id: str) -> int:
        cls._init_redis()
        if cls._redis_available and cls._redis_client is not None:
            try:
                key = cls._get_redis_key(user_id)
                count = cls._redis_client.decr(key)
                if count < 0:
                    # Shouldn't happen, but guard against negative counts
                    count = 0
                    cls._redis_client.delete(key)
                elif count == 0:
                    cls._redis_client.delete(key)
                else:
                    # Refresh TTL on every operation to prevent premature expiry
                    # while the connection is alive across workers
                    cls._redis_client.expire(key, cls._CONNECTION_TTL)
                return max(0, count)
            except Exception as e:
                logger.warning(f"WebSocketRateLimiter: Redis DECR failed ({e}), falling back to memory")
                cls._redis_client = None
                cls._redis_available = False

        # In-memory fallback
        current = cls._memory_connections.get(user_id, 0)
        if current > 0:
            cls._memory_connections[user_id] = current - 1
        return cls._memory_connections.get(user_id, 0)

    @classmethod
    def get_connection_count(cls, user_id: str) -> int:
        cls._init_redis()
        if cls._redis_available and cls._redis_client is not None:
            try:
                key = cls._get_redis_key(user_id)
                val = cls._redis_client.get(key)
                return int(val) if val is not None else 0
            except Exception as e:
                logger.warning(f"WebSocketRateLimiter: Redis GET failed ({e}), falling back to memory")
                cls._redis_client = None
                cls._redis_available = False

        return cls._memory_connections.get(user_id, 0)


from services.conversations import conversation_service


@router.get("/conversations")
@limiter.limit(RateLimits.CHAT_LIST)
async def list_conversations(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    conversations = await conversation_service.get_user_conversations(
        user_id=current_user["id"],
        page=page,
        limit=limit,
    )
    return conversations


@router.get("/conversations/{conversation_id}")
@limiter.limit(RateLimits.CHAT_LIST)
async def get_conversation(
    request: Request,
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    conversation = await conversation_service.get_conversation(
        conversation_id=conversation_id,
        user_id=current_user["id"],
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.delete("/conversations/{conversation_id}")
@limiter.limit(RateLimits.CHAT_LIST)
async def delete_conversation(
    request: Request,
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    await conversation_service.delete_conversation(
        conversation_id=conversation_id,
        user_id=current_user["id"],
    )
    return {"message": "Conversation deleted"}


@router.post("/conversations/{conversation_id}/title")
@limiter.limit(RateLimits.CHAT_LIST)
async def update_conversation_title(
    request: Request,
    conversation_id: str,
    title: str,
    current_user: dict = Depends(get_current_user),
):
    await conversation_service.update_title(
        conversation_id=conversation_id,
        user_id=current_user["id"],
        title=title,
    )
    return {"message": "Title updated"}


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket, token: Optional[str] = None):
    from core.config import settings

    connection_tracked = False
    user_id = None

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required. Please provide a valid token in query parameters.")
        return

    user = await auth_service.get_user_from_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    await websocket.accept()

    user_id = user["id"]
    workspace_id = user.get("workspace_id", user_id)
    event_logger.start_session(user_id, workspace_id)

    try:
        await websocket.send_json({"type": "auth_success"})
    except Exception as e:
        logger.error(f"Failed to send auth success: {e}")
        return

    connection_tracked = True
    WebSocketRateLimiter.increment_connection(user_id)

    await audit_service.log_event(
        event_type="websocket_connect",
        user_id=user_id,
        metadata={"conversation_id": None},
    )

    send_lock = asyncio.Lock()
    active_tasks = {}
    last_pong_time = asyncio.get_event_loop().time()
    heartbeat_task = None

    async def safe_send(message: dict):
        async with send_lock:
            try:
                # If the client socket is not connected, avoid attempting to send.
                try:
                    client_state = websocket.client_state.name
                    app_state = websocket.application_state.name
                except Exception:
                    client_state = 'UNKNOWN'
                    app_state = 'UNKNOWN'
                if client_state != 'CONNECTED' or app_state != 'CONNECTED':
                    logger.debug(f"Refusing to send message because websocket state is client={client_state}, app={app_state}")
                    return False

                await websocket.send_json(ensure_json_serializable(message))
                return True
            except Exception as send_err:
                logger.error(f"Failed to send WebSocket message (type={message.get('type')}): {send_err}")
                return False

    async def server_heartbeat():
        """Send heartbeat pings every 30s to keep connection alive through proxies/firewalls."""
        nonlocal last_pong_time
        try:
            while True:
                await asyncio.sleep(30)
                # Check if we've received a pong in the last 90s
                elapsed = asyncio.get_event_loop().time() - last_pong_time
                if elapsed > 90:
                    logger.warning(f"No pong from client {user_id} in {elapsed:.0f}s — closing connection")
                    await websocket.close(code=1000, reason="Heartbeat timeout")
                    break
                
                # Send ping
                await safe_send({
                    "type": "server_ping",
                    "timestamp": asyncio.get_event_loop().time()
                })
        except asyncio.CancelledError:
            logger.debug(f"Server heartbeat cancelled for {user_id}")
        except Exception as e:
            logger.error(f"Server heartbeat error for {user_id}: {e}")

    try:
        # Start server heartbeat task
        heartbeat_task = asyncio.create_task(server_heartbeat())
        
        while True:
            try:
                try:
                    if websocket.client_state.name != "CONNECTED" or websocket.application_state.name != "CONNECTED":
                        logger.info(f"WebSocket no longer connected (client: {websocket.client_state.name}, app: {websocket.application_state.name}). Exiting loop.")
                        break
                except Exception:
                    pass
                data = await websocket.receive_json()
            except WebSocketDisconnect as wsd:
                logger.info(f"WebSocket disconnected by client {user_id}: {wsd}")
                break
            except Exception as recv_err:
                logger.error(f"Failed to receive websocket message: {recv_err}", exc_info=True)
                break
            
            client_message_id = data.get("clientMessageId", str(uuid4()))
            message_type = data.get("type")
            payload = data.get("payload", {}) if isinstance(data.get("payload", {}), dict) else {}

            # Application-level heartbeat: respond to ping with pong
            if message_type == 'ping':
                await safe_send({"type": "pong", "timestamp": data.get("timestamp")})
                continue
            
            # Track pong receipts to detect dead connections
            if message_type == 'pong' or message_type == 'server_pong':
                last_pong_time = asyncio.get_event_loop().time()
                logger.debug(f"Received pong from client {user_id}")
                continue
            
            legacy_chat_message = (
                message_type is None
                and (
                    "message" in data
                    or "datasetId" in data
                    or "conversationId" in data
                    or "streaming" in data
                )
            )

            if message_type == "chat_message" or legacy_chat_message:
                if legacy_chat_message:
                    payload = data

                try:
                    if payload.get("stream", True):
                        await safe_send(
                            {
                                "type": "stream_start",
                                "clientMessageId": client_message_id,
                            }
                        )

                        async def handle_stream(cid, p):
                            """
                            Stream handler with queue-based backpressure.

                            Uses an asyncio.Queue to decouple the token producer
                            (LLM streaming) from the consumer (WebSocket send).
                            If the consumer is slow, the queue fills up to
                            BACKPRESSURE_LIMIT and then the producer is
                            blocked, preventing unbounded memory growth.

                            If the consumer exits early (WebSocket send failure),
                            the producer checks producer_done.is_set() and has a
                            timeout on queue.put() to avoid deadlock.
                            """
                            BACKPRESSURE_LIMIT = 256  # max queued chunks
                            SEND_TIMEOUT = 30.0       # max seconds to send one chunk

                            queue: asyncio.Queue = asyncio.Queue(maxsize=BACKPRESSURE_LIMIT)
                            producer_done = asyncio.Event()
                            producer_error: Optional[Exception] = None
                            chunk_count = 0

                            async def producer():
                                """Fetch tokens from LLM and push to queue."""
                                nonlocal chunk_count, producer_error
                                try:
                                    async for chunk in ai_service.process_chat_message_streaming(
                                        query=p.get("message", "").strip(),
                                        dataset_id=p.get("datasetId"),
                                        user_id=user["id"],
                                        conversation_id=p.get("conversationId"),
                                    ):
                                        # Check if consumer has exited early
                                        if producer_done.is_set():
                                            logger.info(f"Producer stopping early for {cid} (consumer disconnected)")
                                            break
                                        # Put with timeout to prevent deadlock if consumer exits mid-put
                                        try:
                                            await asyncio.wait_for(
                                                queue.put(("chunk", chunk)),
                                                timeout=5.0,
                                            )
                                        except asyncio.TimeoutError:
                                            logger.warning(f"Producer put timed out for {cid} — consumer likely disconnected")
                                            break
                                        chunk_count += 1
                                except asyncio.CancelledError:
                                    logger.info(f"Stream producer cancelled for {cid}")
                                    raise
                                except Exception as e:
                                    producer_error = e
                                    try:
                                        await asyncio.wait_for(
                                            queue.put(("error", {
                                                "type": "error",
                                                "clientMessageId": cid,
                                                "detail": str(e),
                                            })),
                                            timeout=5.0,
                                        )
                                    except Exception:
                                        pass
                                finally:
                                    # Best-effort: signal done even if queue is full
                                    try:
                                        await asyncio.wait_for(
                                            queue.put(("done", None)),
                                            timeout=5.0,
                                        )
                                    except Exception:
                                        pass
                                    producer_done.set()

                            async def consumer():
                                """Pull chunks from queue and send via WebSocket."""
                                sent_count = 0
                                try:
                                    while True:
                                        try:
                                            msg_type, msg_data = await asyncio.wait_for(
                                                queue.get(), timeout=SEND_TIMEOUT
                                            )
                                        except asyncio.TimeoutError:
                                            logger.warning(
                                                f"Stream consumer timeout after {SEND_TIMEOUT}s "
                                                f"for {cid} (sent {sent_count} chunks)"
                                            )
                                            break

                                        if msg_type == "done":
                                            break

                                        if msg_type == "error":
                                            await safe_send(msg_data)
                                            break

                                        chunk = msg_data
                                        send_result = await safe_send({
                                            "type": "stream_chunk",
                                            "clientMessageId": cid,
                                            "chunk": chunk,
                                        })
                                        sent_count += 1

                                        if not send_result:
                                            logger.error(
                                                f"Failed to send stream chunk; stopping consumer "
                                                f"(type={chunk.get('type')})"
                                            )
                                            break
                                except asyncio.CancelledError:
                                    logger.info(f"Stream consumer cancelled for {cid}")
                                    raise
                                except Exception as e:
                                    logger.error(f"Stream consumer error for {cid}: {e}")
                                finally:
                                    # Signal producer to stop
                                    producer_done.set()

                            # Run producer and consumer concurrently
                            prod_task = asyncio.create_task(producer())
                            cons_task = asyncio.create_task(consumer())

                            try:
                                # Check gather results explicitly to surface exceptions
                                results = await asyncio.gather(prod_task, cons_task, return_exceptions=True)
                                for i, (task_name, result) in enumerate([("producer", results[0]), ("consumer", results[1])]):
                                    if isinstance(result, Exception):
                                        if isinstance(result, asyncio.CancelledError):
                                            logger.info(f"Stream {task_name} cancelled for {cid}")
                                        else:
                                            logger.error(f"Stream {task_name} error for {cid}: {result}")
                                            if i == 0:  # producer error — surface to consumer
                                                await safe_send({
                                                    "type": "error",
                                                    "clientMessageId": cid,
                                                    "detail": str(result),
                                                })
                            finally:
                                # Ensure both tasks are cancelled if one failed
                                if not prod_task.done():
                                    prod_task.cancel()
                                if not cons_task.done():
                                    cons_task.cancel()

                                logger.info(
                                    f"✓ Streaming finished for {cid}: {chunk_count} chunks "
                                    f"from producer, sent via consumer"
                                )
                                await safe_send({
                                    "type": "stream_end",
                                    "clientMessageId": cid,
                                })
                                active_tasks.pop(cid, None)

                        task = asyncio.create_task(handle_stream(client_message_id, payload))
                        active_tasks[client_message_id] = task
                    elif message_type == "cancel" and client_message_id:
                        # Handle cancel message
                        # The frontend sends a cancel message with the clientMessageId to stop
                        # an ongoing streaming operation
                        logger.info(f"Cancel request received for message {client_message_id}")
                        task_to_cancel = active_tasks.get(client_message_id)
                        if task_to_cancel:
                            task_to_cancel.cancel()
                            logger.info(f"Cancelled task for {client_message_id}")
                        
                        await safe_send(
                            {
                                "type": "cancel_ack",
                                "clientMessageId": client_message_id,
                            }
                        )
                    else:
                        async def handle_non_stream(cid, p):
                            try:
                                response = await ai_service.process_chat_message_enhanced(
                                    query=p.get("message", "").strip(),
                                    dataset_id=p.get("datasetId"),
                                    user_id=user["id"],
                                    conversation_id=p.get("conversationId"),
                                    mode=p.get("mode", "learning"),
                                )

                                await safe_send(
                                    {
                                        "type": "assistant_message",
                                        "clientMessageId": cid,
                                        "conversationId": response.get("conversation_id"),
                                        "message": response.get("response"),
                                        "chartConfig": response.get("chart_config"),
                                        "resultTable": response.get("result_table"),
                                        "technicalDetails": response.get("technical_details"),
                                        "insights": response.get("insights", []),
                                        "data_summary": response.get("data_summary", ""),
                                        "follow_up_suggestions": response.get("follow_up_suggestions", []),
                                        "show_follow_up_suggestions": response.get("show_follow_up_suggestions", False),
                                    }
                                )
                            except asyncio.CancelledError:
                                logger.info(f"Non-streaming task cancelled for {cid}")
                                raise
                            except Exception as e:
                                logger.error(f"Non-streaming task failed: {e}", exc_info=True)
                            finally:
                                active_tasks.pop(cid, None)
                                
                        task = asyncio.create_task(handle_non_stream(client_message_id, payload))
                        active_tasks[client_message_id] = task

                except HTTPException as exc:
                    await safe_send(
                        {
                            "type": "error",
                            "clientMessageId": client_message_id,
                            "detail": exc.detail,
                        }
                    )
                except Exception as exc:
                    logger.error(
                        f"WebSocket chat processing failed: {exc}", exc_info=True
                    )
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
        # Cancel heartbeat task
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        
        for t in active_tasks.values():
            t.cancel()
            
        if user_id and connection_tracked:
            try:
                remaining_count = WebSocketRateLimiter.decrement_connection(user_id)
                logger.info(
                    f"WebSocket connection closed for user {user_id} (remaining: {remaining_count})"
                )
                event_logger.end_session()
            except Exception as cleanup_error:
                logger.error(
                    f"Failed to decrement connection for {user_id}: {cleanup_error}",
                    exc_info=True,
                )
                try:
                    _memory_connections = WebSocketRateLimiter._memory_connections
                    _memory_connections[user_id] = max(
                        0, _memory_connections.get(user_id, 0) - 1
                    )
                    if _memory_connections.get(user_id, 0) == 0:
                        _memory_connections.pop(user_id, None)
                except Exception as emergency_error:
                    logger.error(f"Emergency cleanup failed: {emergency_error}")


@router.post("/attachments")
async def upload_chat_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
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

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
        file_ext = ".png"

    unique_filename = f"{uuid4().hex}{file_ext}"
    file_path = CHAT_UPLOAD_DIR / unique_filename

    try:
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        logger.error(f"Failed to save chat image: {e}")
        raise HTTPException(status_code=500, detail="Failed to save image")

    public_url = f"/uploads/chat_images/{unique_filename}"
    return {"url": public_url, "filename": unique_filename}
