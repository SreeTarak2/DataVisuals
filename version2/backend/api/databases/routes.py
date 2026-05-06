import logging
from fastapi import APIRouter, Depends, HTTPException, Request

from api.databases.schemas import (
    TestConnectionRequest,
    TestConnectionResponse,
    SaveConnectionRequest,
    ConnectionResponse,
    ExtractTableRequest,
    ExtractTableResponse,
)
from services.auth_service import get_current_user
from services.databases.db_connection_service import db_connection_service
from core.rate_limiter import limiter, RateLimits

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Test a connection — no save, just validates credentials
# ---------------------------------------------------------------------------

@router.post("/test", response_model=TestConnectionResponse)
@limiter.limit(RateLimits.DB_TEST)
async def test_database_connection(
    request: Request,
    body: TestConnectionRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Test a database connection without saving it.
    Returns connection status, response time, and table count on success.
    """
    config = body.dict()
    result = await db_connection_service.test_connection(config)
    return result


# ---------------------------------------------------------------------------
# Save a connection (test-first, then persist)
# ---------------------------------------------------------------------------

@router.post("/", response_model=ConnectionResponse, status_code=201)
@limiter.limit(RateLimits.DB_CONNECT)
async def save_database_connection(
    request: Request,
    body: SaveConnectionRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Save a database connection after verifying credentials.
    Passwords are AES-encrypted before storage — never stored in plaintext.
    """
    try:
        config = body.dict()
        name = config.pop("name")
        result = await db_connection_service.save_connection(
            user_id=current_user["id"],
            name=name,
            config=config,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save connection for user {current_user['id']}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save connection")


# ---------------------------------------------------------------------------
# List saved connections
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[ConnectionResponse])
@limiter.limit(RateLimits.DB_LIST)
async def list_database_connections(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """List all database connections saved by the current user."""
    return await db_connection_service.list_connections(current_user["id"])


# ---------------------------------------------------------------------------
# List tables inside a saved connection
# ---------------------------------------------------------------------------

@router.get("/{conn_id}/tables")
@limiter.limit(RateLimits.DB_LIST)
async def list_tables(
    request: Request,
    conn_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Connect to the saved database and return a list of available tables/collections.
    Results are cached for 5 minutes by SchemaDiscoveryService.
    """
    try:
        tables = await db_connection_service.get_tables(current_user["id"], conn_id)
        return {"connection_id": conn_id, "tables": tables, "count": len(tables)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# Extract a table → create a DataSage dataset → fire Celery pipeline
# ---------------------------------------------------------------------------

@router.post("/{conn_id}/extract", response_model=ExtractTableResponse, status_code=202)
@limiter.limit(RateLimits.DB_EXTRACT)
async def extract_table(
    request: Request,
    conn_id: str,
    body: ExtractTableRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Extract data from a table (or custom SQL query) into a DataSage dataset.
    - Saves extracted rows as Parquet
    - Creates a dataset record in MongoDB
    - Fires the same Celery processing pipeline used for file uploads
      (EDA, KPI generation, chart recommendations, vector indexing)

    Returns dataset_id and task_id to track processing progress.
    """
    if not body.table_name and not body.custom_query:
        raise HTTPException(
            status_code=400, detail="Provide either table_name or custom_query"
        )

    try:
        result = await db_connection_service.extract_to_dataset(
            user_id=current_user["id"],
            conn_id=conn_id,
            table_name=body.table_name,
            custom_query=body.custom_query,
            dataset_name=body.dataset_name,
            row_limit=body.row_limit,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Extraction failed for conn {conn_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Extraction failed")


# ---------------------------------------------------------------------------
# Delete a saved connection
# ---------------------------------------------------------------------------

@router.delete("/{conn_id}", status_code=204)
@limiter.limit(RateLimits.DB_LIST)
async def delete_database_connection(
    request: Request,
    conn_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a saved database connection. Does not delete datasets created from it."""
    try:
        await db_connection_service.delete_connection(current_user["id"], conn_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
