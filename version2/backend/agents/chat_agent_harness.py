from typing import Any, AsyncGenerator, Dict, Optional

from agents.chat.chat_agent import ChatAgent


chat_agent = ChatAgent()


async def run_chat_agent_streaming(
    query: str,
    dataset_id: str,
    user_id: str,
    df: Any,
    schema: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    yield {
        "type": "thinking_step",
        "label": "Analyzing your question",
        "step": 1,
    }

    # Preferred path for production: real streaming if the agent exposes it.
    if hasattr(chat_agent, "run_streaming"):
        full_response = ""
        async for event in chat_agent.run_streaming(
            query=query,
            dataset_id=dataset_id,
            user_id=user_id,
            df=df,
            dataset_schema=schema,
        ):
            if event.get("type") == "token":
                token = str(event.get("content", ""))
                full_response += token
                yield {"type": "token", "content": token}
            elif event.get("type") in {"thinking_step", "error"}:
                yield event
            elif event.get("type") == "done":
                trace = event.get("trace", {})
                yield {
                    "type": "response_complete",
                    "full_response": full_response,
                }
                yield {
                    "type": "agent_trace",
                    "tools_used": trace.get("tools_used", []),
                    "iterations": trace.get("iterations", 0),
                }
                return

    # Fallback path: no fake token streaming in production mode.
    result = await chat_agent.run(
        query=query,
        dataset_id=dataset_id,
        user_id=user_id,
        df=df,
        dataset_schema=schema,
    )

    yield {
        "type": "thinking_step",
        "label": "Preparing answer",
        "step": 2,
    }
    yield {"type": "response_complete", "full_response": result.get("response", "")}
    yield {
        "type": "agent_trace",
        "tools_used": result.get("tools_used", []),
        "iterations": result.get("iterations", 0),
    }
