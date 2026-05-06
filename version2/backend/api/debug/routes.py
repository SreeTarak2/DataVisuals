import logging
from fastapi import APIRouter
from services.feedback.context_store import context_store

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/debug/feedback/memory/{workspace_id}/{user_id}")
async def get_user_memory_debug(workspace_id: str, user_id: str):
    memory = await context_store.get_user_memory(workspace_id, user_id)
    rules = await context_store.get_correction_rules(workspace_id)
    mappings = await context_store.get_metric_mappings(workspace_id)
    events = await context_store.get_recent_events(workspace_id, user_id, limit=20)

    return {
        "memory": memory.model_dump() if memory else None,
        "rules": [r.model_dump() for r in rules],
        "mappings": [m.model_dump() for m in mappings],
        "recent_events": [e.model_dump() for e in events],
    }
