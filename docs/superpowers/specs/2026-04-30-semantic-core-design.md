# Semantic Learning Core: Package Design
> **Type:** Shared Foundation Package
> **Goal:** One composable `services/semantic_core/` package that all 5 tasks extend
---

## Architecture Overview

```
services/semantic_core/            # Shared foundation (1 package, all tasks import from)
├── __init__.py                 # Single export: MetricCore
├── schemas.py                  # All Pydantic models
├── patterns.py                 # Regex + extraction utilities
├── context_mixin.py            # MongoDB context operations
├── verifier_base.py            # TrustVerifier base
└── extraction.py               # Semantic extraction from text

services/trust/
└── verifier.py                 # TrustVerifier (Task 3: extends verifier_base)
    corrections/
    └── semantic_capture.py    # SemanticCapture (Task 2: uses extraction.py)
    └── capture_routes.py      # Auto-capture API (Task 5: uses context_mixin)
```

**Core principle:** Each file in `semantic_core` is minimal and self-contained. Tasks extend, not modify.

---

## Module Breakdown

### `semantic_core/schemas.py`
```python
# MetricSemantic: stored definition of a metric
class MetricSemantic(BaseModel):
    metric_name: str            # e.g., "revenue"
    definition: str             # e.g., "recognized revenue"
    formula: Optional[str]      # e.g., "sum(amount) where status = 'active'"
    source_columns: List[str]   # e.g., ["amount", "status"]
    aggregation: Optional[str]  # e.g., "sum", "avg"
    business_context: Optional[str]

# ValidationRule: pre-execution check on a metric
class ValidationRule(BaseModel):
    rule_type: str             # e.g., "RANGE"
    expression: str             # e.g., "revenue >= 0"
    threshold: Optional[float]
    fail_message: str

# TrustVerificationResult: result of pre-query check
class TrustVerificationResult(BaseModel):
    is_trusted: bool
    confidence: float
    checks_passed: List[str]
    checks_failed: List[str]
    warnings: List[str]
    applied_semantics: List[MetricSemantic]

# Corrections extension: semantic fields added to CorrectionRule
class SemanticCorrection(BaseModel):
    """Fields added to CorrectionRule for semantic corrections."""
    metric_semantic: Optional[MetricSemantic] = None
    validation_rules: List[ValidationRule] = []
    is_explicit_semantic: bool = False  # True if user marked as semantic
```

### `semantic_core/patterns.py`
```python
# Pure regex + text patterns, no side effects
# All patterns compiled once at import

METRIC_DEFINITION_PATTERNS = [
    r"(\w+)\s+means?\s+(.+)",           # "revenue means recognized revenue"
    r"(\w+)\s+is\s+(.+)",                # "revenue is total recognized"
    r"(\w+)\s+refers?\s+to\s+(.+)",      # "revenue refers to recognized"
]

FORMULA_PATTERNS = [
    r"sum\(([\w_]+)\)",       # sum(amount)
    r"avg\(([\w_]+)\)",       # avg(quantity)
    r"count\(([\w_]+)\)",     # count(id)
    # ... more patterns
]

def extract_metric_term(text: str) -> Optional[Tuple[str, str]]: ...
"""Extract (metric_name, definition) from correction text."""

def infer_aggregation(definition: str) -> Optional[str]: ...
"""Infer aggregation type from definition text."""

def extract_columns_from_formula(formula: str) -> List[str]: ...
"""Extract column names from formula text."""
```

### `semantic_core/context_mixin.py`
```python
# MongoDB operations scoped to workspace/dataset
# No LLM calls, no side effects

class SemanticContextMixin:
    """Mixin providing shared context operations."""

    async def get_workspace_semantics(self, workspace_id: str) -> List[MetricSemantic]: ...
    async def get_workspace_validation_rules(self, workspace_id: str) -> List[ValidationRule]: ...
    async def upsert_semantic(self, semantic: MetricSemantic, workspace_id: str, user_id: str) -> MetricSemantic: ...
    async def get_semantic_for_metric(self, workspace_id: str, metric_name: str) -> Optional[MetricSemantic]: ...
    async def capture_from_correction(self, rule_id: str, query_context: Optional[str] = None) -> Optional[MetricSemantic]: ...
    async def increment_semantic_usage(self, workspace_id: str, metric_name: str) -> None: ...
```

### `semantic_core/verifier_base.py`
```python
# Abstract interface, not implementation
# Tasks implement TrustVerifier by extending this

class TrustVerifierBase(ABC):
    @abstractmethod
    async def verify_query(
        self, query: str, workspace_id: str, dataset_id: Optional[str]
    ) -> TrustVerificationResult: ...

    def compute_confidence(
        self, semantics: List[MetricSemantic], query: str
    ) -> Tuple[float, List[TrustViolation]]: ...
```

### `semantic_core/extraction.py`
```python
# Pure semantic extraction functions
# No DB calls, no external services

def extract_semantic_from_correction(
    original_term: str, corrected_term: str, query_context: Optional[str] = None
) -> Optional[Tuple[MetricSemantic, List[ValidationRule]]]: ...
"""Main extraction entry point. Returns (MetricSemantic, validation_rules) or None."""

def is_semantic_correction(original_term: str, corrected_term: str) -> bool: ...
"""Fast pattern check: does this look like a semantic correction?"""

def infer_validation_rules(
    metric_name: str, definition: str, formula: Optional[str]
) -> List[ValidationRule]: ...
"""Infer validation rules from definition context."""
```

---

## Data Flow

```
1. User correction: "revenue means recognized revenue"
            ↓
2. correction_rewriter.apply_corrections() [existing]
            ↓
3. SemanticCapture.is_semantic_correction() [from extraction.py] → True/False fast check
            ↓
4. (If True) semantic_rewrite() [from extraction.py]
            → MetricSemantic + ValidationRules
            ↓
5. context_upsert_semantic() [from context_mixin]
            → MongoDB correction_rules collection
            → { metric_semantic: {...}, validation_rules: [...] }
            ↓
6. On next query: TrustVerifier.verify_query() [extends verifier_base]
            → TrustVerificationResult
            → semantic context injected into prompt
            → Response includes trust_Verification metadata
```

---

## Test Strategy

| Test | File | What it covers |
|------|------|----------------|
| Unit: patterns | `tests/unit/test_patterns.py` | Each regex pattern, extraction edge cases |
| Unit: extraction | `tests/unit/test_extraction.py` | extract_semantic_from_correction() |
| Unit: context_mixin | `tests/unit/test_context_mixin.py` | MongoDB operations with mock |
| Unit: verifier | `tests/unit/test_verifier.py` | TrustVerifier with mock semantics |
| Integration: full flow | `tests/integration/test_semantic_flow.py` | correction → capture → verify → query |

---

## Scope Boundaries

**In scope:**
- `semantic_core/` package with all 6 modules
- `services/trust/verifier.py` extending verifier_base
- MongoDB schema migration (add fields to correction_rules)
- Pre-query trust verification hooks

**Out of scope (for this plan):**
- LLM-based semantic extraction (future task)
- Cross-workspace shared semantics (future task)
- Visualization of semantic definitions (frontend)
- Auto-validation execution (future task)
- Permission/govstack on semantics (future task)

---

## Success Criteria

1. `from services.semantic_core import extract_semantic_from_correction` works
2. Corrections with semantic patterns stored with `MetricSemantic` on `CorrectionRule`
3. `TrustVerifier.verify_query()` returns `TrustVerificationResult` before LLM execution
4. Unit tests pass for all 4 core modules
5. Semantic context appears in AI response metadata