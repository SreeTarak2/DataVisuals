# Signal Tenant Architecture Design

## Guiding Principle

Signal's moat is not dashboards or charts. Signal's moat is **accumulated business understanding** — the knowledge the system learns about a workspace over time through entity extraction, corrections, metric definitions, and investigation outcomes.

Every architectural decision should ask: "Does this make Signal understand the business better?"

## Current State

```
User ──→ Datasets ──→ {Charts, KPIs, Insights, Dashboards, Conversations}
```

Everything is scoped to `user_id` + `dataset_id`. No organization or workspace entity exists.

**Existing workspace-scoped infrastructure** (already built but unused):
- `schemas_context.py`: `CorrectionRule.workspace_id`, `MetricMapping.workspace_id`, `UserMemory.workspace_id`, `UserQuery.workspace_id`
- `context_store.py`: MongoDB collections with `workspace_id` indexes
- `services/feedback/`: Event logger, signal classifier, correction rewriter — all take `workspace_id`
- Fallback in `ai_service.py`: `workspace_id = user_id`

**Existing understanding engine** (already built, runs during dataset processing, buried in metadata):
- `entity_discovery.discover()` — extracts business entities from columns with confidence scores
- `primary_object_discovery.discover()` — identifies what each dataset is "about"
- `participation_discovery.discover()` — finds FK-style relationships between entities
- `signal_engine.classify_column()` — classifies every column into structural roles (IDENTIFIER, AMOUNT, DATE, etc.)
- `belief_store` with passive ingestion — accumulates knowledge from every AI interaction
- `correction_memory.json` — tracks every user correction over time
- `entity_extraction_audit.jsonl` — logs all extraction results

All of this runs during dataset processing and is stored in `dataset.metadata.unified_profile` + `dataset.metadata.entity_discovery`. But it's only accessible through the `/api/datasets/{id}/understanding` endpoint.

**The migration is not "build a new engine." It's "promote what exists to the workspace level."**

## Target State

```
Workspace (the container — tenant boundary)
  ├── Understanding (aggregated business knowledge across ALL datasets)
  │     ├── Entities discovered with confidence
  │     ├── Primary objects per dataset
  │     ├── Relationships between entities
  │     ├── Corrections made over time
  │     └── Knowledge objects (definitions, mappings, beliefs)
  ├── Data Sources (datasets, database connections)
  ├── Metrics (computed from understanding + data sources)
  ├── Investigations (structured questioning on top of metrics)
  └── Dashboards (presentation layer — built last)
```

**Key insight:** The understanding layer is what makes Signal different from every other analytics tool. Dashboards and metrics are table stakes. Understanding entities, relationships, and business knowledge across datasets is the differentiator.

## How the Layers Relate

```
Data Sources
     ↓
Understanding Engine (runs during processing — already exists)
  - Entity discovery
  - Primary object detection
  - Column classification
  - Relationship detection
     ↓
Knowledge Objects (user-confirmed knowledge)
  - Metric definitions
  - Term corrections
  - Entity reclassifications
  - Business rules
     ↓
Metrics (computed values with lineage back to understanding)
     ↓
Investigations (structured questioning when metrics change unexpectedly)
     ↓
Dashboards (presentation — last priority)
```

The understanding engine already runs for free during dataset processing. The architecture work is surfacing it at the workspace level, not building it from scratch.

## Phase 1: Make Workspace Real (Week 1)

### 1.1 New MongoDB Collections

```python
# db/schemas_workspace.py

class Workspace(BaseModel):
    id: str
    name: str
    owner_id: str                    # User who created it
    settings: WorkspaceSettings      # Default date range, preferred domain, etc.
    created_at: datetime
    updated_at: datetime

class WorkspaceMember(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    role: Literal["admin", "member", "viewer"]
    added_by: str
    joined_at: datetime

class WorkspaceSettings(BaseModel):
    default_date_range: str = "last_30_days"
    preferred_domain: Optional[str] = None
    timezone: str = "UTC"
    currency: str = "USD"
```

### 1.2 New API Routes

```
POST   /api/workspaces                          # Create workspace
GET    /api/workspaces                          # List user's workspaces
GET    /api/workspaces/{id}                     # Get workspace details
PUT    /api/workspaces/{id}                     # Update workspace settings
DELETE /api/workspaces/{id}                     # Delete workspace

POST   /api/workspaces/{id}/members             # Invite member
GET    /api/workspaces/{id}/members             # List members
DELETE /api/workspaces/{id}/members/{userId}    # Remove member
```

