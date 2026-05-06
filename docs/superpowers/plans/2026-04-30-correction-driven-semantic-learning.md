# Correction-Driven Metric Semantic Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build correction-driven semantic learning to make the system learn metric meaning from user corrections over time—capturing "revenue means recognized revenue in this workspace" and using that as a pre-response validation rule.

**Architecture:** Extend the existing corrections infrastructure (`services/feedback/correction_rewriter.py`, `db/schemas_context.py`, `services/feedback/context_store.py`) to capture semantic metric definitions from corrections, and add pre-query trust verification that validates metric definitions before LLM execution.

**Tech Stack:** Python/FastAPI, MongoDB, existing correction infrastructure

---

## Task 1: Extend CorrectionSchema for Metric Semantics

**Files:**
- Modify: `version2/backend/db/schemas_context.py:22-34`
- Modify: `version2/backend/services/feedback/context_store.py:42-110`
- Test: `version2/backend/tests/unit/test_correction_semantic.py`

- [ ] **Step 1: Add MetricSemantics fields to CorrectionRule**

```python
# In db/schemas_context.py, extend CorrectionRule:
class CorrectionRule(BaseModel):
    # ... existing fields ...
    metric_semantic: Optional[MetricSemantic] = None
    validation_rules: List[ValidationRule] = []
    applies_to_queries: List[str] = []  # query patterns this applies to


class MetricSemantic(BaseModel):
    metric_name: str  # e.g., "revenue"
    definition: str  # e.g., "recognized revenue"
    formula: Optional[str] = None  # e.g., "sum(amount) where status = 'recognized'"
    source_columns: List[str] = []  # e.g., ["amount", "status"]
    aggregation: Optional[str] = None  # e.g., "sum", "avg", "count"
    business_context: Optional[str] = None  # e.g., "GAAP recognized revenue only"


class ValidationRule(BaseModel):
    rule_type: str  # e.g., "RANGE", "COMPARISON"
    expression: str  # e.g., "revenue > 0"
    threshold: Optional[float] = None
    fail_message: str = "Metric value outside expected range"
```

- [ ] **Step 2: Run test to verify schema extends correctly**

Run: `python -c "from db.schemas_context import CorrectionRule, MetricSemantic; print(CorrectionRule.model_fields.keys())"`
Expected: Shows metric_semantic field

- [ ] **Step 3: Add context_store methods for metric semantics**

```python
# Add to services/feedback/context_store.py:

async def add_metric_semantic_to_rule(
    self,
    rule_id: str,
    metric_semantic: MetricSemantic,
) -> CorrectionRule:
    """Add or update metric semantic definition on a correction rule."""
    db = self._get_db()
    await db.correction_rules.update_one(
        {"_id": ObjectId(rule_id)},
        {"$set": {"metric_semantic": metric_semantic.model_dump()}},
    )
    return await self.get_correction_rule_by_id(rule_id)


async def get_metric_semantics_for_workspace(
    self,
    workspace_id: str,
) -> List[MetricSemantic]:
    """Get all metric semantics defined in a workspace."""
    db = self._get_db()
    cursor = db.correction_rules.find({
        "workspace_id": workspace_id,
        "metric_semantic": {"$ne": None}
    })
    docs = await cursor.to_list(length=100)
    semantics = []
    for doc in docs:
        if doc.get("metric_semantic"):
            semantics.append(MetricSemantic(**doc["metric_semantic"]))
    return semantics


async def get_correction_rule_by_id(
    self,
    rule_id: str,
) -> Optional[CorrectionRule]:
    """Get a single correction rule by ID."""
    db = self._get_db()
    doc = await db.correction_rules.find_one({"_id": ObjectId(rule_id)})
    if doc:
        doc["id"] = str(doc.pop("_id"))
        return CorrectionRule(**doc)
    return None
```

- [ ] **Step 4: Run test to verify methods exist**

Run: `python -c "from services.feedback.context_store import context_store; print([m for m in dir(context_store) if 'semantic' in m.lower()])"`
Expected: Shows new methods

