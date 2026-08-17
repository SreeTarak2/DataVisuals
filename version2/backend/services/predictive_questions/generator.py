"""
predictive_questions/generator.py — Predictive Question Generator

The core engine that generates realistic business questions from a dataset's
intelligence profile. Uses a hybrid approach:

  1. DETERMINISTIC ENGINE (always runs, zero LLM cost):
     - Extract measures, dimensions, time columns from intelligence profile
     - For each template × measure × dimension, produce a seed question
     - Deduplicate, rank, group by analytical layer

  2. LLM ENRICHMENT (optional, async):
     - Feed seed questions + rich intelligence context to a small LLM
     - LLM rewrites them into context-aware, human-like questions
       (e.g. "Which regions are dragging down Q3 revenue?" instead of
       "What is total revenue by region?")
     - Falls back to deterministic output if LLM unavailable

This is the "Metric-Dimension Matrix + LLM Polish" approach:
  Deterministic: Measures × Dimensions × Templates → Form letters
  LLM: Form letters + Stats + Domain → Real business questions
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from .templates import (
    ALL_TEMPLATES,
    TEMPLATES_BY_LAYER,
    AnalyticalLayer,
    PredictiveQuestion,
    QuestionTemplate,
)

logger = logging.getLogger(__name__)

# ── Default limits ────────────────────────────────────────────────────────────

DEFAULT_MAX_QUESTIONS = 30
DEFAULT_MAX_PER_LAYER = 10


class PredictiveQuestionGenerator:
    """
    Generates predictive business questions from dataset intelligence.

    Usage:
        questions = predictive_question_generator.generate(intelligence)
        # questions is a list of PredictiveQuestion objects
    """

    # ── Column Extraction ─────────────────────────────────────────────────

    def _extract_measures(
        self, intelligence: dict
    ) -> list[dict]:
        """Extract measure/numeric columns from intelligence data.

        Returns list of dicts with 'name', 'business_category', 'polarity'.
        """
        columns = intelligence.get("columns", [])
        measures = []
        for col in columns:
            role = col.get("semantic_role", "").lower()
            if role in ("measure", "rate", "count"):
                measures.append({
                    "name": col.get("name", ""),
                    "business_category": col.get("business_category", "general"),
                    "polarity": col.get("polarity", "higher_is_better"),
                    "confidence": col.get("classification_confidence", 0.5),
                })
        return measures

    def _extract_dimensions(
        self, intelligence: dict
    ) -> list[dict]:
        """Extract dimension/categorical columns from intelligence data.

        Returns list of dicts with 'name', 'behavioral_role'.
        """
        columns = intelligence.get("columns", [])
        dimensions = []
        for col in columns:
            role = col.get("semantic_role", "").lower()
            if role == "dimension":
                dimensions.append({
                    "name": col.get("name", ""),
                    "behavioral_role": col.get("behavioral_role", "category"),
                })
        return dimensions

    def _extract_time_columns(self, intelligence: dict) -> list[str]:
        """Extract time/date columns from intelligence data."""
        columns = intelligence.get("columns", [])
        time_cols = []
        for col in columns:
            role = col.get("semantic_role", "").lower()
            if role == "time":
                time_cols.append(col.get("name", ""))
        return time_cols

    def _extract_geo_columns(self, intelligence: dict) -> list[str]:
        """Extract geographic columns from intelligence data."""
        columns = intelligence.get("columns", [])
        geo_cols = []
        for col in columns:
            geo_role = col.get("geo_role")
            if geo_role:
                geo_cols.append(col.get("name", ""))
        return geo_cols

    def _make_column_label(self, col_name: str) -> str:
        """Convert a column name to a natural language label.

        E.g. 'total_revenue' → 'Total Revenue', 'customer_id' → 'Customer ID'
        """
        label = col_name.replace("_", " ").replace("-", " ").strip()
        # Title case but preserve acronyms
        words = label.split()
        result = []
        for w in words:
            if w.upper() == w and len(w) <= 4:
                result.append(w.upper())
            else:
                result.append(w.capitalize())
        return " ".join(result)

    # ── Template Matching ─────────────────────────────────────────────────

    def _get_applicable_templates(
        self,
        has_measure: bool,
        has_dimension: bool,
        has_time: bool,
        has_two_metrics: bool,
        layers: Optional[list[AnalyticalLayer]] = None,
    ) -> list[QuestionTemplate]:
        """Get templates that are applicable given available column types."""
        templates = []
        source = (
            TEMPLATES_BY_LAYER
            if layers is None
            else {l: TEMPLATES_BY_LAYER[l] for l in layers if l in TEMPLATES_BY_LAYER}
        )
        for layer_templates in source.values():
            for t in layer_templates:
                if t.requires_metric and not has_measure:
                    continue
                if t.requires_dimension and not has_dimension:
                    continue
                if t.requires_time and not has_time:
                    continue
                if t.requires_two_metrics and not has_two_metrics:
                    continue
                templates.append(t)
        return templates

    # ── Question Generation ───────────────────────────────────────────────

    def _question_id(self, template_id: str,
                     metric: Optional[str],
                     dimension: Optional[str],
                     metric2: Optional[str]) -> str:
        """Generate a deterministic unique ID for a question."""
        parts = [template_id]
        if metric:
            parts.append(metric[:20])
        if dimension:
            parts.append(dimension[:20])
        if metric2:
            parts.append(metric2[:20])
        return "_".join(parts).lower().replace(" ", "_")

    def _fill_template(
        self,
        template: QuestionTemplate,
        metric_label: Optional[str] = None,
        dimension_label: Optional[str] = None,
        metric2_label: Optional[str] = None,
    ) -> str:
        """Fill a template pattern with actual column labels."""
        text = template.pattern
        if metric_label and "{metric}" in text:
            text = text.replace("{metric}", metric_label)
        if dimension_label and "{dimension}" in text:
            text = text.replace("{dimension}", dimension_label)
        if metric2_label and "{metric2}" in text:
            text = text.replace("{metric2}", metric2_label)

        # Remove any remaining unfilled slots (e.g. if template doesn't
        # require a dimension but the pattern has it)
        text = text.replace("{metric}", "the data")
        text = text.replace("{dimension}", "the data")
        text = text.replace("{metric2}", "the data")

        # Clean up double spaces
        text = " ".join(text.split())
        return text

    def _generate_for_template(
        self,
        template: QuestionTemplate,
        measures: list[dict],
        dimensions: list[dict],
        time_cols: list[str],
    ) -> list[PredictiveQuestion]:
        """Generate all valid questions for a single template."""
        questions = []
        measure_names = [m["name"] for m in measures]
        dim_names = [d["name"] for d in dimensions]
        time_dim_label = "Time"  # generic label for time

        if template.requires_two_metrics and len(measure_names) >= 2:
            # Generate question for each metric pair
            for i, m1 in enumerate(measure_names):
                for m2 in measure_names[i + 1:]:
                    q = PredictiveQuestion(
                        id=self._question_id(template.id, m1, None, m2),
                        layer=template.layer,
                        question=self._fill_template(
                            template,
                            metric_label=self._make_column_label(m1),
                            metric2_label=self._make_column_label(m2),
                        ),
                        template_id=template.id,
                        metric=m1,
                        metric2=m2,
                        complexity=template.complexity,
                    )
                    questions.append(q)
                    if len(questions) >= DEFAULT_MAX_PER_LAYER:
                        return questions

        elif template.requires_dimension and template.requires_time:
            # Generate for each metric × dimension pair
            for m in measure_names[:3]:
                for d in dim_names[:5]:
                    q = PredictiveQuestion(
                        id=self._question_id(template.id, m, d, None),
                        layer=template.layer,
                        question=self._fill_template(
                            template,
                            metric_label=self._make_column_label(m),
                            dimension_label=self._make_column_label(d),
                        ),
                        template_id=template.id,
                        metric=m,
                        dimension=d,
                        complexity=template.complexity,
                    )
                    questions.append(q)

        elif template.requires_dimension:
            # Generate for each metric × dimension pair
            for m in measure_names[:3]:
                for d in dim_names[:5]:
                    q = PredictiveQuestion(
                        id=self._question_id(template.id, m, d, None),
                        layer=template.layer,
                        question=self._fill_template(
                            template,
                            metric_label=self._make_column_label(m),
                            dimension_label=self._make_column_label(d),
                        ),
                        template_id=template.id,
                        metric=m,
                        dimension=d,
                        complexity=template.complexity,
                    )
                    questions.append(q)

        elif template.requires_time and time_cols:
            # Generate for each metric with time context
            for m in measure_names[:3]:
                q = PredictiveQuestion(
                    id=self._question_id(template.id, m, None, None),
                    layer=template.layer,
                    question=self._fill_template(
                        template,
                        metric_label=self._make_column_label(m),
                    ),
                    template_id=template.id,
                    metric=m,
                    complexity=template.complexity,
                )
                questions.append(q)

        elif template.requires_metric:
            # Simple metric-only question
            for m in measure_names[:3]:
                q = PredictiveQuestion(
                    id=self._question_id(template.id, m, None, None),
                    layer=template.layer,
                    question=self._fill_template(
                        template,
                        metric_label=self._make_column_label(m),
                    ),
                    template_id=template.id,
                    metric=m,
                    complexity=template.complexity,
                )
                questions.append(q)

        else:
            # No column dependencies — static question
            q = PredictiveQuestion(
                id=template.id,
                layer=template.layer,
                question=template.pattern,
                template_id=template.id,
                complexity=template.complexity,
            )
            questions.append(q)

        return questions

    # ── LLM Enrichment ─────────────────────────────────────────────────

    async def _llm_enrich_questions(
        self,
        seed_questions: list[PredictiveQuestion],
        intelligence: dict,
        user_id: Optional[str] = None,
    ) -> Optional[list[PredictiveQuestion]]:
        """
        Send seed questions + intelligence context to an LLM for refinement.

        The LLM rewrites the template-generated questions into more
        context-aware, human-like questions. It can:
        - Merge similar questions
        - Add domain-specific framing (e.g. "Which regions are dragging
          down Q3 revenue?" instead of "What is revenue by region?")
        - Drop irrelevant questions
        - Generate new questions based on data patterns

        Returns refined list, or None on failure (caller falls back to seed).
        """
        try:
            from llm.router import llm_router
        except ImportError:
            logger.warning("[PredictiveQG] llm_router unavailable — skipping LLM enrichment")
            return None

        # ── Build intelligence context summary for the LLM ──

        # Measures summary
        measures = self._extract_measures(intelligence)
        dimensions = self._extract_dimensions(intelligence)
        time_cols = self._extract_time_columns(intelligence)
        geo_cols = self._extract_geo_columns(intelligence)

        measures_str = "; ".join(
            f"{m['name']} ({m.get('business_category', 'general')}, "
            f"{m.get('polarity', 'higher_is_better')})"
            for m in measures[:8]
        ) or "none detected"

        dimensions_str = "; ".join(
            f"{d['name']} ({d.get('behavioral_role', 'category')})"
            for d in dimensions[:8]
        ) or "none detected"

        time_str = "; ".join(time_cols) or "none detected"
        geo_str = "; ".join(geo_cols) or "none detected"

        # Domain info
        domain = intelligence.get("domain", {})
        domain_name = "unknown"
        if isinstance(domain, dict):
            top = domain.get("top_candidate", {})
            llm_v = domain.get("llm_verdict", {})
            domain_name = (
                llm_v.get("domain", "")
                or (top.get("domain_name", "") if isinstance(top, dict) else "")
                or "unknown"
            )

        # Temporal info
        temporal = intelligence.get("temporal", {})
        if isinstance(temporal, dict):
            date_col = temporal.get("date_column", "")
            date_range = temporal.get("date_range_days", 0)
        else:
            date_col = ""
            date_range = 0

        # ── Build seed questions summary ──
        seed_by_layer: dict[str, list[str]] = {}
        for q in seed_questions:
            layer = q.layer.value
            if layer not in seed_by_layer:
                seed_by_layer[layer] = []
            if len(seed_by_layer[layer]) < 5:  # cap per layer for prompt length
                seed_by_layer[layer].append(q.question)

        seed_summary = "\n\n".join(
            f"### {layer.title()}\n" + "\n".join(f"- {qq}" for qq in qs)
            for layer, qs in seed_by_layer.items()
            if qs
        )

        prompt = f"""\
You are an expert Business Intelligence analyst helping a user understand what questions they should ask about their data before building a dashboard.

## Dataset Context
Domain: {domain_name}

### Measures (metrics you can aggregate)
{measures_str}

### Dimensions (categories you can group by)
{dimensions_str}

### Time Columns
{time_str}

### Geographic Columns
{geo_str}
{"" if not date_range else f"\nData spans {date_range} days (primary date column: {date_col})"}

## Seed Questions (generated automatically)
These are template-based starting points. Your job is to refine them.

{seed_summary}

## Your Task
Refine these into realistic questions a business user would actually ask.
For each question, you can:
- Add business context (e.g. "Which regions are underperforming?")
- Merge similar questions together
- Drop questions that don't make sense for this data
- Add ONE or TWO new questions based on patterns you see in the data

Rules:
- MAXIMUM 15 questions total
- Each question must be grounded in actual dataset columns
- Questions should feel like a real stakeholder meeting, not a template
- Vary difficulty: some quick answers, some deep investigations
- Use natural language, no jargon

Return JSON ONLY:
{{
  "questions": [
    {{
      "question": "Which regions are underperforming on revenue this quarter?",
      "layer": "diagnostic",
      "complexity": "moderate"
    }}
  ]
}}"""

        try:
            response = await llm_router.call(
                prompt=prompt,
                model_role="intent_engine",
                expect_json=True,
                temperature=0.5,
                max_tokens=1024,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(f"[PredictiveQG] LLM enrichment failed: {e}")
            return None

        if not isinstance(response, dict):
            logger.warning("[PredictiveQG] LLM response not a dict — skipping enrichment")
            return None

        raw_questions = response.get("questions", [])
        if not isinstance(raw_questions, list) or not raw_questions:
            logger.warning("[PredictiveQG] LLM returned empty questions — falling back")
            return None

        # ── Parse LLM output into PredictiveQuestion objects ──
        refined: list[PredictiveQuestion] = []
        for i, raw_q in enumerate(raw_questions):
            if not isinstance(raw_q, dict):
                continue
            question_text = raw_q.get("question", "").strip()
            if not question_text or len(question_text) < 10:
                continue

            layer_str = raw_q.get("layer", "strategic").strip().lower()
            try:
                layer = AnalyticalLayer(layer_str)
            except ValueError:
                layer = AnalyticalLayer.STRATEGIC

            complexity = raw_q.get("complexity", "moderate").strip().lower()
            if complexity not in ("simple", "moderate", "complex"):
                complexity = "moderate"

            refined.append(PredictiveQuestion(
                id=f"llm_{i}",
                layer=layer,
                question=question_text,
                template_id="llm_enriched",
                complexity=complexity,
            ))

        if not refined:
            logger.warning("[PredictiveQG] No valid questions parsed from LLM — falling back")
            return None

        logger.info(
            "[PredictiveQG] LLM enrichment produced %d refined questions",
            len(refined),
        )
        return refined

    # ── Main Generation Entry Points ───────────────────────────────────────

    def generate(
        self,
        intelligence: dict,
        layers: Optional[list[AnalyticalLayer]] = None,
        max_questions: int = DEFAULT_MAX_QUESTIONS,
        max_per_layer: int = DEFAULT_MAX_PER_LAYER,
    ) -> list[PredictiveQuestion]:
        """Generate predictive questions from dataset intelligence.

        SYNCHRONOUS path: purely deterministic template filling.
        Zero LLM calls. Use for fast, predictable results.

        Args:
            intelligence: UnifiedIntelligenceResult dict (or any dict with
                a 'columns' list containing semantic_role, name, etc.).
            layers: Optional filter — only generate questions for these
                analytical layers. If None, all layers are used.
            max_questions: Maximum total questions to generate.
            max_per_layer: Maximum questions per analytical layer.

        Returns:
            List of PredictiveQuestion objects, grouped by layer.
        """
        return self._generate_deterministic(
            intelligence, layers, max_questions, max_per_layer
        )

    async def generate_async(
        self,
        intelligence: dict,
        layers: Optional[list[AnalyticalLayer]] = None,
        max_questions: int = DEFAULT_MAX_QUESTIONS,
        max_per_layer: int = DEFAULT_MAX_PER_LAYER,
        use_llm: bool = True,
        user_id: Optional[str] = None,
    ) -> list[PredictiveQuestion]:
        """Generate predictive questions with optional LLM enrichment.

        ASYNC path: runs deterministic engine first, then optionally
        enriches with an LLM pass. Falls back to deterministic if LLM
        is unavailable or fails.

        Args:
            intelligence: UnifiedIntelligenceResult dict.
            layers: Optional filter for specific analytical layers.
            max_questions: Maximum total questions to generate.
            max_per_layer: Maximum questions per analytical layer.
            use_llm: If True, attempt LLM enrichment. Deterministic
                fallback used on failure.
            user_id: Optional user ID for LLM cost tracking.

        Returns:
            List of PredictiveQuestion objects.
        """
        # Step 1: Always run deterministic engine
        seed = self._generate_deterministic(
            intelligence, layers, max_questions, max_per_layer
        )

        # Step 2: Attempt LLM enrichment
        if use_llm:
            enriched = await self._llm_enrich_questions(seed, intelligence, user_id=user_id)
            if enriched is not None:
                logger.info(
                    "[PredictiveQG] LLM enrichment successful: %d questions (was %d deterministic)",
                    len(enriched), len(seed),
                )
                return enriched

            logger.info(
                "[PredictiveQG] LLM enrichment unavailable — returning %d deterministic questions",
                len(seed),
            )

        return seed

    def _generate_deterministic(
        self,
        intelligence: dict,
        layers: Optional[list[AnalyticalLayer]] = None,
        max_questions: int = DEFAULT_MAX_QUESTIONS,
        max_per_layer: int = DEFAULT_MAX_PER_LAYER,
    ) -> list[PredictiveQuestion]:
        """Purely deterministic question generation — zero LLM calls.

        This is the Metric-Dimension Matrix approach:
          Given: Measures = [Revenue, Cost, Users], Dimensions = [Region, Product]
          The matrix produces: "What is Revenue by Region?",
          "What is Revenue by Product?", etc.
        """
        # ── 1. Extract columns ────────────────────────────────────────────
        measures = self._extract_measures(intelligence)
        dimensions = self._extract_dimensions(intelligence)
        time_cols = self._extract_time_columns(intelligence)

        has_measure = len(measures) > 0
        has_dimension = len(dimensions) > 0
        has_time = len(time_cols) > 0
        has_two_metrics = len(measures) >= 2

        logger.info(
            "[PredictiveQG] Extracted %d measures, %d dimensions, %d time cols",
            len(measures), len(dimensions), len(time_cols),
        )

        if not has_measure:
            logger.warning("[PredictiveQG] No measure columns found — generating limited questions")
            # Still generate non-metric questions
            measures = [{"name": "records", "business_category": "general"}]
            has_measure = True

        # ── 2. Get applicable templates ───────────────────────────────────
        templates = self._get_applicable_templates(
            has_measure=has_measure,
            has_dimension=has_dimension,
            has_time=has_time,
            has_two_metrics=has_two_metrics,
            layers=layers,
        )

        logger.info(
            "[PredictiveQG] %d applicable templates out of %d total",
            len(templates), len(ALL_TEMPLATES),
        )

        # ── 3. Generate questions ─────────────────────────────────────────
        all_questions: list[PredictiveQuestion] = []
        seen_ids: set[str] = set()

        # First, add the count question (always relevant)
        all_questions.append(PredictiveQuestion(
            id="strat_count_records",
            layer=AnalyticalLayer.STRATEGIC,
            question="How many records are in this dataset?",
            template_id="strat_count_records",
            complexity="simple",
        ))

        # Sort templates: simple first, then moderate, then complex
        complexity_rank = {"simple": 0, "moderate": 1, "complex": 2}
        templates.sort(key=lambda t: complexity_rank.get(t.complexity, 0))

        for template in templates:
            if len(all_questions) >= max_questions:
                break

            # Count questions already generated for this layer
            layer_count = sum(
                1 for q in all_questions
                if q.layer == template.layer
            )
            if layer_count >= max_per_layer:
                continue

            generated = self._generate_for_template(
                template, measures, dimensions, time_cols
            )

            for q in generated:
                if q.id in seen_ids:
                    continue
                if len(all_questions) >= max_questions:
                    break
                # Check per-layer limit
                layer_count = sum(
                    1 for x in all_questions
                    if x.layer == q.layer
                )
                if layer_count >= max_per_layer:
                    continue

                seen_ids.add(q.id)
                all_questions.append(q)

        # ── 4. Sort by layer order ────────────────────────────────────────
        layer_order = {
            AnalyticalLayer.STRATEGIC: 0,
            AnalyticalLayer.DIAGNOSTIC: 1,
            AnalyticalLayer.ROOT_CAUSE: 2,
            AnalyticalLayer.EXPLORATORY: 3,
            AnalyticalLayer.FORECAST: 4,
        }
        all_questions.sort(key=lambda q: (
            layer_order.get(q.layer, 99),
            complexity_rank.get(q.complexity, 0),
        ))

        logger.info(
            "[PredictiveQG] Generated %d questions across %d layers",
            len(all_questions),
            len(set(q.layer for q in all_questions)),
        )
        return all_questions

    def generate_for_dataset(
        self,
        dataset_intelligence: dict,
        max_questions: int = 30,
    ) -> dict:
        """Generate questions and return as a structured JSON-friendly dict.

        SYNCHRONOUS — deterministic only, zero LLM calls.

        Args:
            dataset_intelligence: UnifiedIntelligenceResult dict.
            max_questions: Maximum total questions.

        Returns:
            Dict with 'questions' (list of dicts) and 'metadata' (summary).
        """
        questions = self.generate(
            dataset_intelligence,
            max_questions=max_questions,
        )
        return self._format_output(dataset_intelligence, questions, generator="deterministic_template")

    async def generate_for_dataset_async(
        self,
        dataset_intelligence: dict,
        max_questions: int = 30,
        use_llm: bool = True,
        user_id: Optional[str] = None,
    ) -> dict:
        """Generate questions with optional LLM enrichment.

        ASYNC — runs deterministic engine, then enriches with LLM.

        Args:
            dataset_intelligence: UnifiedIntelligenceResult dict.
            max_questions: Maximum total questions.
            use_llm: If True, attempt LLM enrichment.
            user_id: Optional user ID for cost tracking.

        Returns:
            Dict with 'questions' (list of dicts), 'by_layer' grouping,
            and 'metadata' including generator source.
        """
        questions = await self.generate_async(
            dataset_intelligence,
            max_questions=max_questions,
            use_llm=use_llm,
            user_id=user_id,
        )

        # Determine generator source from first question's template_id
        has_llm = any(q.template_id == "llm_enriched" for q in questions)
        generator = "llm_enriched" if has_llm else "deterministic_template"

        return self._format_output(dataset_intelligence, questions, generator=generator)

    def _format_output(
        self,
        dataset_intelligence: dict,
        questions: list[PredictiveQuestion],
        generator: str = "deterministic_template",
    ) -> dict:
        """Format questions into the standard output shape."""
        # Group by layer
        by_layer = {}
        for q in questions:
            layer = q.layer.value
            if layer not in by_layer:
                by_layer[layer] = []
            by_layer[layer].append(q.to_dict())

        layer_counts = {layer: len(qs) for layer, qs in by_layer.items()}

        return {
            "questions": [q.to_dict() for q in questions],
            "by_layer": by_layer,
            "metadata": {
                "total": len(questions),
                "layers": layer_counts,
                "generator": generator,
                "has_measures": any(
                    c.get("semantic_role", "").lower()
                    in ("measure", "rate", "count")
                    for c in dataset_intelligence.get("columns", [])
                ),
                "has_dimensions": any(
                    c.get("semantic_role", "").lower() == "dimension"
                    for c in dataset_intelligence.get("columns", [])
                ),
            },
        }


# Singleton
predictive_question_generator = PredictiveQuestionGenerator()
