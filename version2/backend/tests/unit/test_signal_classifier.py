import asyncio

from services.feedback.signal_classifier import signal_classifier


class TestExtractCorrectionTerm:
    def test_leading_no_pattern(self):
        result = signal_classifier.extract_correction_term(
            "no, revenue is recognized revenue", ""
        )
        assert result == ("revenue", "recognized revenue", "revenue = recognized revenue")

    def test_actually_pattern(self):
        result = signal_classifier.extract_correction_term(
            "actually, churn refers to cancellation rate", ""
        )
        assert result is not None
        assert result[0] == "churn"
        assert result[1] == "cancellation rate"

    def test_means_pattern(self):
        result = signal_classifier.extract_correction_term(
            "revenue means recognized revenue", ""
        )
        assert result == ("revenue", "recognized revenue", "revenue = recognized revenue")

    def test_should_be_pattern(self):
        result = signal_classifier.extract_correction_term(
            "mrr should be monthly recurring revenue", ""
        )
        assert result is not None
        assert result[0] == "mrr"
        assert result[1] == "monthly recurring revenue"

    def test_equals_pattern(self):
        result = signal_classifier.extract_correction_term(
            "gross margin = total revenue - cogs", ""
        )
        assert result is not None
        assert result[0] == "gross margin"
        assert "cogs" in result[1]

    def test_rejected_alternative_stripped(self):
        # "is mrr, not arr" → corrected term should be "mrr" only
        result = signal_classifier.extract_correction_term(
            "no, the metric is mrr, not arr", ""
        )
        assert result is None  # "metric" is a stopword subject → conservatively skipped

    def test_not_a_correction(self):
        assert signal_classifier.extract_correction_term("show me the top products", "") is None
        assert signal_classifier.extract_correction_term("", "") is None
        assert signal_classifier.extract_correction_term("i mean revenue", "") is None

    def test_single_letter_term_rejected(self):
        assert signal_classifier.extract_correction_term("no, x is y", "") is None

    def test_stopword_leading_corrected_term_rejected(self):
        # "revenue is is recognized" → corrected term "is recognized" starts
        # with a stopword → parse is over-consumed → rejected
        assert signal_classifier.extract_correction_term("no, revenue is is recognized", "") is None

    def test_metric_scoped_as_workspace(self):
        result = signal_classifier.extract_correction_term(
            "revenue is recognized revenue", ""
        )
        assert result is not None


class TestDetectReusableCorrection:
    def test_metric_term_gets_workspace_scope(self):
        result = asyncio.run(
            signal_classifier.detect_reusable_correction(
                user_id="u1",
                workspace_id="w1",
                correction_text="no, revenue is recognized revenue",
                original_response="Revenue was $120K.",
            )
        )
        assert result is not None
        assert result["original_term"] == "revenue"
        assert result["corrected_term"] == "recognized revenue"
        assert result["is_metric_term"] is True
        assert result["scope"] == "workspace"

    def test_non_metric_gets_conversation_scope(self):
        result = asyncio.run(
            signal_classifier.detect_reusable_correction(
                user_id="u1",
                workspace_id="w1",
                correction_text="no, the segment is enterprise customers",
                original_response="",
            )
        )
        assert result is not None
        assert result["scope"] == "conversation"

    def test_non_correction_returns_none(self):
        result = asyncio.run(
            signal_classifier.detect_reusable_correction(
                user_id="u1",
                workspace_id="w1",
                correction_text="show me the top products",
                original_response="",
            )
        )
        assert result is None
