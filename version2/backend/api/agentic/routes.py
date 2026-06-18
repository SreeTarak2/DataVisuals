import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.auth_service import get_current_user
from agents import AgentRegistry
from core.rate_limiter import limiter, RateLimits

logger = logging.getLogger(__name__)
router = APIRouter()


class AnalyzeRequest(BaseModel):
    dataset_id: str
    question: str = "Give me a full exploratory analysis of this dataset"


@router.post("/agentic/analyze")
@limiter.limit(RateLimits.AI_INSIGHTS)
async def analyze_dataset(
    request: Request,
    body: AnalyzeRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Run the 6-agent EDA pipeline and stream progress as Server-Sent Events.

    Each SSE event is a JSON object:
      {"type": "agent_start",   "agent": "planner",   "label": "Planning analysis…"}
      {"type": "agent_done",    "agent": "planner",   "data": {...}}
      {"type": "agent_error",   "agent": "...",       "error": "…"}
      {"type": "pipeline_done", "data": {full result}}
      {"type": "pipeline_error","error": "…"}

    Frontend: use EventSource or fetch with ReadableStream.
    """
    async def event_stream():
        async for chunk in AgentRegistry.run_streaming(
            "eda",
            dataset_id=body.dataset_id,
            user_id=current_user["id"],
            user_question=body.question,
        ):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disables nginx buffering
        },
    )
