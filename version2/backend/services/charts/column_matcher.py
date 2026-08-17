"""
Column Matcher Service
======================
Provides intelligent column matching for chart generation.

Handles cases where LLM suggests column names that don't exactly match
the dataset columns (case variations, spaces vs underscores, synonyms,
token/word overlap, domain-specific terms).

Author: Signal AI Team
"""

import logging
import re
from typing import List, Tuple, Optional, Dict, Any, Set
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class ColumnMatcher:
    """
    Match LLM-suggested columns to actual dataset columns using multiple strategies:

    1. Exact match
    2. Case-insensitive match
    3. Underscore/space normalization
    4. Synonym matching (general + domain-specific)
    5. Token overlap matching (Jaccard similarity on word tokens)
    6. Partial token match (LLM sugggests abbreviated version of a real column)
    7. Fuzzy string matching (SequenceMatcher)
    """

    SYNONYMS = {
        "date": [
            "timestamp",
            "datetime",
            "created_at",
            "updated_at",
            "time",
            "day",
            "month",
            "year",
        ],
        "timestamp": ["date", "datetime", "created_at", "time"],
        "year": ["yr", "years"],
        "month": ["mo", "months", "monthly"],
        "quarter": ["qtr", "q", "quarterly"],
        "revenue": ["sales", "income", "amount", "total", "value", "gmv", "earnings"],
        "sales": ["revenue", "amount", "total", "gmv"],
        "price": ["cost", "amount", "value", "unit_price", "rate"],
        "profit": ["margin", "earnings", "net_income"],
        "quantity": ["count", "qty", "num", "number", "units", "volume"],
        "count": ["quantity", "total", "num", "number", "frequency"],
        "category": ["type", "group", "segment", "class", "kind", "category_name"],
        "product": ["item", "sku", "name", "product_name"],
        "region": ["location", "area", "territory", "zone", "country", "state", "city", "province"],
        "customer": ["user", "client", "buyer", "account", "member"],
        "id": ["_id", "identifier", "key", "code"],
        "name": ["title", "label", "description"],
        "gender": ["sex", "male", "female"],
        "age": ["age_group", "age_range", "generation"],
        "education": [
            "edu",
            "educational",
            "school",
            "learning",
            "enrollment",
            "enrolment",
            "oosr",
            "out_of_school",
        ],
        "rate": [
            "percentage",
            "percent",
            "ratio",
            "proportion",
            "share",
            "completion_rate",
            "rates",
            "oosr",
            "out_of_school_rate",
        ],
        "completion": [
            "graduate",
            "graduation",
            "complete",
            "completed",
            "attainment",
            "enrollment",
        ],
        "primary": ["elementary", "basic", "prim"],
        "secondary": ["high_school", "sec", "upper_secondary", "lower_secondary"],
        "tertiary": ["higher", "college", "university", "post_secondary"],
        "enrollment": [
            "enrolment",
            "enrolled",
            "participation",
            "attendance",
            "registration",
            "completion",
        ],
        "population": ["people", "persons", "total_pop", "inhabitants", "demographic"],
        "income": ["earnings", "wage", "salary", "revenue_per_capita", "gdp_per_capita", "profit"],
        "growth": ["change", "increase", "decrease", "trend", "delta", "growth_rate"],
        "score": ["grade", "result", "rating", "mark", "performance"],
        "index": ["indicator", "metric", "measure", "benchmark"],
        "level": [
            "grade",
            "stage",
            "tier",
            "class",
            "standard",
            "primary",
            "secondary",
            "tertiary",
        ],
    }

    @classmethod
    def match(
        cls, suggested: str, available: List[str], threshold: float = 0.55
    ) -> Tuple[Optional[str], float]:
        """
        Find the best matching column from available columns.

        Uses a cascade of strategies, from high-precision to high-recall.

        Args:
            suggested: Column name suggested by LLM
            available: List of actual column names in dataset
            threshold: Minimum similarity threshold (0.0-1.0)

        Returns:
            Tuple of (matched_column, confidence_score)
            Returns (None, 0.0) if no match found above threshold
        """
        if not suggested or not available:
            return None, 0.0

        # 1. Exact match
        if suggested in available:
            logger.debug(f"Exact match found: {suggested}")
            return suggested, 1.0

        # 2. Case-insensitive match
        suggested_lower = suggested.lower()
        for col in available:
            if col.lower() == suggested_lower:
                logger.debug(f"Case-insensitive match: {suggested} \u2192 {col}")
                return col, 0.98

        # 3. Normalized match (spaces, underscores, hyphens, dots)
        suggested_normalized = cls._normalize(suggested)
        for col in available:
            if cls._normalize(col) == suggested_normalized:
                logger.debug(f"Normalized match: {suggested} \u2192 {col}")
                return col, 0.95

        best_match = None
        best_score = 0.0

        # Score every available column with combined strategy
        for col in available:
            col_normalized = cls._normalize(col)
            score = cls._combined_score(
                suggested, suggested_lower, suggested_normalized, col, col_normalized
            )
            if score > best_score:
                best_score = score
                best_match = col

        if best_score >= threshold:
            logger.debug(
                f"Combined match: {suggested} \u2192 {best_match} (score: {best_score:.2f})"
            )
            return best_match, best_score

        logger.warning(
            f"No match found for column: {suggested} (best: {best_match} @ {best_score:.2f})"
        )
        return None, 0.0

    @classmethod
    def _tokenize(cls, text: str) -> Set[str]:
        text = text.strip()
        text = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", text)
        text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", text)
        text = re.sub(r"[^a-zA-Z0-9]", "_", text)
        tokens = {t.lower() for t in text.split("_") if t and len(t) >= 2}
        return tokens

    @classmethod
    def _token_jaccard(cls, tokens_a: Set[str], tokens_b: Set[str]) -> float:
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)

    @classmethod
    def _partial_token_match(cls, tokens_suggested: Set[str], tokens_col: Set[str]) -> float:
        if not tokens_suggested or not tokens_col:
            return 0.0
        matches = 0
        for st in tokens_suggested:
            best_for_token = 0.0
            for ct in tokens_col:
                if st == ct:
                    best_for_token = max(best_for_token, 1.0)
                elif len(st) >= 3 and (st in ct or ct in st):
                    best_for_token = max(best_for_token, 0.6)
                elif len(st) >= 4 and (st.startswith(ct) or ct.startswith(st)):
                    best_for_token = max(best_for_token, 0.4)
                elif cls._is_synonym(st, ct):
                    best_for_token = max(best_for_token, 0.85)
                elif len(st) >= 4 and len(ct) >= 4:
                    # Fuzzy token match for singular/plural and morphological variants
                    # e.g. country ↔ countries, category ↔ categories
                    ratio = SequenceMatcher(None, st, ct).ratio()
                    if ratio >= 0.75:
                        best_for_token = max(best_for_token, 0.65)
            matches += best_for_token
        return matches / max(len(tokens_suggested), 1)

    @classmethod
    def _combined_score(
        cls,
        suggested: str,
        suggested_lower: str,
        suggested_normalized: str,
        col: str,
        col_normalized: str,
    ) -> float:
        tokens_s = cls._tokenize(suggested)
        tokens_c = cls._tokenize(col)

        seq_score = max(
            SequenceMatcher(None, suggested_lower, col.lower()).ratio(),
            SequenceMatcher(None, suggested_normalized, col_normalized).ratio(),
        )
        jaccard_score = cls._token_jaccard(tokens_s, tokens_c)
        partial_score = cls._partial_token_match(tokens_s, tokens_c)

        synonym_score = 0.0
        if tokens_s and tokens_c:
            syn_matches = 0
            for st in tokens_s:
                for ct in tokens_c:
                    if cls._is_synonym(st, ct):
                        syn_matches += 1
                        break
            synonym_score = syn_matches / len(tokens_s)

        if seq_score >= 0.90:
            return seq_score
        if jaccard_score >= 0.90:
            return jaccard_score

        score = (
            0.25 * seq_score + 0.20 * jaccard_score + 0.30 * partial_score + 0.25 * synonym_score
        )

        if jaccard_score >= 0.4 and seq_score >= 0.3:
            score = min(1.0, score + 0.08)

        if tokens_s and tokens_c:
            shorter = tokens_s if len(tokens_s) <= len(tokens_c) else tokens_c
            longer = tokens_c if len(tokens_s) <= len(tokens_c) else tokens_s
            if shorter and all(t in longer for t in shorter):
                score = max(score, 0.75)

        return min(score, 1.0)

    @classmethod
    def match_multiple(
        cls, suggested_columns: List[str], available: List[str], threshold: float = 0.6
    ) -> Dict[str, Tuple[Optional[str], float]]:
        """
        Match multiple suggested columns to available columns.

        Returns:
            Dict mapping suggested → (matched, confidence)
        """
        results = {}
        for suggested in suggested_columns:
            results[suggested] = cls.match(suggested, available, threshold)
        return results

    @classmethod
    def validate_and_fix_chart_config(
        cls, chart_config: Dict[str, Any], available_columns: List[str], threshold: float = 0.55
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validate and auto-correct column references in a chart config.

        Args:
            chart_config: Chart configuration from LLM
            available_columns: List of actual columns in dataset
            threshold: Minimum similarity for column matching

        Returns:
            Tuple of (fixed_config, list_of_corrections_made)
        """
        corrections = []
        fixed_config = chart_config.copy()

        # Pre-process: strip parenthetical annotations from column fields
        # LLMs often append aggregation hints like (median), (sum) after column names
        _PAREN_ANNOTATION = re.compile(r"\s*\([^)]*\)\s*")
        for field in ["x", "y", "labels", "values", "column", "group_by", "color", "size"]:
            if field in fixed_config and isinstance(fixed_config[field], str):
                val = fixed_config[field]
                stripped = _PAREN_ANNOTATION.sub("", val).strip()
                if stripped != val:
                    logger.debug(f"Stripped annotation from {field}: '{val}' → '{stripped}'")
                    fixed_config[field] = stripped

        # Column fields to check
        column_fields = ["x", "y", "labels", "values", "column", "group_by", "color", "size"]

        for field in column_fields:
            if field in fixed_config:
                original = fixed_config[field]

                # Skip if it's not a string (could be a list or dict)
                if not isinstance(original, str):
                    continue

                # Skip special values (aggregation keywords are not column names)
                if original.lower() in ["count", "sum", "average", "mean", "median", "max", "min"]:
                    corrections.append(f"{field}: '{original}' → aggregation keyword, removed")
                    fixed_config.pop(field, None)
                    continue

                # Try to match
                matched, confidence = cls.match(original, available_columns, threshold)

                # Only substitute if confidence is high enough (65%+)
                # Lowered from 75% — the new combined scoring is more conservative
                # and 0.65 represents a genuinely useful match
                if matched and matched != original and confidence >= 0.65:
                    fixed_config[field] = matched
                    corrections.append(
                        f"{field}: '{original}' → '{matched}' (confidence: {confidence:.0%})"
                    )
                elif matched and matched != original and confidence < 0.65:
                    # Low confidence match — drop the field instead of guessing wrong
                    corrections.append(
                        f"{field}: '{original}' → LOW CONFIDENCE ({confidence:.0%}), column name ambiguous"
                    )
                    fixed_config.pop(field, None)  # Remove the low-confidence substitution
                elif not matched and original not in available_columns:
                    corrections.append(f"{field}: '{original}' → NOT FOUND (below threshold)")
                    fixed_config.pop(field, None)  # Remove unmatchable column reference

        if corrections:
            logger.info(f"Chart config corrections: {corrections}")

        return fixed_config, corrections

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize column name for comparison."""
        result = text.lower()
        result = re.sub(r"[^a-zA-Z0-9]", "_", result)
        result = re.sub(r"_+", "_", result)
        return result.strip("_")

    @classmethod
    def _is_synonym(cls, word1: str, word2: str) -> bool:
        """Check if two words are synonyms based on our synonym table."""
        w1 = cls._normalize(word1)
        w2 = cls._normalize(word2)

        # Check both directions
        for base, synonyms in cls.SYNONYMS.items():
            all_related = [base] + synonyms
            all_related_normalized = [cls._normalize(s) for s in all_related]

            if w1 in all_related_normalized and w2 in all_related_normalized:
                return True

        return False


# Singleton instance
column_matcher = ColumnMatcher()