### 1.3 Migration: Add `workspace_id` to Existing Collections

Every existing MongoDB collection gets a `workspace_id` field:

```python
# Migration script
db.uploads.update_many({}, {"$set": {"workspace_id": None}})
db.charts.update_many({}, {"$set": {"workspace_id": None}})
db.insights.update_many({}, {"$set": {"workspace_id": None}})
db.conversations.update_many({}, {"$set": {"workspace_id": None}})
db.dashboards.update_many({}, {"$set": {"workspace_id": None}})
db.kpi_configs.update_many({}, {"$set": {"workspace_id": None}})
db.dataset_analytics.update_many({}, {"$set": {"workspace_id": None}})
db.reports.update_many({}, {"$set": {"workspace_id": None}})
```

On user registration, auto-create a personal workspace named after the user.
Backfill: create personal workspaces for all existing users.

### 1.4 Auth: JWT Includes `workspace_id`

```python
# In auth_service.create_access_token()
def create_access_token(self, data: dict, ...):
    to_encode = data.copy()
    to_encode.update({
        "sub": user_id,
        "email": email,
        "workspace_id": workspace_id,  # NEW: current workspace context
    })
```

The frontend passes `X-Workspace-Id` header on every request, or the backend resolves it from the JWT.

### 1.5 Middleware: Resolve Current Workspace

```python
# middleware/workspace.py
async def get_current_workspace(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict:
    # 1. Check X-Workspace-Id header
    workspace_id = request.headers.get("X-Workspace-Id")
    
    # 2. Fall back to JWT claim
    if not workspace_id:
        workspace_id = current_user.get("workspace_id")
    
    # 3. Default to user's personal workspace
    if not workspace_id:
        workspace = await workspace_service.get_personal_workspace(current_user["id"])
        workspace_id = workspace["id"]
    
    # 4. Verify membership
    member = await workspace_service.get_member(workspace_id, current_user["id"])
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    
    return {"workspace_id": workspace_id, "role": member["role"]}
```

---

## Phase 2: Workspace Understanding Layer (Week 2)

### 2.1 New MongoDB Collection

```python
class KnowledgeObject(BaseModel):
    """
    A single piece of understanding about the workspace.
    Everything becomes knowledge: entity labels, metric definitions,
    term corrections, business rules, column classifications, beliefs.
    """
    id: str
    workspace_id: str
    type: Literal[
        "entity_label",           # "this column represents a customer"
        "metric_definition",      # "MRR = sum of subscription revenue"
        "term_correction",        # "revenue means recognized revenue, not booked"
        "column_classification",  # "customer_id is IDENTIFIER, not CATEGORY"
        "business_rule",          # "exclude test accounts from revenue"
        "relationship",           # "orders.customer_id → customers.id"
        "primary_object",         # "the orders table is about orders"
        "belief",                 # "Q4 revenue is typically 30% higher"
    ]
    title: str                                    # Human-readable title
    content: str                                  # The knowledge itself
    confidence: float = 1.0                      # How confident Signal is
    source: str                                   # "auto_discovered" | "user_defined" | "correction" | "ingested"
    
    # Optional relations
    source_datasets: List[str] = []              # Which datasets contributed
    related_objects: List[str] = []              # Other knowledge object IDs
    metadata: Dict[str, Any] = {}                # Flexible metadata per type
    
    # Lineage
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    correction_history: List[Dict] = []          # Track changes over time
```

### 2.2 What Gets Promoted From the Existing Engine

The understanding pipeline already runs during dataset processing. The following data already exists but is trapped in `dataset.metadata`:

| Existing computed data | New KnowledgeObject type | Where it lives today |
|---|---|---|
| `entity_discovery.entities` with labels + confidence | `entity_label` | `dataset.metadata.unified_profile` |
| `primary_object_discovery` result | `primary_object` | `/api/datasets/{id}/understanding` |
| `participation_discovery` entities | `relationship` | `/api/datasets/{id}/understanding` |
| `signal_engine.classify_column()` results | `column_classification` | `dataset.metadata.unified_profile.columns[].intelligence` |
| `correction_memory.json` entries | `term_correction` | File path in `kg_config.CORRECTION_MEMORY_PATH` |
| `MetricMapping` from context_store | `metric_definition` | MongoDB `metric_mappings` collection |
| `CorrectionRule` from context_store | `term_correction` | MongoDB `correction_rules` collection |
| `belief_store` promoted beliefs | `belief` | ChromaDB `beliefs_{user_id}` collection |

