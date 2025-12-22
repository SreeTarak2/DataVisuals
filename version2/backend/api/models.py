"""
API endpoints for managing and testing OpenRouter models.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import logging

from services.llm_router import llm_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/list")
async def list_models():
    """
    List all available OpenRouter models with their configurations.
    
    Returns:
        Dict with model information, strengths, and role mappings
    """
    try:
        models_info = llm_router.list_available_models()
        return {
            "success": True,
            "data": models_info
        }
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/{model_key}")
async def test_model(model_key: str, test_prompt: Optional[str] = None):
    """
    Test a specific OpenRouter model.
    
    Args:
        model_key: Model identifier (e.g., 'hermes_405b', 'qwen_235b')
        test_prompt: Optional custom test prompt
        
    Returns:
        Test results including success status, response, and timing
    """
    try:
        prompt = test_prompt or "Hello! Please respond with a brief greeting to confirm you're working."
        result = await llm_router.test_model(model_key, prompt)
        
        return {
            "success": result.get("success", False),
            "data": result
        }
    except Exception as e:
        logger.error(f"Failed to test model {model_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-all")
async def test_all_models():
    """
    Test all configured OpenRouter models.
    
    Returns:
        Comprehensive test results for all models
    """
    try:
        results = await llm_router.test_all_models()
        return {
            "success": True,
            "data": results
        }
    except Exception as e:
        logger.error(f"Failed to test all models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def models_health():
    """
    Quick health check for model infrastructure.
    
    Returns:
        Health status and configuration info
    """
    return {
        "success": True,
        "openrouter_configured": bool(llm_router.use_openrouter),
        "total_models": len(llm_router.openrouter_models),
        "available_roles": list(llm_router.role_mapping.keys())
    }
