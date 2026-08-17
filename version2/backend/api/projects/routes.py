"""
Project Workspace API Routes
==============================
The analysis container (one problem / one journey). Tenants scope via
``get_current_workspace``; every collection is tenant-scoped.

Routes:
    POST   /api/projects                      Create project
    GET    /api/projects                      List user's projects
    GET    /api/projects/{id}                 Project detail
    PUT    /api/projects/{id}                 Update project
    DELETE /api/projects/{id}                 Delete project (+ cascade sources/cells)

    POST   /api/projects/{id}/sources         Bind a source (reference, never re-create)
    GET    /api/projects/{id}/sources         List bound sources with sync state
    POST   /api/projects/{id}/sources/{sid}/sync   Trigger sync via existing machinery

    POST   /api/projects/{id}/cells           Add a cell
    GET    /api/projects/{id}/cells           List cells (journey)
    PUT    /api/projects/{id}/cells/{cid}     Update cell (incl. corrections)

    POST   /api/projects/{id}/journey/next-question   Next pivotal question
    POST   /api/projects/{id}/context/rules   Add a manual business rule (→ belief store)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from db.schemas_projects import (
    NextQuestion,
    NextQuestionRequest,
    NextQuestionResponse,
    Project,
    ProjectCell,
    ProjectCellCreate,
    ProjectCellUpdate,
    ProjectCreate,
    ProjectSource,
    ProjectSourceCreate,
    ProjectSummary,
    ProjectUpdate,
)
from middleware.workspace import get_current_workspace
from services.auth_service import get_current_user
from services.projects import project_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _raise_400(e: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─── Project CRUD ─────────────────────────────────────────────────────────────


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    current_user: dict = Depends(get_current_user),
    workspace: dict = Depends(get_current_workspace),
):
    """Create a project in the caller's workspace."""
    return await project_service.create_project(
        workspace_id=workspace["workspace_id"],
        owner_id=current_user["id"],
        payload=payload,
    )


