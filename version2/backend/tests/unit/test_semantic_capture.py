import pytest
from services.feedback.semantic_capture import semantic_capture


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
        assert semantic_capture.is_semantic_correction("x", "y") is True  # "x means y" matches

    def test_infer_validation_rules_positive(self):
        _, rules = semantic_capture.extract_metric_semantic("revenue", "total revenue")
        assert len(rules) > 0
        assert any(r.rule_type == "RANGE" for r in rules)

    def test_means_pattern(self):
        result = semantic_capture.extract_metric_semantic("revenue", "recognized revenue per GAAP")
        assert result is not None
        metric, _ = result
        assert metric.metric_name == "revenue"
        assert "GAAP" in metric.definition

    def test_is_pattern(self):
        result = semantic_capture.extract_metric_semantic("churn", "cancellation rate")
        assert result is not None
        metric, _ = result
        assert metric.metric_name == "churn"

    def test_refers_to_pattern(self):
        result = semantic_capture.extract_metric_semantic("ARR", "annual recurring revenue")
        assert result is not None
        metric, _ = result
        assert metric.metric_name == "arr"

    def test_extract_always_detected_due_to_means_construction(self):
        result = semantic_capture.extract_metric_semantic("x", "y")
        assert result is not None
        metric, _ = result
        assert metric.metric_name == "x"
        assert metric.definition == "y"

    def test_with_query_context(self):
        result = semantic_capture.extract_metric_semantic(
            original_term="revenue",
            corrected_term="recognized revenue",
            query_context="in the context of GAAP accounting",
        )
        assert result is not None
        metric, _ = result

    def test_validation_rules_rate_metric(self):
        _, rules = semantic_capture.extract_metric_semantic("growth_rate", "yoy growth percentage")
        assert len(rules) > 0
        assert any("0 <=" in r.expression for r in rules)
