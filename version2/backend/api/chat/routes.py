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
from services.chat import chat_pipeline
from services.audit import audit_service
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
        token = (
            websocket.cookies.get("access_token")
            or websocket.cookies.get("auth_token")
            or websocket.cookies.get("token")
        )

    user = await auth_service.get_user_from_token(token) if token else None

    if not user:
        dev_user_id = getattr(settings, "DEV_USER_ID", "default_user")
        if getattr(settings, "ENVIRONMENT", "development") == "development" or getattr(settings, "DEBUG", True) or not getattr(settings, "REQUIRE_AUTH", False):
            user = {"id": dev_user_id, "workspace_id": "default_workspace"}
        else:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required. Please provide a valid token.")
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

    # Register socket with the notification hub so job events (dataset
    # ready / failed / resumed) can be pushed to this user in real time.
    from services.notifications.hub import notification_hub

    notification_hub.register(user_id, websocket)

    await audit_service.log_event(
        event_type="websocket_connect",
        user_id=user_id,
        metadata={"conversation_id": None},
    )

    send_lock = asyncio.Lock()
    active_tasks = {}
    # ── Request deduplication with size cap ──
    _DEDUP_MAX_IDS = 10000
    processed_message_ids: set = set()
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

            # ── P1: Request deduplication ──
            # Skip if we've already processed this exact clientMessageId.
            # Frontend may retry on WebSocket reconnect and re-send the same message.
            if message_type in ("chat_message", "regenerate", None) and client_message_id in processed_message_ids:
                logger.info(f"Duplicate clientMessageId {client_message_id} — skipping (dedup)")
                await safe_send({
                    "type": "dedup_ack",
                    "clientMessageId": client_message_id,
                    "message": "Already processing this message.",
                })
                continue

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
                            (ChatPipeline streaming) from the consumer (WebSocket send).
                            If the consumer is slow, the queue fills up to
                            BACKPRESSURE_LIMIT and then the producer is
                            blocked, preventing unbounded memory growth.

                            If the consumer exits early (WebSocket send failure),
                            the producer checks producer_done.is_set() and has a
                            timeout on queue.put() to avoid deadlock.

                            Conversation persistence is handled internally by
                            ChatPipeline.process_streaming().
                            """
                            BACKPRESSURE_LIMIT = 256  # max queued chunks
                            SEND_TIMEOUT = 30.0       # max seconds to send one chunk

                            queue: asyncio.Queue = asyncio.Queue(maxsize=BACKPRESSURE_LIMIT)
                            producer_done = asyncio.Event()
                            producer_error: Optional[Exception] = None
                            chunk_count = 0

                            async def producer():
                                """Fetch tokens from the unified ChatPipeline and push to queue.

                                Uses a single pipeline (services.chat.ChatPipeline) that
                                replaces the old two-pipeline copilot_service + ai_service
                                fallback. The pipeline handles guardrails, context loading,
                                query understanding, agent execution, synthesis, and
                                conversation persistence internally.
                                """
                                nonlocal chunk_count, producer_error

                                # ── Signal: record query ──
                                from services.learning.signal_collector import signal_collector as _sc
                                import asyncio as _asyncio
                                _asyncio.ensure_future(
                                    _sc.record_query(
                                        user_id=user["id"],
                                        workspace_id=workspace_id,
                                        dataset_id=p.get("datasetId", ""),
                                        query_text=p.get("message", "").strip(),
                                        source="chat_pipeline",
                                    )
                                )

                                try:
                                    async for chunk in chat_pipeline.process_streaming(
                                        query=p.get("message", "").strip(),
                                        dataset_id=p.get("datasetId"),
                                        user_id=user["id"],
                                        conversation_id=p.get("conversationId"),
                                        mode=p.get("mode", "analyst"),
                                        workspace_id=workspace_id,
                                    ):
                                        if producer_done.is_set():
                                            logger.info(f"Producer stopping early for {cid} (consumer disconnected)")
                                            return
                                        try:
                                            await asyncio.wait_for(
                                                queue.put(("chunk", chunk)),
                                                timeout=5.0,
                                            )
                                        except asyncio.TimeoutError:
                                            logger.warning(f"Producer put timed out for {cid} — consumer likely disconnected")
                                            return
                                        chunk_count += 1
                                except asyncio.CancelledError:
                                    logger.info(f"Stream producer cancelled for {cid}")
                                    raise
                                except Exception as e:
                                    producer_error = e
                                    logger.error(f"Stream producer error for {cid}: {e}")
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
                                """Pull chunks from queue and send via WebSocket.

                                Conversation persistence is handled internally
                                by ChatPipeline.process_streaming().
                                """
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

                                # ── Conversation persistence handled by ChatPipeline internally ──
                                # The pipeline's process_streaming() already calls
                                # _save_and_background() which saves the conversation and
                                # runs background tasks (memory, belief update, reflection).
                                # No need for a separate save here.

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
                        processed_message_ids.add(client_message_id)
                        if len(processed_message_ids) > _DEDUP_MAX_IDS:
                            processed_message_ids.clear()
                    # Cancel is handled as a top-level message type below.
                    # Regenerate is handled as a top-level message type below.
                    else:
                        async def handle_non_stream(cid, p):
                            try:
                                result = await chat_pipeline.process(
                                    query=p.get("message", "").strip(),
                                    dataset_id=p.get("datasetId"),
                                    user_id=user["id"],
                                    conversation_id=p.get("conversationId"),
                                    workspace_id=workspace_id,
                                )

                                await safe_send(
                                    {
                                        "type": "assistant_message",
                                        "clientMessageId": cid,
                                        "conversationId": result.conversation_id,
                                        "message": result.response_text,
                                        "chartConfig": result.chart_config,
                                        "follow_up_suggestions": result.follow_up_suggestions,
                                        # ── Backward-compatible fields (safe defaults) ──
                                        "resultTable": None,
                                        "technicalDetails": None,
                                        "insights": [],
                                        "data_summary": "",
                                        "show_follow_up_suggestions": bool(result.follow_up_suggestions),
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
                        processed_message_ids.add(client_message_id)
                        if len(processed_message_ids) > _DEDUP_MAX_IDS:
                            processed_message_ids.clear()

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

            elif message_type == "cancel" and client_message_id:
                # Handle cancel message
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

            elif message_type == "regenerate" and client_message_id:
                # ── Regenerate handler ──
                # Creates a new version of an AI message, streams the pipeline
                # with skip_persist, and updates the version entry on completion.
                conv_id = payload.get("conversationId")
                message_id = payload.get("messageId")
                dataset_id = payload.get("datasetId")

                if not all([conv_id, message_id, dataset_id]):
                    await safe_send({"type": "error", "clientMessageId": client_message_id, "detail": "Missing regenerate parameters"})
                    continue

                logger.info(f"Regenerate request for message {message_id} in conv {conv_id}")

                async def _handle_regenerate_stream(cid, conv_id, msg_id, ds_id, usr):
                    from services.conversations.message_tree_service import (
                        regenerate_message,
                        complete_streaming_message,
                    )
                    from bson import ObjectId
                    from db.database import get_database as _get_db

                    BACKPRESSURE_LIMIT = 256
                    SEND_TIMEOUT = 30.0
                    queue: asyncio.Queue = asyncio.Queue(maxsize=BACKPRESSURE_LIMIT)
                    producer_done = asyncio.Event()
                    chunk_count = 0
                    version_msg_id = None

                    # Step 1: Create version entry (placeholder with status="streaming")
                    try:
                        version_msg = await regenerate_message(
                            conv_id=conv_id,
                            message_id=msg_id,
                            user_id=usr["id"],
                            new_content=None,
                            metadata={"model": settings.OPENROUTER_ROLE_MAPPING.get("narrative_story", "qwen_2.5_72b")},
                        )
                        if not version_msg:
                            await safe_send({"type": "error", "clientMessageId": cid, "detail": "Failed to create version entry"})
                            active_tasks.pop(cid, None)
                            return
                        version_msg_id = version_msg["id"]
                    except Exception as e:
                        logger.error(f"[Regen] Failed to create version entry: {e}")
                        await safe_send({"type": "error", "clientMessageId": cid, "detail": "Failed to create version entry"})
                        active_tasks.pop(cid, None)
                        return

                    # Step 2: Get parent user message content
                    parent_content = payload.get("message", "")
                    try:
                        db = _get_db()
                        conv = await db.conversations.find_one({"_id": ObjectId(conv_id), "user_id": usr["id"]})
                        if conv:
                            msgs = conv.get("messages", [])
                            target = next((m for m in msgs if m["id"] == msg_id), None)
                            if target:
                                pid = target.get("parent_id")
                                if pid:
                                    parent = next((m for m in msgs if m["id"] == pid), None)
                                    if parent:
                                        parent_content = parent.get("content", "")
                    except Exception as e:
                        logger.warning(f"[Regen] Could not find parent message, using fallback: {e}")

                    # Step 3: Producer — stream from pipeline
                    async def producer():
                        nonlocal chunk_count
                        accumulated_text = ""
                        try:
                            async for chunk in chat_pipeline.process_streaming(
                                query=parent_content,
                                dataset_id=ds_id,
                                user_id=usr["id"],
                                conversation_id=conv_id,
                                skip_persist=True,
                                workspace_id=workspace_id,
                            ):
                                if producer_done.is_set():
                                    return
                                if chunk.get("type") == "token":
                                    accumulated_text += chunk.get("content", "")
                                try:
                                    await asyncio.wait_for(queue.put(("chunk", chunk)), timeout=5.0)
                                except asyncio.TimeoutError:
                                    return
                                chunk_count += 1
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            logger.error(f"[Regen] Producer error: {e}")
                            try:
                                await asyncio.wait_for(queue.put(("error", {"type": "error", "clientMessageId": cid, "detail": str(e)})), timeout=5.0)
                            except Exception:
                                pass
                        finally:
                            # Update version entry with accumulated response
                            if version_msg_id:
                                try:
                                    await complete_streaming_message(
                                        conv_id=conv_id,
                                        user_id=usr["id"],
                                        message_id=version_msg_id,
                                        content=accumulated_text,
                                        status="completed",
                                    )
                                except Exception as e:
                                    logger.error(f"[Regen] Failed to complete version entry: {e}")
                            try:
                                await asyncio.wait_for(queue.put(("regen_done", {"versionMessageId": version_msg_id})), timeout=5.0)
                            except Exception:
                                pass
                            producer_done.set()

                    # Step 4: Consumer — send chunks to WebSocket
                    async def consumer():
                        sent_count = 0
                        try:
                            while True:
                                try:
                                    msg_type, msg_data = await asyncio.wait_for(queue.get(), timeout=SEND_TIMEOUT)
                                except asyncio.TimeoutError:
                                    break
                                if msg_type == "regen_done":
                                    await safe_send({
                                        "type": "regenerate_complete",
                                        "clientMessageId": cid,
                                        "versionMessageId": msg_data.get("versionMessageId"),
                                    })
                                    break
                                if msg_type == "error":
                                    await safe_send(msg_data)
                                    break
                                result = await safe_send({
                                    "type": "stream_chunk",
                                    "clientMessageId": cid,
                                    "chunk": msg_data,
                                })
                                sent_count += 1
                                if not result:
                                    break
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            logger.error(f"[Regen] Consumer error: {e}")
                        finally:
                            producer_done.set()

                    # Step 5: Run concurrently
                    prod_task = asyncio.create_task(producer())
                    cons_task = asyncio.create_task(consumer())
                    try:
                        await asyncio.gather(prod_task, cons_task, return_exceptions=True)
                    finally:
                        for t in [prod_task, cons_task]:
                            if not t.done():
                                t.cancel()
                        await safe_send({"type": "stream_end", "clientMessageId": cid})
                        active_tasks.pop(cid, None)

                regen_task = asyncio.create_task(
                    _handle_regenerate_stream(client_message_id, conv_id, message_id, dataset_id, user)
                )
                active_tasks[client_message_id] = regen_task
                processed_message_ids.add(client_message_id)
                if len(processed_message_ids) > _DEDUP_MAX_IDS:
                    processed_message_ids.clear()

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
            
        # Remove socket from the notification hub so we stop pushing to a
        # dead connection (and clean up the per-user registry entry).
        try:
            from services.notifications.hub import notification_hub

            notification_hub.unregister(user_id, websocket)
        except Exception:
            pass

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
