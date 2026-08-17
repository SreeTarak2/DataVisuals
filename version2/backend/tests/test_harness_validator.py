"""
Unit tests for HarnessValidator — Self-Harness-Style Validation Gate.

Covers:
1. Self-consistency check (LLM-based, with mock)
2. Non-redundancy check (Jaccard similarity)
3. Non-regression check (LLM-based, with mock)
4. get_held_out_queries with query enrichment (substring matching)
5. Validation gate end-to-end (validate() method)
6. Edge cases (empty instruction, timeouts, MongoDB load)
"""

import sys
import os
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.insight_reflection.harness_validator import (
    HarnessValidator,
    ValidationResult,
    ValidationDecision,
    _DUPLICATE_SIMILARITY_THRESHOLD,
    _MIN_INSTRUCTION_LENGTH,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def validator():
    """Fresh HarnessValidator with no prior decisions and mock LLM router."""
    v = HarnessValidator()
    # Clear any cached decisions from singleton state in other tests
    v._decisions = []
    v._loaded_from_db = True  # Skip MongoDB lazy-load in tests
    # Mock the LLM router
    v._llm_router = MagicMock()
    v._llm_router.call = AsyncMock()
    return v


@pytest.fixture
def validator_with_history():
    """Validator with some pre-existing accepted/rejected decisions."""
    v = HarnessValidator()
    v._decisions = []
    v._loaded_from_db = True
    v._llm_router = MagicMock()
    v._llm_router.call = AsyncMock()

    # Add some accepted instructions
    v._decisions.append(ValidationDecision(
        conversation_id="conv_1",
        instruction="Always cite exact column names when providing answers.",
        failure_modes=["overly_generic"],
        accepted=True,
        reason="all checks passed",
        evidence={},
        timestamp="2026-01-01T00:00:00Z",
    ))
    v._decisions.append(ValidationDecision(
        conversation_id="conv_1",
        instruction="When comparing categories, always include sample sizes.",
        failure_modes=["missing_context"],
        accepted=True,
        reason="all checks passed",
        evidence={},
        timestamp="2026-01-02T00:00:00Z",
    ))
    v._decisions.append(ValidationDecision(
        conversation_id="conv_2",
        instruction="Use bullet points for lists of findings.",
        failure_modes=["poor_formatting"],
        accepted=True,
        reason="all checks passed",
        evidence={},
        timestamp="2026-01-01T00:00:00Z",
    ))
    # A rejected decision (should not be counted in redundancy check)
    v._decisions.append(ValidationDecision(
        conversation_id="conv_1",
        instruction="Rejected instruction.",
        failure_modes=["unclear"],
        accepted=False,
        reason="self-consistency check failed",
        evidence={},
        timestamp="2026-01-03T00:00:00Z",
    ))
    return v


# ═══════════════════════════════════════════════════════════════
# 1. Self-consistency check
# ═══════════════════════════════════════════════════════════════

class TestSelfConsistency:
    """Test _check_self_consistency — does the instruction address the failure modes?"""

    @pytest.mark.asyncio
    async def test_self_consistent(self, validator):
        """Instruction clearly addresses the failure mode."""
        validator._llm_router.call.return_value = {
            "addresses_failures": True,
            "rationale": "The instruction explicitly tells the model to cite specific columns, which addresses the 'overly_generic' failure mode.",
        }
        ok, evidence = await validator._check_self_consistency(
            instruction="Always cite exact column names with their values.",
            failure_modes=["overly_generic"],
        )
        assert ok is True, "Instruction addressing failure mode should pass"
        assert evidence["addresses_failures"] is True
        assert "columns" in evidence.get("rationale", "").lower()

    @pytest.mark.asyncio
    async def test_not_self_consistent(self, validator):
        """Instruction does not address the failure mode."""
        validator._llm_router.call.return_value = {
            "addresses_failures": False,
            "rationale": "Telling the model to 'be more verbose' does not address the 'hallucination' failure mode — it may make hallucinations worse.",
        }
        ok, evidence = await validator._check_self_consistency(
            instruction="Always respond with at least three paragraphs.",
            failure_modes=["hallucination"],
        )
        assert ok is False, "Instruction not addressing failure mode should fail"
        assert evidence["addresses_failures"] is False

    @pytest.mark.asyncio
    async def test_empty_failure_modes_skips(self, validator):
        """No failure modes → skip check (pass by default)."""
        ok, evidence = await validator._check_self_consistency(
            instruction="Some instruction.",
            failure_modes=[],
        )
        assert ok is True
        assert evidence.get("skipped") is True

    @pytest.mark.asyncio
    async def test_timeout_returns_skip(self, validator):
        """LLM timeout should skip (not reject) the check."""
        validator._llm_router.call.side_effect = asyncio.TimeoutError()
        ok, evidence = await validator._check_self_consistency(
            instruction="Be specific.",
            failure_modes=["overly_generic"],
        )
        assert ok is True, "Timeout should skip (not reject)"
        assert "timed out" in evidence.get("rationale", "").lower()

    @pytest.mark.asyncio
    async def test_non_dict_response_skips_check(self, validator):
        """Non-dict LLM response should skip (not fail) the check — same as timeout."""
        validator._llm_router.call.return_value = "I think it's fine"
        ok, evidence = await validator._check_self_consistency(
            instruction="Be specific.",
            failure_modes=["overly_generic"],
        )
        assert ok is True, "Non-dict response should skip (not fail)"
        assert "non-dict" in evidence.get("rationale", "").lower()

    @pytest.mark.asyncio
    async def test_general_exception_returns_failure(self, validator):
        """General exception should fail the check."""
        validator._llm_router.call.side_effect = RuntimeError("LLM unavailable")
        ok, evidence = await validator._check_self_consistency(
            instruction="Be specific.",
            failure_modes=["overly_generic"],
        )
        assert ok is False
        assert "unavailable" in evidence.get("rationale", "")


# ═══════════════════════════════════════════════════════════════
# 2. Non-redundancy check (Jaccard similarity)
# ═══════════════════════════════════════════════════════════════

class TestNonRedundancy:
    """Test _check_non_redundancy — Jaccard similarity duplicate detection."""

    @pytest.mark.asyncio
    async def test_exact_duplicate_detected(self, validator_with_history):
        """Exact same instruction should be detected as redundant."""
        dup, evidence = await validator_with_history._check_non_redundancy(
            instruction="Always cite exact column names when providing answers.",
            conversation_id="conv_1",
        )
        assert dup is True, "Exact duplicate should be detected"
        assert evidence["similarity"] >= _DUPLICATE_SIMILARITY_THRESHOLD

    @pytest.mark.asyncio
    async def test_near_duplicate_detected(self, validator_with_history):
        """Very similar instruction (same meaning, slightly different words) should be detected."""
        dup, evidence = await validator_with_history._check_non_redundancy(
            instruction="Always cite exact column names in your answers.",
            conversation_id="conv_1",
        )
        assert dup is True, "Near-duplicate should be detected"
        assert evidence["similarity"] >= _DUPLICATE_SIMILARITY_THRESHOLD

    @pytest.mark.asyncio
    async def test_different_instruction_not_redundant(self, validator_with_history):
        """Completely different instruction should not be flagged as redundant."""
        dup, evidence = await validator_with_history._check_non_redundancy(
            instruction="When showing trends, always include a date axis.",
            conversation_id="conv_1",
        )
        assert dup is False, "Different instruction should not be redundant"
        assert evidence["similarity"] < _DUPLICATE_SIMILARITY_THRESHOLD

    @pytest.mark.asyncio
    async def test_different_conversation_not_redundant(self, validator_with_history):
        """Instructions from different conversations should not affect redundancy."""
        dup, evidence = await validator_with_history._check_non_redundancy(
            instruction="Always cite exact column names when providing answers.",
            conversation_id="conv_NONEXISTENT",
        )
        assert dup is False, "No prior instructions for this conversation"
        assert evidence["found"] == 0

    @pytest.mark.asyncio
    async def test_short_instruction_skipped(self, validator_with_history):
        """Very short instructions (< _MIN_INSTRUCTION_LENGTH chars) should skip check."""
        dup, evidence = await validator_with_history._check_non_redundancy(
            instruction="Short.",
            conversation_id="conv_1",
        )
        assert dup is False, "Short instruction should skip"
        assert evidence.get("skipped") is True

    @pytest.mark.asyncio
    async def test_no_history_passes(self, validator):
        """Empty validator with no history → no duplicate found."""
        dup, evidence = await validator._check_non_redundancy(
            instruction="Always cite exact column names.",
            conversation_id="conv_new",
        )
        assert dup is False
        assert evidence["found"] == 0

    @pytest.mark.asyncio
    async def test_rejected_instructions_ignored(self, validator_with_history):
        """Rejected instructions should not be counted for redundancy."""
        # conv_1 has 2 accepted + 1 rejected
        # The rejected instruction should not appear in accepted instructions
        dup, evidence = await validator_with_history._check_non_redundancy(
            instruction="Rejected instruction.",
            conversation_id="conv_1",
        )
        # "Rejected instruction." vs "Rejected instruction." — these differ:
        # The rejected one has a period, the instruction uses "Rejected instruction." (no period added)
        # Actually, the instruction being checked is "Rejected instruction." with a period
        # The rejected instruction stored is "Rejected instruction." as well
        # But it's rejected, so it won't be in the accepted list
        # The accepted instructions for conv_1 are about columns and sample sizes
        # so this should not match
        assert dup is False, "Rejected instruction should not cause redundancy"
        assert evidence["similarity"] < 0.3


# ═══════════════════════════════════════════════════════════════
# 3. Non-regression check
# ═══════════════════════════════════════════════════════════════

class TestNonRegression:
    """Test _check_non_regression — would the instruction degrade past successes?"""

    @pytest.mark.asyncio
    async def test_low_regression_risk_passes(self, validator):
        """Low regression risk should pass the check."""
        validator._llm_router.call.return_value = {
            "regression_risk": "low",
            "rationale": "Adding specific constraints will not degrade responses to general questions.",
        }
        ok, evidence = await validator._check_non_regression(
            instruction="Always include sample sizes when comparing groups.",
            recent_successful_queries=["Show total revenue by region", "What is the growth rate?"],
        )
        assert ok is True, "Low risk should pass"
        assert evidence["risk"] == "low"

    @pytest.mark.asyncio
    async def test_high_regression_risk_fails(self, validator):
        """High regression risk should fail the check."""
        validator._llm_router.call.return_value = {
            "regression_risk": "high",
            "rationale": "Requiring sample sizes will make responses to simple metric queries unnecessarily verbose.",
        }
        ok, evidence = await validator._check_non_regression(
            instruction="Always include sample sizes when comparing groups.",
            recent_successful_queries=["Show total revenue by region"],
        )
        assert ok is False, "High risk should fail"
        assert evidence["risk"] == "high"

    @pytest.mark.asyncio
    async def test_medium_regression_risk_fails(self, validator):
        """Medium regression risk should also fail (conservative)."""
        validator._llm_router.call.return_value = {
            "regression_risk": "medium",
            "rationale": "May add unnecessary detail to simple queries.",
        }
        ok, evidence = await validator._check_non_regression(
            instruction="Always include sample sizes.",
            recent_successful_queries=["Show revenue"],
        )
        assert ok is False, "Medium risk should fail (conservative)"
        assert evidence["risk"] == "medium"

    @pytest.mark.asyncio
    async def test_no_held_out_queries_skips(self, validator):
        """No held-out queries → skip the check."""
        ok, evidence = await validator._check_non_regression(
            instruction="Some instruction.",
            recent_successful_queries=[],
        )
        assert ok is True
        assert evidence.get("skipped") is True

    @pytest.mark.asyncio
    async def test_timeout_returns_skip(self, validator):
        """LLM timeout should skip (not reject) the check."""
        validator._llm_router.call.side_effect = asyncio.TimeoutError()
        ok, evidence = await validator._check_non_regression(
            instruction="Be specific about dates.",
            recent_successful_queries=["Show revenue by month", "What was sales last quarter?"],
        )
        assert ok is True, "Timeout should skip"
        assert "timed out" in evidence.get("rationale", "").lower()

    @pytest.mark.asyncio
    async def test_non_dict_response_skips_check(self, validator):
        """Non-dict LLM response should skip (not fail) the check — same as timeout."""
        validator._llm_router.call.return_value = "looks fine to me"
        ok, evidence = await validator._check_non_regression(
            instruction="Be specific.",
            recent_successful_queries=["Show revenue"],
        )
        assert ok is True, "Non-dict response should skip (not fail)"
        assert "non-dict" in evidence.get("rationale", "").lower()

    @pytest.mark.asyncio
    async def test_queries_capped_at_three(self, validator):
        """Only the first 3 queries should be checked."""
        validator._llm_router.call.return_value = {
            "regression_risk": "low",
            "rationale": "Low risk.",
        }
        many_queries = [f"Query {i}" for i in range(20)]
        ok, evidence = await validator._check_non_regression(
            instruction="Be specific.",
            recent_successful_queries=many_queries,
        )
        assert ok is True
        assert evidence["queries_checked"] == 3, "Should only check 3 queries"


# ═══════════════════════════════════════════════════════════════
# 4. get_held_out_queries with query enrichment
# ═══════════════════════════════════════════════════════════════

class TestGetHeldOutQueries:
    """Test extraction of held-out queries from conversation messages."""

    @pytest.mark.asyncio
    async def test_basic_extraction(self, validator):
        """Extract user queries from messages."""
        messages = [
            {"role": "user", "content": "Show me total revenue"},
            {"role": "ai", "content": "Revenue is $1.2M"},
            {"role": "user", "content": "Break it down by region"},
            {"role": "ai", "content": "By region: North $500K, South $400K..."},
            {"role": "user", "content": "What is the trend over time?"},
        ]
        queries = await validator.get_held_out_queries(messages, max_queries=3)
        assert len(queries) == 3
        assert queries == [
            "Show me total revenue",
            "Break it down by region",
            "What is the trend over time?",
        ]

    @pytest.mark.asyncio
    async def test_exclude_current_query(self, validator):
        """Exclude the current query (the one being processed)."""
        messages = [
            {"role": "user", "content": "Show total revenue"},
            {"role": "ai", "content": "Revenue is $1M"},
            {"role": "user", "content": "Current query here"},  # This should be excluded
        ]
        queries = await validator.get_held_out_queries(
            messages, exclude_query="Current query here", max_queries=3
        )
        assert "Current query here" not in queries
        assert queries == ["Show total revenue"]

    @pytest.mark.asyncio
    async def test_exclude_with_substring_matching_enrichment(self, validator):
        """Query enrichment: the original query IS a contiguous substring of the
        enriched query. The system enriches 'show total revenue' to
        'show total revenue for each region'. The original is preserved as a
        contiguous substring, so the exclude should work.
        """
        messages = [
            {"role": "user", "content": "Show total revenue"},
            {"role": "ai", "content": "Revenue is $1M"},
            # Enriched version: original is preserved as a contiguous substring
            {"role": "user", "content": "show total revenue for each region"},
        ]
        # exclude_query is the ORIGINAL query (before enrichment)
        queries = await validator.get_held_out_queries(
            messages, exclude_query="show total revenue", max_queries=3
        )
        # The enriched query should be excluded because it contains the original
        assert "show total revenue for each region" not in queries
        assert queries == ["Show total revenue"]

    @pytest.mark.asyncio
    async def test_enriched_query_contains_original(self, validator):
        """When enriched query contains the original as a contiguous substring."""
        messages = [
            {
                "role": "user",
                "content": "list top selling products by total revenue for fiscal year 2026",
            },
        ]
        # 'top selling products' IS a contiguous substring of the stored query
        queries = await validator.get_held_out_queries(
            messages, exclude_query="top selling products", max_queries=3
        )
        assert len(queries) == 0, "Enriched query should be excluded"

    @pytest.mark.asyncio
    async def test_original_contains_enriched_edge_case(self, validator):
        """Edge case: original query contains the stored shortened query."""
        messages = [
            {"role": "user", "content": "revenue"},
        ]
        # 'revenue' IS a contiguous substring of the exclude query
        queries = await validator.get_held_out_queries(
            messages, exclude_query="show total revenue for each region", max_queries=3
        )
        # 'revenue' (in content) is in 'show total revenue for each region' (exclude_query)
        # So content in exclude_query → True → excluded
        assert len(queries) == 0

    @pytest.mark.asyncio
    async def test_short_messages_filtered(self, validator):
        """Messages with ≤10 chars should be filtered out."""
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "user", "content": "OK"},
            {"role": "user", "content": "What is the total revenue?"},  # Only this qualifies
        ]
        queries = await validator.get_held_out_queries(messages, max_queries=3)
        assert len(queries) == 1
        assert queries[0] == "What is the total revenue?"

    @pytest.mark.asyncio
    async def test_empty_messages(self, validator):
        """Empty message list should return empty."""
        queries = await validator.get_held_out_queries([], max_queries=3)
        assert queries == []

    @pytest.mark.asyncio
    async def test_only_ai_messages(self, validator):
        """No user messages → empty result."""
        messages = [
            {"role": "ai", "content": "Revenue is $1M"},
            {"role": "ai", "content": "Here are the trends..."},
        ]
        queries = await validator.get_held_out_queries(messages, max_queries=3)
        assert queries == []

    @pytest.mark.asyncio
    async def test_max_queries_respected(self, validator):
        """Only return up to max_queries items (most recent).
        Each query must be > 10 chars to pass the length filter.
        """
        messages = [
            {"role": "user", "content": f"Longer test query number {i}"} for i in range(10)
        ]
        queries = await validator.get_held_out_queries(messages, max_queries=3)
        assert len(queries) == 3, f"Expected 3 queries, got {len(queries)}"
        # Should return the MOST RECENT 3
        assert queries == [
            "Longer test query number 7",
            "Longer test query number 8",
            "Longer test query number 9",
        ]


