# backend/api/agentic.py

"""
Agentic QUIS API Endpoints
==========================
FastAPI routes for the LangGraph-based agentic analysis system.

Endpoints:
- POST /agentic/analyze - Run agentic QUIS analysis
- POST /agentic/feedback - Submit user feedback (thumbs up/down)
- GET /agentic/beliefs - List user's Belief Store
- DELETE /agentic/beliefs/{belief_id} - Remove a belief
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

from services.auth_service import get_current_user
from db.database import get_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agentic", tags=["Agentic AI"])


# ============================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================

class AgenticAnalysisRequest(BaseModel):
    """Request to run agentic QUIS analysis."""
    dataset_id: str = Field(..., description="Dataset to analyze")
    novelty_threshold: float = Field(0.35, ge=0.0, le=1.0, description="Minimum novelty to show (0-1)")
    max_questions: int = Field(15, ge=1, le=50, description="Maximum questions to generate")


class AgenticAnalysisResponse(BaseModel):
    """Response from agentic analysis."""
    thread_id: str
    final_response: str
    novel_insights: List[dict]
    filtered_insights: List[dict]
    stats: dict


class FeedbackRequest(BaseModel):
    """User feedback on an insight."""
    insight_text: str = Field(..., description="The insight text")
    feedback_type: str = Field(..., pattern="^(useful|known|wrong)$", description="Type of feedback")
    dataset_id: Optional[str] = Field(None, description="Optional dataset reference")


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""
    success: bool
    belief_id: Optional[str] = None
    message: str


class BeliefListResponse(BaseModel):
    """List of user beliefs."""
    beliefs: List[dict]
    total_count: int


# ============================================================
# ENDPOINTS
# ============================================================

@router.post("/analyze", response_model=AgenticAnalysisResponse)
async def run_agentic_analysis(
    request: AgenticAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Run agentic QUIS analysis on a dataset.
    
    This uses the LangGraph-based pipeline with:
    - Question generation (QUGEN)
    - Statistical analysis (ISGEN)  
    - Self-correction (Critic loops)
    - Subjective Novelty filtering
    
    Returns only insights that are statistically significant AND
    novel to this specific user.
    """
    user_id = current_user["id"]
    dataset_id = request.dataset_id
    
    logger.info(f"Starting agentic analysis for user {user_id}, dataset {dataset_id}")
    
    try:
        # Get dataset from database
        from bson import ObjectId
        db = get_database()
        dataset = await db.datasets.find_one({
            "_id": ObjectId(dataset_id),
            "user_id": user_id
        })
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found"
            )
        
        # Extract schema info
        columns = dataset.get("columns", [])
        data_schema = str({col["name"]: col.get("type", "unknown") for col in columns})
        sample_rows = dataset.get("preview_data", "")[:500]  # First 500 chars
        row_count = dataset.get("row_count", 0)
        column_count = len(columns)
        
        # Import and run agentic QUIS
        try:
            from services.agents import run_agentic_quis
            
            result = await run_agentic_quis(
                dataset_id=dataset_id,
                user_id=user_id,
                data_schema=data_schema,
                sample_rows=sample_rows,
                row_count=row_count,
                column_count=column_count,
                novelty_threshold=request.novelty_threshold
            )
            
            return AgenticAnalysisResponse(
                thread_id=result.get("stats", {}).get("thread_id", "unknown"),
                final_response=result.get("final_response", "Analysis complete."),
                novel_insights=result.get("approved_insights", []),
                filtered_insights=result.get("boring_insights", []),
                stats=result.get("stats", {})
            )
            
        except ImportError as e:
            logger.error(f"LangGraph not available: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Agentic analysis requires LangGraph. Install with: pip install langgraph"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agentic analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit feedback on an insight.
    
    Feedback types:
    - "useful": User found the insight valuable (adds to Belief Store with moderate confidence)
    - "known": User already knew this (adds to Belief Store with high confidence, prevents future repeats)
    - "wrong": Insight was incorrect (logged for debugging, does not add to Belief Store)
    """
    user_id = current_user["id"]
    
    try:
        from services.agents.belief_store import get_belief_store
        belief_store = get_belief_store()
        
        belief_id = None
        message = ""
        
        if request.feedback_type == "useful":
            belief_id = await belief_store.accept_insight(
                user_id=user_id,
                insight_text=request.insight_text,
                dataset_id=request.dataset_id
            )
            message = "Thank you! This insight has been noted."
            
        elif request.feedback_type == "known":
            belief_id = await belief_store.mark_as_known(
                user_id=user_id,
                insight_text=request.insight_text,
                dataset_id=request.dataset_id
            )
            message = "Got it! We won't show you similar insights in the future."
            
        elif request.feedback_type == "wrong":
            # Log but don't add to Belief Store
            logger.warning(f"User {user_id} marked insight as wrong: {request.insight_text[:100]}...")
            message = "Thank you for the feedback. We'll work on improving accuracy."
        
        return FeedbackResponse(
            success=True,
            belief_id=belief_id,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Feedback submission failed: {e}")
        return FeedbackResponse(
            success=False,
            message=f"Failed to process feedback: {str(e)}"
        )


@router.get("/beliefs", response_model=BeliefListResponse)
async def list_beliefs(
    current_user: dict = Depends(get_current_user),
    limit: int = 50
):
    """
    List all beliefs in the user's Belief Store.
    
    Returns the user's accumulated knowledge that is used
    to filter "boring" insights.
    """
    user_id = current_user["id"]
    
    try:
        from services.agents.belief_store import get_belief_store
        belief_store = get_belief_store()
        
        # Get belief count
        count = await belief_store.get_belief_count(user_id)
        
        # Query all beliefs (using empty query to get all)
        if count > 0:
            # Use a generic query to retrieve beliefs
            beliefs = await belief_store.query_similar_beliefs(
                user_id=user_id,
                query_text="",  # Empty query returns random sample
                n_results=min(limit, count)
            )
        else:
            beliefs = []
        
        return BeliefListResponse(
            beliefs=beliefs,
            total_count=count
        )
        
    except Exception as e:
        logger.error(f"Failed to list beliefs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve beliefs: {str(e)}"
        )


@router.delete("/beliefs/{belief_id}")
async def delete_belief(
    belief_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a specific belief from the Belief Store.
    
    Use this if the user wants to "forget" something and
    start seeing related insights again.
    """
    user_id = current_user["id"]
    
    try:
        from services.agents.belief_store import get_belief_store
        belief_store = get_belief_store()
        
        success = await belief_store.delete_belief(user_id, belief_id)
        
        if success:
            return {"success": True, "message": "Belief deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Belief not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete belief: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete belief: {str(e)}"
        )


@router.delete("/beliefs")
async def clear_all_beliefs(
    current_user: dict = Depends(get_current_user)
):
    """
    Clear ALL beliefs for the current user.
    
    ⚠️ WARNING: This resets the user's Belief Store completely.
    All novelty filtering will start fresh.
    """
    user_id = current_user["id"]
    
    try:
        from services.agents.belief_store import get_belief_store
        belief_store = get_belief_store()
        
        success = await belief_store.clear_user_beliefs(user_id)
        
        if success:
            return {"success": True, "message": "All beliefs cleared. Novelty filtering reset."}
        else:
            return {"success": False, "message": "Failed to clear beliefs"}
            
    except Exception as e:
        logger.error(f"Failed to clear beliefs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear beliefs: {str(e)}"
        )
