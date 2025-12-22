# backend/api/chat.py

import logging
import json
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)

# --- Application Modules ---
from db.schemas import ChatRequest
from services.auth_service import auth_service, get_current_user
from services.ai.ai_service import ai_service

# --- Configuration ---
logger = logging.getLogger(__name__)
router = APIRouter()


# --- HTTP Chat Endpoints ---

@router.post("/datasets/{dataset_id}/chat")
async def process_chat(
    dataset_id: str,
    request: ChatRequest,
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
            query=request.message,
            dataset_id=dataset_id,
            user_id=current_user["id"],
            conversation_id=request.conversation_id,
            mode=mode,
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat processing error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


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
    """
    # --- WebSocket Authentication ---
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authorization token")
        return

    user_claims = auth_service.decode_token(token)
    if not user_claims or not user_claims.get("id"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")
        return

    user = await auth_service.get_user_by_id(user_claims["id"])
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
        return

    await websocket.accept()
    logger.info(f"WebSocket connection established for user {user['id']}")

    # --- Main WebSocket Loop ---
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

            # --- Message Processing ---
            client_message_id = payload.get("clientMessageId")
            use_streaming = payload.get("streaming", True)  # Default to streaming
            
            # Send initial "processing" status to the client
            await websocket.send_json({
                "type": "status",
                "status": "processing",
                "clientMessageId": client_message_id,
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
        logger.error(f"Unexpected WebSocket error for user {user['id']}: {exc}", exc_info=True)
        # The connection might already be closed, so this is a best-effort attempt
        if websocket.client_state.name == 'CONNECTED':
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")