### 2.3 Migration: Aggregate Understanding at Workspace Level

Instead of building a new engine, aggregate what already exists:

```python
async def sync_workspace_understanding(workspace_id: str):
    """Sync all dataset-level understanding to workspace level."""
    db = get_database()
    
    # 1. Get all datasets in this workspace
    datasets = await db.uploads.find({"workspace_id": workspace_id}).to_list(None)
    
    # 2. For each dataset, extract understanding and create KnowledgeObjects
    for dataset in datasets:
        meta = dataset.get("metadata", {})
        
        # Primary object → knowledge_object (type: "primary_object")
        entity_discovery = meta.get("entity_discovery", {})
        if entity_discovery.get("primary_object"):
            po = entity_discovery["primary_object"]
            await upsert_knowledge_object(
                workspace_id=workspace_id,
                type="primary_object",
                title=f"{dataset['name']} is about {po['label']}",
                content=json.dumps(po),
                source="auto_discovered",
                source_datasets=[dataset["_id"]],
                confidence=po.get("evidence_strength", 0.5),
            )
        
        # Entities → knowledge_objects (type: "entity_label")
        for entity in entity_discovery.get("entities", []):
            await upsert_knowledge_object(...)
        
        # Column classifications → knowledge_objects (type: "column_classification")
        unified_profile = meta.get("unified_profile", {})
        for col in unified_profile.get("columns", []):
            intelligence = col.get("intelligence", {})
            if intelligence.get("column_role"):
                await upsert_knowledge_object(...)
```

### 2.4 New API Routes

```
GET    /api/workspaces/{id}/understanding               # Dashboard: what Signal knows
GET    /api/workspaces/{id}/understanding/summary        # Counts by type, confidence distribution
GET    /api/workspaces/{id}/understanding/by-type/{type} # Filter by knowledge type
GET    /api/workspaces/{id}/understanding/{objId}        # Single knowledge object with history
POST   /api/workspaces/{id}/understanding                # User creates a knowledge object
PUT    /api/workspaces/{id}/understanding/{objId}        # User corrects a knowledge object
DELETE /api/workspaces/{id}/understanding/{objId}        # Remove incorrect knowledge

GET    /api/workspaces/{id}/understanding/corrections    # All corrections made in workspace
GET    /api/workspaces/{id}/understanding/needs-review   # Low-confidence items (threshold < 0.7)
```

### 2.5 Why This Phase Exists Before Metrics

Metrics depend on understanding. A metric like "Revenue" needs:
- Which columns represent revenue amounts? ← column_classification tells us
- Which datasets contain revenue data? ← entity_discovery tells us
- How has revenue been corrected before? ← correction history tells us

Without the understanding layer, metrics have no context. With it, metrics emerge naturally from what Signal already knows about the workspace.

---

## Phase 3: Metrics as First-Class Entities (Week 3)

### 3.1 New MongoDB Collection

```python
class Metric(BaseModel):
    id: str
    workspace_id: str
    name: str                                 # "Monthly Recurring Revenue"
    definition: str                           # "Sum of all active subscription revenue"
    formula: Optional[Dict]                   # Expression or SQL
    owner: str                                # Person/team name
    category: str                             # "saas", "ecommerce", "finance", "custom"
    trend_direction: Literal["up_is_good", "down_is_good", "stable_is_good"]
    
    # Knowledge (references understanding layer)
    knowledge_object_id: Optional[str]        # Links to KnowledgeObject
    known_exceptions: List[str]               # "Excludes one-time fees"
    tags: List[str]
    
    # Data lineage
    source_datasets: List[SourceMapping]      # Which datasets feed this metric
    
    # Quality
    confidence: float = 1.0                   # How well the AI understands this metric
    correction_count: int = 0
    
    # Metadata
    created_by: str
    created_at: datetime
    updated_at: datetime

class SourceMapping(BaseModel):
    dataset_id: str
    column: str
    aggregation: str                          # "sum", "mean", "count", etc.
    weight: float = 1.0                       # For composite metrics across datasets

class MetricCorrection(BaseModel):
    id: str
    metric_id: str
    workspace_id: str
    user_id: str
    original_interpretation: str
    corrected_interpretation: str
    correction_type: Literal["value", "definition", "formula", "exception"]
    created_at: datetime
```