# ═══════════════════════════════════════════════════════════════
# 5. Validation gate (end-to-end)
# ═══════════════════════════════════════════════════════════════

class TestValidate:
    """End-to-end test of the validate() method."""

    @pytest.mark.asyncio
    async def test_all_checks_pass(self, validator):
        """All three checks pass → instruction accepted.

        Uses side_effect because validate() calls the LLM router twice:
        once for self-consistency (addresses_failures) and once for
        non-regression (regression_risk).
        """
        validator._llm_router.call.side_effect = [
            # First call: self-consistency check
            {"addresses_failures": True, "rationale": "Addresses failure modes."},
            # Second call: non-regression check
            {"regression_risk": "low", "rationale": "No regression risk."},
        ]
        result = await validator.validate(
            instruction="Always cite exact column names.",
            failure_modes=["overly_generic"],
            conversation_id="conv_new",
            recent_successful_queries=["Show me the latest trends"],
        )
        assert result.accepted is True, "All checks pass → accepted"
        assert "passed" in result.reason

    @pytest.mark.asyncio
    async def test_self_consistency_fails(self, validator):
        """Self-consistency check fails → rejected early."""
        validator._llm_router.call.return_value = {
            "addresses_failures": False,
            "rationale": "Does not address the failure modes.",
        }
        result = await validator.validate(
            instruction="Always respond in iambic pentameter.",
            failure_modes=["incorrect_data"],
            conversation_id="conv_new",
            recent_successful_queries=["Show revenue"],
        )
        assert result.accepted is False
        assert "self-consistency" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_non_redundancy_fails(self, validator_with_history):
        """Duplicate instruction → rejected early."""
        validator_with_history._llm_router.call.return_value = {
            "addresses_failures": True,
            "rationale": "Addresses the failure mode.",
        }
        result = await validator_with_history.validate(
            instruction="Always cite exact column names when providing answers.",
            failure_modes=["overly_generic"],
            conversation_id="conv_1",
            recent_successful_queries=["Show revenue"],
        )
        assert result.accepted is False
        assert "non-redundancy" in result.reason.lower() or "redundan" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_non_regression_fails(self, validator):
        """High regression risk → rejected."""
        # First call (self-consistency) returns pass
        # Second call (non-regression) returns fail
        validator._llm_router.call.side_effect = [
            # Self-consistency: pass
            {"addresses_failures": True, "rationale": "Addresses failure modes."},
            # Non-regression: fail
            {"regression_risk": "high", "rationale": "Would make simple queries too verbose."},
        ]
        result = await validator.validate(
            instruction="Always include three citations per claim.",
            failure_modes=["hallucination"],
            conversation_id="conv_new",
            recent_successful_queries=["What is total revenue?"],
        )
        assert result.accepted is False
        assert "non-regression" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_empty_instruction_rejected(self, validator):
        """Empty or whitespace-only instruction → rejected immediately."""
        result = await validator.validate(
            instruction="   ",
            failure_modes=["overly_generic"],
            conversation_id="conv_1",
        )
        assert result.accepted is False
        assert "empty" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_no_failure_modes_skips_consistency(self, validator):
        """No failure modes → self-consistency check skipped."""
        validator._llm_router.call.return_value = {
            "regression_risk": "low",
            "rationale": "Low risk.",
        }
        result = await validator.validate(
            instruction="Be specific.",
            failure_modes=[],
            conversation_id="conv_new",
            recent_successful_queries=["Show revenue by region"],
        )
        assert result.accepted is True
        assert result.evidence.get("self_consistency", {}).get("skipped") is True

    @pytest.mark.asyncio
    async def test_skip_flags_respected(self, validator):
        """All skip flags set → bypass all checks and accept."""
        validator._llm_router.call.return_value = {
            "regression_risk": "high",
            "rationale": "Would cause issues.",
        }
        result = await validator.validate(
            instruction="Some instruction.",
            failure_modes=["overly_generic"],
            conversation_id="conv_new",
            recent_successful_queries=["Show revenue"],
            skip_consistency=True,
            skip_redundancy=True,
            skip_regression=True,
        )
        assert result.accepted is True, "Skip flags should bypass all checks"

    @pytest.mark.asyncio
    async def test_decision_logged_on_accept(self, validator):
        """Accepted decisions are stored in-memory.

        Uses side_effect because validate() calls the LLM router twice:
        once for self-consistency (addresses_failures) and once for
        non-regression (regression_risk).
        """
        validator._llm_router.call.side_effect = [
            # First call: self-consistency check
            {"addresses_failures": True, "rationale": "Addresses failure mode."},
            # Second call: non-regression check
            {"regression_risk": "low", "rationale": "No regression risk."},
        ]
        initial_count = len(validator._decisions)
        result = await validator.validate(
            instruction="Always cite exact column names.",
            failure_modes=["overly_generic"],
            conversation_id="conv_new",
            recent_successful_queries=["Show revenue"],
        )
        assert result.accepted is True
        assert len(validator._decisions) == initial_count + 1

    @pytest.mark.asyncio
    async def test_decision_logged_on_reject(self, validator):
        """Rejected decisions are also stored in-memory."""
        validator._llm_router.call.return_value = {
            "addresses_failures": False,
            "rationale": "Does not help.",
        }
        initial_count = len(validator._decisions)
        result = await validator.validate(
            instruction="Always respond in iambic pentameter.",
            failure_modes=["incorrect_data"],
            conversation_id="conv_new",
        )
        assert result.accepted is False
        assert len(validator._decisions) == initial_count + 1