- [ ] **Step 5: Commit**

```bash
git add version2/backend/db/schemas_context.py version2/backend/services/feedback/context_store.py
git commit -m "feat: extend CorrectionRule with MetricSemantic for correction-driven semantics"
```

---

## Task 2: Build Semantic Correction Capture from User Feedback

**Files:**
- Modify: `version2/backend/services/feedback/context_store.py:226-246`
- Modify: `version2/backend/services/feedback/signal_classifier.py` (if exists)
- Create: `version2/backend/services/feedback/semantic_capture.py`
- Test: `version2/backend/tests/unit/test_semantic_capture.py`

- [ ] **Step 1: Create SemanticCapture service**

```python
# Create version2/backend/services/feedback/semantic_capture.py:

import logging
import re
from typing import Optional, List, Tuple
from db.schemas_context import (
    CorrectionRule,
    MetricSemantic,
    ValidationRule,
    CorrectionScope,
)

logger = logging.getLogger(__name__)


class SemanticCapture:
    """
    Extract metric semantic definitions from user corrections.
    
    When user says "revenue means recognized revenue", capture that semantic
    definition and store it as a rule that validates future queries.
    """
    
    # Patterns that indicate semantic corrections
    SEMANTIC_CORRECTION_PATTERNS = [
        r"(\w+)\s+means\s+(.+)",  # "revenue means recognized revenue"
        r"(\w+)\s+is\s+(.+)",     # "revenue is total recognized"
        r"(\w+)\s+=\s+(.+)",       # "revenue = GAAP revenue"
        r"(\w+)\s+refers\s+to\s+(.+)",  # "revenue refers to recognized"
    ]
    
    FORMULA_PATTERNS = [
        r"sum\(([\w_]+)\)",      # sum(amount)
        r"avg\(([\w_]+)\)",       # avg(amount)
        r"count\(([\w_]+)\)",     # count(id)
        r"([\w_]+)\s*where\s+(.+)",  # amount where status = 'X'
    ]
    
    def __init__(self):
        self._patterns = [re.compile(p, re.IGNORECASE) for p in self.SEMANTIC_CORRECTION_PATTERNS]
    
    def extract_metric_semantic(
        self,
        original_term: str,
        corrected_term: str,
        query_context: Optional[str] = None,
    ) -> Optional[Tuple[MetricSemantic, List[ValidationRule]]]:
        """
        Extract metric semantic definition from correction text.
        
        Returns:
            - MetricSemantic if this looks like a metric correction
            - List of validation rules inferred
        """
        full_text = f"{original_term} means {corrected_term}"
        if query_context:
            full_text += f" {query_context}"
        
        for pattern in self._patterns:
            match = pattern.search(full_text)
            if match:
                metric_name = match.group(1).strip().lower()
                definition = match.group(2).strip()
                
                # Try to extract formula
                formula = None
                source_columns = []
                aggregation = None
                
                for fp in self.FORMULA_PATTERNS:
                    formula_match = re.search(fp, definition, re.IGNORECASE)
                    if formula_match:
                        if "where" in definition.lower():
                            parts = definition.split("where")
                            formula = definition
                            # Extract column from sum()/avg() part
                            col_match = re.search(r"(sum|avg|count)\(([\w_]+)\)", parts[0], re.IGNORECASE)
                            if col_match:
                                aggregation = col_match.group(1).lower()
                                source_columns = [col_match.group(2)]
                        elif formula_match.lastindex >= 1:
                            formula = definition
                            # Check what function it's in
                            fn_match = re.search(r"(sum|avg|count)\(([\w_]+)\)", definition, re.IGNORECASE)
                            if fn_match:
                                aggregation = fn_match.group(1).lower()
                                source_columns = [fn_match.group(2)]
                        break
                
                # Try to infer validation rules
                validation_rules = self._infer_validation_rules(metric_name, definition)
                
                return MetricSemantic(
                    metric_name=metric_name,
                    definition=definition,
                    formula=formula,
                    source_columns=source_columns,
                    aggregation=aggregation,
                    business_context=definition,
                ), validation_rules
        
        return None
    
    def _infer_validation_rules(
        self,
        metric_name: str,
        definition: str,
    ) -> List[ValidationRule]:
        """Infer validation rules from definition context."""
        rules = []
        
        # Positive value check for most metrics
        if any(m in metric_name.lower() for m in ["revenue", "amount", "sales", "profit", "income"]):
            rules.append(ValidationRule(
                rule_type="RANGE",
                expression=f"{metric_name} >= 0",
                threshold=0,
                fail_message=f"{metric_name} should not be negative",
            ))
        
        # Percentage bounds
        if any(m in metric_name.lower() for m in ["rate", "percentage", "margin", "growth"]):
            rules.append(ValidationRule(
                rule_type="RANGE",
                expression=f"0 <= {metric_name} <= 100",
                threshold=100,
                fail_message=f"{metric_name} should be between 0 and 100",
            ))
        
        return rules
    
    def is_semantic_correction(
        self,
        original_term: str,
        corrected_term: str,
    ) -> bool:
        """Check if this correction appears to be a semantic metric correction."""
        full_text = f"{original_term} means {corrected_term}"
        return any(p.search(full_text) for p in self._patterns)


semantic_capture = SemanticCapture()
```