### 3.2 New API Routes

```
GET    /api/workspaces/{id}/metrics                 # List all metrics with current values
POST   /api/workspaces/{id}/metrics                 # Define new metric
GET    /api/workspaces/{id}/metrics/{metricId}      # Get metric detail + history
PUT    /api/workspaces/{id}/metrics/{metricId}      # Update metric definition
DELETE /api/workspaces/{id}/metrics/{metricId}      # Archive metric
GET    /api/workspaces/{id}/metrics/{metricId}/value # Compute current value across datasets

GET    /api/workspaces/{id}/metrics/changed         # Metrics that changed since last visit (for homepage)
GET    /api/workspaces/{id}/metrics/conflicts       # Definitions that conflict across datasets
```

### 3.3 Routing Change

The current `/api/datasets/{dataset_id}/kpis` endpoint computes KPIs *from a dataset*.
The new `/api/workspaces/{id}/metrics/{metricId}/value` computes a metric *across all its source datasets*.

Both coexist. The old endpoint powers single-dataset dashboards. The new endpoint powers the organization-wide homepage.

### 3.4 Existing Infrastructure to Repurpose

| Current | New | What to migrate |
|---------|-----|-----------------|
| `KPIDefinition` in `schemas_kpi.py` | `Metric` | Formula, thresholds, trend direction, category |
| `SaaSMetrics`, `EcommerceMetrics` | Templates | Built-in metric templates become seed data |
| `intelligent_kpi_generator` | `metric_value_computer` | Reuse the per-column computation logic |
| `MetricMapping` in `schemas_context.py` | KnowledgeObject (metric_definition) | Migrate existing term→definition mappings |
| `correction_memory.json` | `MetricCorrection` | Migrate correction history per metric |
| `belief_store` | `Metric.known_exceptions` | Beliefs about metrics become metric metadata |

---

## Phase 4: Investigations (Week 4)

### 4.1 New MongoDB Collection

```python
class Investigation(BaseModel):
    id: str
    workspace_id: str
    title: str                                # "Revenue mismatch between Finance and Sales"
    status: Literal["open", "evidence_collecting", "resolved", "closed"]
    
    # Context
    hypothesis: str
    related_metrics: List[str]                # Metric IDs being investigated
    related_datasets: List[str]
    
    # Evidence
    evidence: List[EvidenceItem]
    possible_causes: List[str]
    resolution: Optional[str]
    
    # Audit
    created_by: str
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]

class EvidenceItem(BaseModel):
    id: str
    type: Literal["chart", "insight", "query_result", "note", "correction"]
    title: str
    description: str
    data: Optional[Dict]                      # Snapshot of the evidence
    added_by: str
    added_at: datetime
```

### 4.2 New API Routes

```
POST   /api/workspaces/{id}/investigations               # Create investigation
GET    /api/workspaces/{id}/investigations                # List active investigations
GET    /api/workspaces/{id}/investigations/{invId}        # Get investigation detail
PUT    /api/workspaces/{id}/investigations/{invId}        # Update status, hypothesis, etc.

POST   /api/workspaces/{id}/investigations/{invId}/evidence  # Add evidence
POST   /api/workspaces/{id}/investigations/{invId}/resolve   # Mark resolved
POST   /api/workspaces/{id}/investigations/{invId}/from-chat # Create from chat message
```

### 4.3 Existing Infrastructure to Repurpose

| Current | New | What to migrate |
|---------|-----|-----------------|
| `quis_graph.py` | `Investigation` state machine | State transitions, hypothesis tracking |
| `anomaly_investigator` | `Investigation.evidence` | Automated evidence collection |
| `ChatPanel` (frontend) | `POST /from-chat` | "Investigate" button on chat messages |
| `anomaly` insight type | `EvidenceItem` | Detected anomalies as evidence |
| `PowerBIInsightCards` | Evidence gallery | Visual evidence display |

