"""
Project Workspace Schemas
==========================
A project is the analysis container (one problem / one journey). Datasets,
connections, and context materials are bound into it as sources.

Tenant model:
- ``workspace_id`` — the team/tenant boundary (same as every tenant-scoped doc).
- ``owner_id`` — the user who created the project.

See docs/NOTEBOOK_WORKSPACE.md for the full design.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class _Config:
    from_attributes = True
    extra = "forbid"
    use_enum_values = True


# ---------------------------------------------------------------------------
# PROJECT
# ---------------------------------------------------------------------------


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    problem_statement: Optional[str] = Field(None, max_length=8000)

    class Config(_Config):
        pass


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    problem_statement: Optional[str] = Field(None, max_length=8000)
    status: Optional[Literal["draft", "active", "archived"]] = None

    class Config(_Config):
        pass


class Project(ProjectBase):
    id: str
    workspace_id: str
    owner_id: str
    status: str = "draft"
    source_count: int = 0
    cell_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config(_Config):
        pass


class ProjectSummary(BaseModel):
    """Lightweight project representation for list views."""

    id: str
    name: str
    problem_statement: Optional[str] = None
    status: str = "draft"
    source_count: int = 0
    cell_count: int = 0
    updated_at: datetime

    class Config(_Config):
        pass


# ---------------------------------------------------------------------------
# PROJECT SOURCES (the context binder)
# ---------------------------------------------------------------------------


class SourceRef(BaseModel):
    """
    A reference to EXISTING infrastructure — never a re-creation.

    - database / dlt: ``conn_id`` points at a row in ``db_connections``.
    - file / google_sheets: ``dataset_id`` points at an upload doc.
    - document: ``document_text`` is the context material itself
      (ingested into the belief store; not stored as a blob).
    """

    connection_type: Literal["database", "dlt", "google_sheets", "file", "document"]
    conn_id: Optional[str] = None
    table: Optional[str] = None
    source_type: Optional[str] = None  # for dlt: "slack", "salesforce", ...
    dataset_id: Optional[str] = None
    document_text: Optional[str] = None

    class Config(_Config):
        pass


class ProjectSourceCreate(BaseModel):
    kind: Literal["data", "context"] = "data"
    ref: SourceRef

    class Config(_Config):
        pass


class ProjectSource(ProjectSourceCreate):
    id: str
    project_id: str
    workspace_id: str
    sync: Dict[str, Any] = Field(
        default_factory=lambda: {
            "status": "idle",
            "last_sync_at": None,
            "watermark": None,
            "next_sync": "on_demand",
            "error": None,
        }
    )
    created_at: datetime

    class Config(_Config):
        pass


# ---------------------------------------------------------------------------
# PROJECT CELLS (the journey)
# ---------------------------------------------------------------------------


class Provenance(BaseModel):
    """The trust layer: every answer cites what produced it."""

    sql: Optional[str] = None
    metric_definition_id: Optional[str] = None
    row_count: Optional[int] = None
    date_range: Optional[List[str]] = None
    dataset_ids: Optional[List[str]] = None

    class Config(_Config):
        pass


class ProjectCellCreate(BaseModel):
    kind: Literal["problem", "question", "answer", "note", "chart", "table"] = "question"
    question: Optional[str] = Field(None, max_length=8000)
    answer_md: Optional[str] = None
    provenance: Provenance = Field(default_factory=Provenance)
    status: Literal["pending", "answered", "blocked"] = "pending"

    class Config(_Config):
        pass


class ProjectCell(ProjectCellCreate):
    id: str
    project_id: str
    workspace_id: str
    order: int = 0
    created_at: datetime
    updated_at: datetime

    class Config(_Config):
        pass


class ProjectCellUpdate(BaseModel):
    question: Optional[str] = Field(None, max_length=8000)
    answer_md: Optional[str] = None
    provenance: Optional[Provenance] = None
    status: Optional[Literal["pending", "answered", "blocked"]] = None

    class Config(_Config):
        pass


# ---------------------------------------------------------------------------
# JOURNEY (next pivotal question)
# ---------------------------------------------------------------------------


class NextQuestionRequest(BaseModel):
    """Optional grounding: findings already in the project are used automatically."""

    problem_statement: Optional[str] = Field(None, max_length=8000)

    class Config(_Config):
        pass


class NextQuestion(BaseModel):
    question: str
    rationale: str = ""
    component: str = ""
    priority: Literal["high", "medium", "low"] = "high"
    confidence: float = 0.5

    class Config(_Config):
        pass


class NextQuestionResponse(BaseModel):
    next_question: NextQuestion
    decomposition: List[Dict[str, Any]] = Field(default_factory=list)
    answered_count: int = 0

    class Config(_Config):
        pass


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

__all__ = [
    "ProjectBase",
    "ProjectCreate",
    "ProjectUpdate",
    "Project",
    "ProjectSummary",
    "SourceRef",
    "ProjectSourceCreate",
    "ProjectSource",
    "Provenance",
    "ProjectCellCreate",
    "ProjectCell",
    "ProjectCellUpdate",
    "NextQuestionRequest",
    "NextQuestion",
    "NextQuestionResponse",
]
