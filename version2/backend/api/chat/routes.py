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

from db.schemas import ChatRequest
from services.auth_service import auth_service, get_current_user
from services.ai.ai_service import ai_service
from services.audit_service import audit_service
from core.rate_limiter import limiter, RateLimits

logger = logging.getLogger(__name__)
router = APIRouter()

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
    _memory_connections: Dict[str, int] = {}
    _redis_client = None

    @classmethod
    def increment_connection(cls, user_id: str) -> int:
        current = cls._memory_connections.get(user_id, 0)
        cls._memory_connections[user_id] = current + 1
        return cls._memory_connections[user_id]

    @classmethod
    def decrement_connection(cls, user_id: str) -> int:
        current = cls._memory_connections.get(user_id, 0)
        if current > 0:
            cls._memory_connections[user_id] = current - 1
        return cls._memory_connections[user_id]

    @classmethod
    def get_connection_count(cls, user_id: str) -> int:
        return cls._memory_connections.get(user_id, 0)


@router.get("/conversations")
@limiter.limit(RateLimits.CHAT_LIST)
async def list_conversations(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    from services.conversations.conversation_service import conversation_service

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
    from services.conversations.conversation_service import conversation_service

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
    from services.conversations.conversation_service import conversation_service

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
    from services.conversations.conversation_service import conversation_service

    await conversation_service.update_title(
        conversation_id=conversation_id,
        user_id=current_user["id"],
        title=title,
    )
    return {"message": "Title updated"}


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket, token: Optional[str] = None):
    from core.config import settings

    await websocket.accept()
    connection_tracked = False
    user_id = None

    try:
        if not token:
            await websocket.send_json(
                {
                    "type": "error",
                    "detail": "Authentication required. Please provide a valid token.",
                }
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        user = await get_current_user(token)
        user_id = user["id"]

        connection_count = WebSocketRateLimiter.get_connection_count(user_id)
        if connection_count >= settings.MAX_WEBSOCKET_CONNECTIONS:
            await websocket.send_json(
                {
                    "type": "error",
                    "detail": f"Maximum concurrent connections ({settings.MAX_WEBSOCKET_CONNECTIONS}) reached.",
                }
            )
            await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
            return

        connection_tracked = True
        WebSocketRateLimiter.increment_connection(user_id)

        await audit_service.log_event(
            event_type="websocket_connect",
            user_id=user_id,
            metadata={"conversation_id": None},
        )

        try:
            while True:
                data = await websocket.receive_json()
                client_message_id = data.get("clientMessageId", str(uuid4()))
                message_type = data.get("type")

                if message_type == "chat_message":
                    payload = data.get("payload", {})

                    async def safe_send(message: dict):
                        try:
                            await websocket.send_json(ensure_json_serializable(message))
                            return True
                        except Exception:
                            return False

                    try:
                        if payload.get("stream", True):
                            await safe_send(
                                {
                                    "type": "stream_start",
                                    "clientMessageId": client_message_id,
                                }
                            )

                            async for (
                                chunk
                            ) in ai_service.process_chat_message_streaming(
                                query=payload.get("message", "").strip(),
                                dataset_id=payload.get("datasetId"),
                                user_id=user["id"],
                                conversation_id=payload.get("conversationId"),
                                mode=payload.get("mode", "learning"),
                            ):
                                await safe_send(
                                    {
                                        "type": "stream_chunk",
                                        "clientMessageId": client_message_id,
                                        "chunk": chunk,
                                    }
                                )

                            await safe_send(
                                {
                                    "type": "stream_end",
                                    "clientMessageId": client_message_id,
                                }
                            )
                        else:
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
                                    "technicalDetails": response.get(
                                        "technical_details"
                                    ),
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