---

## Phase 5: API Restructuring (Ongoing)

The route prefix hierarchy should reflect the new architecture:

```python
# Current (dataset-centric):
/api/auth/...
/api/datasets/{id}/...
/api/chat/...
/api/dashboard/{id}/...
/api/charts/...
/api/insights/{id}/...

# Future (workspace-centric):
/api/workspaces/{wid}/members/...
/api/workspaces/{wid}/metrics/...
/api/workspaces/{wid}/knowledge/...
/api/workspaces/{wid}/investigations/...
/api/workspaces/{wid}/datasets/...           # Old dataset routes, scoped to workspace
/api/workspaces/{wid}/dashboards/...
/api/workspaces/{wid}/charts/...
/api/workspaces/{wid}/insights/...
```

**Migration strategy:** Don't delete old routes immediately. Add the new workspace-scoped routes alongside them. Have the frontend switch to the new routes page by page. The old routes continue working for backward compatibility.

---

## Data Flow Summary

```
User logs in
  ↓
JWT contains {user_id, email, workspace_id}
  ↓
All API calls go through /api/workspaces/{wid}/...
  ↓
Workspace middleware validates membership
  ↓
Scoped data access: all queries include workspace_id filter
```

```
Homepage loads:
  GET /api/workspaces/{wid}/metrics/changed
  → Returns: [{name, value, delta, trend, owner, confidence}, ...]
  → Computed across ALL source datasets scoped to workspace
```

```
User asks about a metric:
  POST /api/workspaces/{wid}/chat  (with metric context)
  → Uses Metric.definition, Metric.known_exceptions, MetricCorrection history
  → Uses old chat pipeline but with workspace-level context
```

```
User spots an issue:
  POST /api/workspaces/{wid}/investigations
  → Creates investigation with title, hypothesis, related metrics
  → Old "Ask AI" becomes "Investigate" with structured output
```

---

## Implementation Order

| Phase | What | Dependencies | Estimated Effort |
|-------|------|-------------|------------------|
| 1 | Workspace collection + auth middleware | None | 2-3 days |
| 1 | Migration: add workspace_id to all collections | Phase 1a | 1 day |
| 2 | Metrics collection + routes | Phase 1 | 3-4 days |
| 2 | Migrate existing KPIs/definitions to metrics | Phase 2a | 2 days |
| 3 | Knowledge Center API | Phase 2 | 2 days |
| 3 | Consolidate scattered knowledge | Phase 3a | 1 day |
| 4 | Investigations collection + routes | Phase 2 | 3-4 days |
| 4 | Connect inquis_graph + anomaly_investigator | Phase 4a | 2 days |
| 5 | Route restructuring (workspace-first) | Phase 1-4 | Ongoing |

**Total backend effort:** ~16-20 days for a single developer.

**Can be parallelized with:** Frontend redesign (page by page, using new API routes as they ship).

---

## What This Doesn't Do

- **Billing**: No Stripe, no plans, no payment processing. Workspace is the Tenant boundary.
- **Organizations**: No org hierarchy above workspace. Not needed for MVP.
- **Role management**: Only `owner` and `member` roles. No `viewer` or fine-grained permissions.
- **Cross-workspace sharing**: Each workspace is fully isolated.
- **SSO/SAML**: Auth remains email/password + Google OAuth.
- **Dashboards first**: Dashboard features are the LAST priority. Understanding, metrics, and investigations come first.

All of these can be added later. Workspace-level isolation is the foundation.

## Scoring This Architecture Against Signal's Moat

| Area | Score | Notes |
|------|-------|-------|
| Understanding as differentiator | 9/10 | Existing engine promoted, not rebuilt |
| SaaS readiness | 9/10 | Workspace is tenant boundary |
| Multi-tenant design | 9/10 | workspace_id on every collection |
| AI Analyst vision | 8/10 | Investigations + Understanding = structured analyst |
| Scalability | 8/10 | Understanding engine runs during processing, not on read |
| Business understanding layer | 8/10 | KnowledgeObject promotes existing data |
| Dashboards | 4/10 | Deliberately deprioritized — dashboards last |

**The strongest asset Signal will have by 2030 is not dashboards or metrics. It's the accumulated business understanding that Signal learns about a workspace over time.** This architecture makes that asset first-class from day one of the migration.
