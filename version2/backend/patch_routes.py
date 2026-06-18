import re

with open('/home/vamsi/nothing/signal/version2/backend/api/chat/routes.py', 'r') as f:
    content = f.read()

# 1. Add send_lock and active_tasks
target1 = """    await audit_service.log_event(
        event_type="websocket_connect",
        user_id=user_id,
        metadata={"conversation_id": None},
    )

    async def safe_send(message: dict):"""

replacement1 = """    await audit_service.log_event(
        event_type="websocket_connect",
        user_id=user_id,
        metadata={"conversation_id": None},
    )

    import asyncio
    send_lock = asyncio.Lock()
    active_tasks = {}

    async def safe_send(message: dict):
        async with send_lock:"""

content = content.replace(target1, replacement1)

# 2. Refactor stream block
target2 = """                        try:
                            chunk_count = 0
                            async for (
                                chunk
                            ) in ai_service.process_chat_message_streaming(
                                query=payload.get("message", "").strip(),
                                dataset_id=payload.get("datasetId"),
                                user_id=user["id"],
                                conversation_id=payload.get("conversationId"),
                            ):
                                chunk_type = chunk.get("type", "unknown")
                                if chunk_type == "done":
                                    logger.info(f"📤 Streaming: Sending DONE chunk ({chunk_count} chunks total)")
                                elif chunk_count % 20 == 0 or chunk_type not in ["token"]:
                                    logger.debug(f"📤 Streaming: Chunk {chunk_count} type={chunk_type}")
                                chunk_count += 1
                                
                                send_result = await safe_send(
                                    {
                                        "type": "stream_chunk",
                                        "clientMessageId": client_message_id,
                                        "chunk": chunk,
                                    }
                                )
                                if not send_result:
                                    logger.error(f"Failed to send stream chunk; stopping stream (chunk_type={chunk_type})")
                                    break
                            
                            logger.info(f"✓ Streaming: Generator finished (sent {chunk_count} total chunks)")
                        except Exception as streaming_error:
                            logger.error(
                                f"Streaming error: {streaming_error}", exc_info=True
                            )
                            await safe_send(
                                {
                                    "type": "error",
                                    "clientMessageId": client_message_id,
                                    "detail": str(streaming_error),
                                }
                            )

                        await safe_send(
                            {
                                "type": "stream_end",
                                "clientMessageId": client_message_id,
                            }
                        )"""

replacement2 = """                        async def handle_stream(cid, p):
                            try:
                                chunk_count = 0
                                async for chunk in ai_service.process_chat_message_streaming(
                                    query=p.get("message", "").strip(),
                                    dataset_id=p.get("datasetId"),
                                    user_id=user["id"],
                                    conversation_id=p.get("conversationId"),
                                ):
                                    chunk_type = chunk.get("type", "unknown")
                                    if chunk_type == "done":
                                        logger.info(f"📤 Streaming: Sending DONE chunk ({chunk_count} chunks total)")
                                    elif chunk_count % 20 == 0 or chunk_type not in ["token"]:
                                        logger.debug(f"📤 Streaming: Chunk {chunk_count} type={chunk_type}")
                                    chunk_count += 1
                                    
                                    send_result = await safe_send(
                                        {
                                            "type": "stream_chunk",
                                            "clientMessageId": cid,
                                            "chunk": chunk,
                                        }
                                    )
                                    if not send_result:
                                        logger.error(f"Failed to send stream chunk; stopping stream (chunk_type={chunk_type})")
                                        break
                                
                                logger.info(f"✓ Streaming: Generator finished (sent {chunk_count} total chunks)")
                            except asyncio.CancelledError:
                                logger.info(f"Streaming task cancelled for {cid}")
                                raise
                            except Exception as streaming_error:
                                logger.error(f"Streaming error: {streaming_error}", exc_info=True)
                                await safe_send(
                                    {
                                        "type": "error",
                                        "clientMessageId": cid,
                                        "detail": str(streaming_error),
                                    }
                                )
                            finally:
                                await safe_send(
                                    {
                                        "type": "stream_end",
                                        "clientMessageId": cid,
                                    }
                                )
                                active_tasks.pop(cid, None)

                        task = asyncio.create_task(handle_stream(client_message_id, payload))
                        active_tasks[client_message_id] = task"""

content = content.replace(target2, replacement2)

# 3. Handle cancel
target3 = """                        logger.info(
                            f"Cancel request received for message {client_message_id}"
                        )
                        # We need to cancel the ongoing streaming operation
                        # This is a placeholder - the actual cancellation logic needs to be implemented
                        # in ai_service.process_chat_message_streaming to support cancellation
                        # For now, we'll just acknowledge the cancel request
                        await safe_send(
                            {
                                "type": "cancel_ack",
                                "clientMessageId": client_message_id,
                            }
                        )"""

replacement3 = """                        logger.info(f"Cancel request received for message {client_message_id}")
                        task_to_cancel = active_tasks.get(client_message_id)
                        if task_to_cancel:
                            task_to_cancel.cancel()
                            logger.info(f"Cancelled task for {client_message_id}")
                        
                        await safe_send(
                            {
                                "type": "cancel_ack",
                                "clientMessageId": client_message_id,
                            }
                        )"""

content = content.replace(target3, replacement3)

# 4. Handle non-streaming message
target4 = """                    else:
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
                                "resultTable": response.get("result_table"),
                                "technicalDetails": response.get(
                                    "technical_details"
                                ),
                                "insights": response.get("insights", []),
                                "data_summary": response.get("data_summary", ""),
                                "follow_up_suggestions": response.get(
                                    "follow_up_suggestions", []
                                ),
                                "show_follow_up_suggestions": response.get(
                                    "show_follow_up_suggestions", False
                                ),
                            }
                        ):
                            break"""

replacement4 = """                    else:
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
                        active_tasks[client_message_id] = task"""

content = content.replace(target4, replacement4)


# 5. Cleanup at end
target5 = """    finally:
        if user_id and connection_tracked:"""

replacement5 = """    finally:
        for t in active_tasks.values():
            t.cancel()
            
        if user_id and connection_tracked:"""

content = content.replace(target5, replacement5)

with open('/home/vamsi/nothing/signal/version2/backend/api/chat/routes.py', 'w') as f:
    f.write(content)

print("routes.py updated successfully")