# ═══════════════════════════════════════════════════════════════
# 6. Additional edge cases
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Additional edge cases for the validator."""

    @pytest.mark.asyncio
    async def test_get_history_empty(self, validator):
        """Empty history should return empty list."""
        history = await validator.get_history()
        assert history == []

    @pytest.mark.asyncio
    async def test_get_history_with_decisions(self, validator_with_history):
        """History should return stored decisions."""
        history = await validator_with_history.get_history()
        assert len(history) >= 3  # 3 accepted + 1 rejected across all convs
        for entry in history:
            assert "conversation_id" in entry
            assert "instruction" in entry
            assert "accepted" in entry
            assert "timestamp" in entry

    @pytest.mark.asyncio
    async def test_get_history_filtered_by_conversation(self, validator_with_history):
        """History filtered by conversation_id."""
        history = await validator_with_history.get_history(conversation_id="conv_1")
        assert len(history) == 3  # 2 accepted + 1 rejected for conv_1
        for entry in history:
            assert entry["conversation_id"] == "conv_1"

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, validator):
        """Empty validator stats."""
        stats = await validator.get_stats()
        assert stats["total_decisions"] == 0
        assert stats["accept_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_stats_with_decisions(self, validator_with_history):
        """Stats with mixed decisions."""
        stats = await validator_with_history.get_stats()
        assert stats["total_decisions"] == 4
        assert stats["accepted"] == 3
        assert stats["rejected"] == 1
        assert stats["accept_rate"] > 0.7


# ═══════════════════════════════════════════════════════════════
# 7. Fire-and-forget MongoDB persistence
# ═══════════════════════════════════════════════════════════════

class TestFireAndForgetPersistence:
    """Verify _log_decision uses asyncio.create_task (not await) for MongoDB."""

    @pytest.mark.asyncio
    async def test_persist_decision_is_fire_and_forget(self, validator):
        """
        _log_decision must NOT await _persist_decision directly.

        The verification strategy:
        - Replace _persist_decision with a tracking function that sets a flag
        - Mock asyncio.create_task so it doesn't execute the scheduled coroutine
        - Call _log_decision
        - If the flag is NOT set, _persist_decision was never awaited directly
          (it was wrapped in create_task, which our mock intercepted)
        - Also verify create_task was called at all
        """
        # Make self.db non-None so the MongoDB path is entered
        validator._db = MagicMock()

        # Track whether _persist_decision gets called directly
        persist_called_directly = False

        original_persist = validator._persist_decision

        async def tracking_persist(decision):
            nonlocal persist_called_directly
            persist_called_directly = True  # Would only be True if awaited directly
            return await original_persist(decision)

        validator._persist_decision = tracking_persist

        with patch.object(asyncio, "create_task") as mock_create_task:
            await validator._log_decision(
                conversation_id="conv_1",
                instruction="Test instruction",
                failure_modes=["test"],
                accepted=True,
                reason="all checks passed",
                evidence={"check": "value"},
            )

        # _persist_decision should NOT have been called directly
        # If _log_decision used `await self._persist_decision(...)`, the tracking
        # function would have been invoked. Since it wasn't, create_task was used.
        assert not persist_called_directly, (
            "_persist_decision should not be awaited directly — "
            "it should be wrapped in asyncio.create_task"
        )

        # create_task should have been called with our coroutine
        mock_create_task.assert_called_once()
        args, _ = mock_create_task.call_args
        assert len(args) == 1, "create_task should receive exactly one positional arg (coroutine)"

        # In-memory decision should be recorded immediately (proves _log_decision
        # returned without waiting for the MongoDB write)
        assert len(validator._decisions) == 1
        assert validator._decisions[0].instruction == "Test instruction"
        assert validator._decisions[0].accepted is True

    @pytest.mark.asyncio
    async def test_persist_decision_skipped_when_db_is_none(self, validator):
        """When self.db is None, _log_decision should skip create_task entirely.

        Patches db.database.get_database to return None so the behavior is
        deterministic regardless of whether MongoDB is running in the test
        environment (some drivers return lazy handles that appear non-None).
        """
        # Force the db property to return None by patching get_database
        with patch("db.database.get_database", return_value=None):
            validator._db = None  # Reset cached db handle so property re-evaluates

            with patch.object(asyncio, "create_task") as mock_create_task:
                await validator._log_decision(
                    conversation_id="conv_1",
                    instruction="Test instruction",
                    failure_modes=["test"],
                    accepted=True,
                    reason="all checks passed",
                    evidence={},
                )

            # create_task should NOT be called when db is None
            mock_create_task.assert_not_called()

        # But the in-memory decision should still be recorded
        assert len(validator._decisions) == 1

    @pytest.mark.asyncio
    async def test_persist_decision_handles_db_error(self, validator):
        """_persist_decision should catch exceptions without crashing."""
        decision = ValidationDecision(
            conversation_id="conv_1",
            instruction="Test instruction",
            failure_modes=["test"],
            accepted=True,
            reason="all checks passed",
            evidence={},
        )

        # Simulate a failing MongoDB (the mock raises on insert_one)
        mock_db = MagicMock()
        mock_db.harness_validation_log.insert_one = AsyncMock(side_effect=Exception("DB connection lost"))
        validator._db = mock_db

        # This should not raise — _persist_decision catches exceptions
        await validator._persist_decision(decision)

        # Verify insert_one was attempted
        mock_db.harness_validation_log.insert_one.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════
# 8. ValidationResult dataclass
# ═══════════════════════════════════════════════════════════════

class TestValidationResult:
    """Test the ValidationResult dataclass."""

    def test_accept_result(self):
        """Accepted result has correct fields."""
        r = ValidationResult(
            accepted=True,
            instruction="Test instruction",
            reason="all checks passed",
            evidence={"check_1": True},
            failure_modes=["test"],
        )
        assert r.accepted is True
        assert r.instruction == "Test instruction"
        assert r.reason == "all checks passed"
        assert r.evidence == {"check_1": True}
        assert r.failure_modes == ["test"]

    def test_reject_result_defaults(self):
        """Rejected result with default values."""
        r = ValidationResult(
            accepted=False,
            instruction="",
            reason="Empty instruction",
        )
        assert r.accepted is False
        assert r.evidence == {}
        assert r.failure_modes == []


# ═══════════════════════════════════════════════════════════════
# Run directly
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