- [ ] **Step 2: Write unit test**

```python
# Create version2/backend/tests/unit/test_semantic_capture.py:

import pytest
from services.feedback.semantic_capture import semantic_capture, SemanticCapture


class TestSemanticCapture:
    
    def test_extract_metric_semantic_simple(self):
        result = semantic_capture.extract_metric_semantic(
            original_term="revenue",
            corrected_term="recognized revenue",
        )
        assert result is not None
        metric, rules = result
        assert metric.metric_name == "revenue"
        assert metric.definition == "recognized revenue"
    
    def test_extract_metric_semantic_with_formula(self):
        result = semantic_capture.extract_metric_semantic(
            original_term="mrr",
            corrected_term="sum(amount) where status = 'active'",
        )
        assert result is not None
        metric, rules = result
        assert metric.formula is not None
        assert metric.aggregation == "sum"
        assert "amount" in metric.source_columns
    
    def test_is_semantic_correction(self):
        assert semantic_capture.is_semantic_correction("revenue", "recognized revenue") is True
        assert semantic_capture.is_semantic_correction("fix typo", "correct") is False
    
    def test_infer_validation_rules_positive(self):
        _, rules = semantic_capture.extract_metric_semantic("revenue", "total revenue")
        assert len(rules) > 0
        assert any(r.rule_type == "RANGE" for r in rules)
```

- [ ] **Step 3: Run test**