@router.get("", response_model=list[ProjectSummary])
async def list_projects(
    current_user: dict = Depends(get_current_user),
    workspace: dict = Depends(get_current_workspace),
):
    """List the caller's projects in the current workspace."""
    return await project_service.list_projects(
        workspace_id=workspace["workspace_id"],
        owner_id=current_user["id"],
    )


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    workspace: dict = Depends(get_current_workspace),
):
    """Get project detail. Tenant-scoped."""
    project = await project_service.get_project(workspace["workspace_id"], project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    workspace: dict = Depends(get_current_workspace),
):
    """Update project name / problem statement / status."""
    project = await project_service.update_project(
        workspace["workspace_id"], project_id, payload
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    workspace: dict = Depends(get_current_workspace),
):
    """Delete a project and its sources + cells."""
    deleted = await project_service.delete_project(workspace["workspace_id"], project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return None


# ─── Sources (context binder) ─────────────────────────────────────────────────


@router.post(
    "/{project_id}/sources",
    response_model=ProjectSource,
    status_code=status.HTTP_201_CREATED,
)
async def bind_source(
    project_id: str,
    payload: ProjectSourceCreate,
    current_user: dict = Depends(get_current_user),
    workspace: dict = Depends(get_current_workspace),
):
    """
    Bind a source to a project.

    The ref must point at EXISTING infrastructure (a saved connection or an
    upload in this workspace) — never re-created here.
    """
    try:
        return await project_service.bind_source(
            workspace_id=workspace["workspace_id"],
            project_id=project_id,
            user_id=current_user["id"],
            payload=payload,
        )
    except ValueError as e:
        raise _raise_400(e)


@router.get("/{project_id}/sources", response_model=list[ProjectSource])
async def list_sources(
    project_id: str,
    workspace: dict = Depends(get_current_workspace),
):
    """List bound sources with their sync state (freshness UI)."""
    return await project_service.list_sources(workspace["workspace_id"], project_id)


@router.post("/{project_id}/sources/{source_id}/sync", response_model=ProjectSource)
async def sync_source(
    project_id: str,
    source_id: str,
    current_user: dict = Depends(get_current_user),
    workspace: dict = Depends(get_current_workspace),
):
    """
    Trigger a sync via the existing incremental machinery.

    One failing source degrades gracefully — the project keeps working and
    the source's sync state records the error.
    """
    try:
        return await project_service.sync_source(
            workspace_id=workspace["workspace_id"],
            project_id=project_id,
            source_id=source_id,
            user_id=current_user["id"],
        )
    except ValueError as e:
        raise _raise_400(e)


# ─── Cells (journey) ──────────────────────────────────────────────────────────


@router.post(
    "/{project_id}/cells",
    response_model=ProjectCell,
    status_code=status.HTTP_201_CREATED,
)
async def add_cell(
    project_id: str,
    payload: ProjectCellCreate,
    workspace: dict = Depends(get_current_workspace),
):
    """Add a cell (problem / question / answer / note / chart / table)."""
    try:
        return await project_service.add_cell(
            workspace_id=workspace["workspace_id"],
            project_id=project_id,
            payload=payload,
        )
    except ValueError as e:
        raise _raise_400(e)


@router.get("/{project_id}/cells", response_model=list[ProjectCell])
async def list_cells(
    project_id: str,
    workspace: dict = Depends(get_current_workspace),
):
    """List cells in journey order (the analysis notebook)."""
    return await project_service.list_cells(workspace["workspace_id"], project_id)


@router.put("/{project_id}/cells/{cell_id}", response_model=ProjectCell)
async def update_cell(
    project_id: str,
    cell_id: str,
    payload: ProjectCellUpdate,
    workspace: dict = Depends(get_current_workspace),
):
    """Update a cell — including corrections (→ belief store wiring is in chat)."""
    cell = await project_service.update_cell(
        workspace_id=workspace["workspace_id"],
        project_id=project_id,
        cell_id=cell_id,
        payload=payload,
    )
    if not cell:
        raise HTTPException(status_code=404, detail="Cell not found")
    return cell


# ─── Journey ──────────────────────────────────────────────────────────────────


@router.post("/{project_id}/journey/next-question", response_model=NextQuestionResponse)
async def journey_next_question(
    project_id: str,
    payload: NextQuestionRequest | None = None,
    current_user: dict = Depends(get_current_user),
    workspace: dict = Depends(get_current_workspace),
):
    """
    Surface the next pivotal question in the journey.

    MECE-decomposes the problem, grounds the next question in findings
    already in the project + the user's beliefs (corrections / business
    rules). Pure backend — the frontend journey panel is a thin consumer.
    """
    try:
        result = await project_service.journey_next_question(
            workspace_id=workspace["workspace_id"],
            project_id=project_id,
            user_id=current_user["id"],
            problem_statement=payload.problem_statement if payload else None,
        )
    except ValueError as e:
        raise _raise_400(e)

    return NextQuestionResponse(
        next_question=NextQuestion(**result["next_question"]),
        decomposition=result["decomposition"],
        answered_count=result["answered_count"],
    )


@router.post("/{project_id}/context/rules", status_code=status.HTTP_201_CREATED)
async def add_context_rule(
    project_id: str,
    payload: dict,
    current_user: dict = Depends(get_current_user),
    workspace: dict = Depends(get_current_workspace),
):
    """
    Add a manual business rule to the project.

    Example: {"rule_text": "Churn = cancelled + failed renewal, not free trials"}
    The rule is ingested into the belief store (source='manual_rule') and
    bound to the project as a context source.
    """
    rule_text = (payload or {}).get("rule_text")
    if not rule_text or not str(rule_text).strip():
        raise HTTPException(status_code=400, detail="rule_text is required")
    try:
        belief_id = await project_service.add_context_rule(
            workspace_id=workspace["workspace_id"],
            project_id=project_id,
            user_id=current_user["id"],
            rule_text=str(rule_text),
        )
    except ValueError as e:
        raise _raise_400(e)
    return {"belief_id": belief_id, "status": "ok"}