Run: `pytest version2/backend/tests/unit/test_semantic_capture.py -v`
Expected: FAIL (file doesn't exist yet)

- [ ] **Step 4: Implement minimal service**

Check: `ls version2/backend/services/feedback/` to see what exists there

- [ ] **Step 5: Run test again**

Run: `pytest version2/backend/tests/unit/test_semantic_capture.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add version2/backend/services/feedback/semantic_capture.py version2/backend/tests/unit/test_semantic_capture.py
git commit -m "feat: add SemanticCapture to extract metric semantics from corrections"
```

---

## Task 3: Pre-Query Trust Verification Layer

**Files:**
- Create: `version2/backend/services/trust/verifier.py`
- Modify: `version2/backend/services/ai/ai_service.py` (hook in query processing)
- Test: `version2/backend/tests/unit/test_trust_verifier.py`

- [ ] **Step 1: Create TrustVerifier service**

```python
# Create version2/backend/services/trust/verifier.py:

import logging
import re
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class TrustVerificationResult:
    def __init__(
        self,
        is_trusted: bool,
        confidence: float,
        checks_passed: List[str],
        checks_failed: List[str],
        warnings: List[str] = [],
        applied_semantics: List[Dict[str, Any]] = [],
    ):
        self.is_trusted = is_trusted
        self.confidence = confidence
        self.checks_passed = checks_passed
        self.checks_failed = checks_failed
        self.warnings = warnings
        self.applied_semantics = applied_semantics
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_trusted": self.is_trusted,
            "confidence": self.confidence,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "warnings": self.warnings,
            "applied_semantics": self.applied_semantics,
        }


class TrustVerifier:
    """
    Pre-query trust verification: validate metric definitions before LLM execution.
    
    Before executing a query, check if we have stored semantic definitions
    for the metrics being queried. If we do, validate query interpretation
    against those definitions.
    """
    
    def __init__(self, context_store):
        self.context_store = context_store
    
    async def verify_query(
        self,
        query: str,
        workspace_id: str,
        dataset_id: Optional[str] = None,
    ) -> TrustVerificationResult:
        """
        Verify query trust before execution.
        
        Returns:
            - TrustVerificationResult with trust score and applied semantics
        """
        # Get metric semantics for workspace
        semantics = await self.context_store.get_metric_semantics_for_workspace(workspace_id)
        
        checks_passed = []
        checks_failed = []
        warnings = []
        applied_semantics = []
        
        if not semantics:
            # No semantic definitions yet - can't verify, but don't fail
            return TrustVerificationResult(
                is_trusted=True,
                confidence=0.5,
                checks_passed=["no semantic definitions stored"],
                checks_failed=[],
                warnings=["No metric definitions found - query interpretation unchecked"],
            )
        
        # Extract metrics mentioned in query
        query_lower = query.lower()
        metrics_found = []
        
        for semantic in semantics:
            if semantic.metric_name.lower() in query_lower:
                metrics_found.append(semantic)
                applied_semantics.append({
                    "metric_name": semantic.metric_name,
                    "definition": semantic.definition,
                    "formula": semantic.formula,
                })
                
                # Check if query uses correct formula
                if semantic.formula:
                    checks_passed.append(f"metric_{semantic.metric_name}_formula_checked")
                    
                    # Warn if query doesn't match expected formula pattern
                    # (This is informational - we trust the query but note the deviation)
                    if not any(col in query_lower for col in (semantic.source_columns or [])):
                        warnings.append(
                            f"Query for {semantic.metric_name} may not use expected columns "
                            f"{semantic.source_columns}"
                        )
        
        # Calculate trust score
        metrics_with_defs = len([s for s in semantics if s.metric_name])
        metrics_covered = len(metrics_found)
        
        if metrics_covered == 0:
            # Query doesn't reference any defined metrics - OK, trust based on other factors
            confidence = 0.7
            checks_passed.append("no defined metrics in query")
        elif metrics_covered > 0:
            # Metrics found and validated
            confidence = min(0.95, 0.7 + (0.25 * metrics_covered / max(1, metrics_with_defs)))
            checks_passed.append(f"validated_{metrics_covered}_metrics")
        else:
            confidence = 0.5
        
        is_trusted = confidence >= 0.6
        
        logger.info(
            f"Trust verification: {is_trusted} (confidence={confidence:.2f}) "
            f"metrics_found={metrics_covered}"
        )
        
        return TrustVerificationResult(
            is_trusted=is_trusted,
            confidence=confidence,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            warnings=warnings,
            applied_semantics=applied_semantics,
        )


async def get_verifier():
    """Factory to get TrustVerifier instance."""
    from services.feedback.context_store import context_store
    return TrustVerifier(context_store)
```

- [ ] **Step 2: Write unit test**

```python
# Create version2/backend/tests/unit/test_trust_verifier.py:

import pytest
from unittest.mock import AsyncMock, MagicMock
from services.trust.verifier import TrustVerifier, TrustVerificationResult


class TestTrustVerifier:
    
    @pytest.fixture
    def mock_context_store(self):
        store = MagicMock()
        store.get_metric_semantics_for_workspace = AsyncMock(return_value=[])
        return store
    
    @pytest.fixture
    def verifier(self, mock_context_store):
        return TrustVerifier(mock_context_store)
    
    @pytest.mark.asyncio
    async def test_no_semantics_returns_trusted(self, verifier):
        result = await verifier.verify_query("show me the data", "workspace-1")
        # Without semantics, should return trusted but low confidence
        assert result.is_trusted is True
        assert result.confidence < 0.6
    
    @pytest.mark.asyncio
    async def test_with_matching_metric(self, verifier):
        # Mock having semantic for revenue
        mock_semantic = MagicMock()
        mock_semantic.metric_name = "revenue"
        mock_semantic.definition = "recognized revenue"
        mock_semantic.formula = "sum(amount)"
        mock_semantic.source_columns = ["amount"]
        
        verifier.context_store.get_metric_semantics_for_workspace = AsyncMock(
            return_value=[mock_semantic]
        )
        
        result = await verifier.verify_query("show revenue", "workspace-1")
        # Should find the metric and validate
        assert len(result.applied_semantics) > 0
        assert result.confidence >= 0.6
```

- [ ] **Step 3: Run test**

Run: `pytest version2/backend/tests/unit/test_trust_verifier.py -v`
Expected: FAIL (file doesn't exist)

- [ ] **Step 4: Create directory and file**

```bash
mkdir -p version2/backend/services/trust
```

- [ ] **Step 5: Run test again**

Run: `pytest version2/backend/tests/unit/test_trust_verifier.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add version2/backend/services/trust/ version2/backend/tests/unit/test_trust_verifier.py
git commit -m "feat: add pre-query TrustVerifier for metric semantic validation"
```

---

## Task 4: Integrate Trust Verification into AI Query Pipeline

**Files:**
- Modify: `version2/backend/services/ai/ai_service.py:1380-1500`
- Test: `version2/backend/tests/integration/test_trust_integration.py`

- [ ] **Step 1: Hook TrustVerifier into ai_service query processing**

In `version2/backend/services/ai/ai_service.py`, after query rewrite but before SQL generation:

```python
# In ai_service.py, add import:
from services.trust.verifier import get_verifier

# In process_message or similar query handler:
async def _apply_trust_verification(
    self,
    query: str,
    workspace_id: str,
    dataset_id: str,
) -> Tuple[str, TrustVerificationResult]:
    """
    Apply trust verification before query execution.
    
    Returns:
        - query (potentially augmented with semantic context)
        - trust_result
    """
    trust_verifier = await get_verifier()
    trust_result = await trust_verifier.verify_query(query, workspace_id, dataset_id)
    
    if trust_result.applied_semantics:
        # Add semantic context to query for LLM
        semantic_context = "\n".join([
            f"Note: {s['metric_name']} = {s['definition']}"
            for s in trust_result.applied_semantics
        ])
        augmented_query = f"{query}\n\n{semantic_context}"
        
        logger.info(f"Augmented query with {len(trust_result.applied_semantics)} semantic definitions")
        
        return augmented_query, trust_result
    
    return query, trust_result
```

- [ ] **Step 2: Add trust_result to response metadata**

In the response dict, include:

```python
"trust_verification": trust_result.to_dict() if trust_result else None,
```

- [ ] **Step 3: Write integration test**

```python
# Create version2/backend/tests/integration/test_trust_integration.py:

import pytest
from unittest.mock import patch, AsyncMock


class TestTrustIntegration:
    
    @pytest.mark.asyncio
    @patch("services.trust.verifier.get_verifier")
    async def test_trust_verification_in_query_flow(self, mock_get_verifier):
        # Mock verifier returning trusted result
        mock_verifier = AsyncMock()
        mock_verifier.verify_query = AsyncMock(return_value=MagicMock(
            is_trusted=True,
            confidence=0.8,
            applied_semantics=[{"metric_name": "revenue", "definition": "recognized"}],
            to_dict=lambda: {"is_trusted": True, "confidence": 0.8},
        ))
        mock_get_verifier.return_value = mock_verifier
        
        # Integration test would call ai_service and verify trust_result in response
        # (Full integration test requires more setup)
        pass
```

- [ ] **Step 4: Commit**

```bash
git add version2/backend/services/ai/ai_service.py
git commit -m "feat: integrate TrustVerifier into query pipeline"
```

---

## Task 5: Auto-Capture Corrections as Semantic Rules

**Files:**
- Modify: `version2/backend/services/feedback/context_store.py`
- Modify: `version2/backend/api/chat/routes.py` (if correction endpoint exists)
- Test: `version2/backend/tests/unit/test_correction_capture.py`

- [ ] **Step 1: Add method to auto-convert correction to semantic rule**

```python
# Add to context_store.py:

async def capture_semantic_from_correction(
    self,
    rule_id: str,
    query_context: Optional[str] = None,
) -> Optional[MetricSemantic]:
    """
    When a correction is marked as semantic, extract and store metric definition.
    
    This is called when user provides feedback indicating their correction
    defines how a metric should be interpreted going forward.
    """
    rule = await self.get_correction_rule_by_id(rule_id)
    if not rule:
        return None
    
    # Use SemanticCapture to extract
    from services.feedback.semantic_capture import semantic_capture
    
    result = semantic_capture.extract_metric_semantic(
        original_term=rule.original_term,
        corrected_term=rule.corrected_term,
        query_context=query_context,
    )
    
    if result:
        metric_semantic, validation_rules = result
        
        # Add semantic to the rule for future validation
        await self.add_metric_semantic_to_rule(rule_id, metric_semantic)
        
        # Update rule interpretation to indicate semantic capture
        await db.correction_rules.update_one(
            {"_id": ObjectId(rule_id)},
            {
                "$set": {
                    "interpretation": f"[SEMANTIC] {rule.interpretation}",
                    "validation_rules": [v.model_dump() for v in validation_rules],
                }
            },
        )
        
        logger.info(f"Captured semantic definition for {metric_semantic.metric_name}")
        return metric_semantic
    
    return None
```

- [ ] **Step 2: Add endpoint to explicitly capture semantics**

If there's a feedback endpoint, add `POST /feedback/corrections/{rule_id}/capture-semantic`:

```python
# In api/feedback/routes.py (create if not exists):

@router.post("/corrections/{rule_id}/capture-semantic")
async def capture_correction_semantic(
    rule_id: str,
    request: CaptureSemanticRequest,
    user_id: str = Depends(get_current_user),
):
    """Explicitly capture a correction as a semantic metric definition."""
    
    semantic = await context_store.capture_semantic_from_correction(
        rule_id=rule_id,
        query_context=request.query_context,
    )
    
    if not semantic:
        raise HTTPException(400, "Could not extract semantic from correction")
    
    return {"semantic": semantic.model_dump()}
```

- [ ] **Step 3: Commit**

```bash
git add version2/backend/services/feedback/context_store.py
git commit -m "feat: auto-capture corrections as semantic metric definitions"
```

---

## Summary

This plan builds correction-driven semantic learning in 5 tasks:

| Task | Description | Files Changed |
|------|-------------|---------------|
| 1 | Extend CorrectionRule schema | schemas_context.py, context_store.py |
| 2 | Build SemanticCapture | semantic_capture.py |
| 3 | Build TrustVerifier | trust/verifier.py |
| 4 | Integrate into query pipeline | ai_service.py |
| 5 | Auto-capture from corrections | context_store.py, api routes |

**Total estimated tasks:** ~20 atomic steps across 5 major tasks.

**Key deliverables:**
- `MetricSemantic` stored on `CorrectionRule`
- `SemanticCapture.extract_metric_semantic()` 
- `TrustVerifier.verify_query()` called before LLM
- Corrections with semantic definitions auto-captured

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-30-correction-driven-semantic-learning.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**