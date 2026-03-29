"""Professional PDF Report Generator.

Generates comprehensive analytical reports with:
- Narrative intelligence (AI story)
- Executive summary with key findings
- Full statistical analysis (correlations, trends, anomalies)
- Data quality scorecard
- Strategic action plan
- Appendix: column statistics
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId

from db.database import get_database

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates professional PDF reports from analysis data."""

    def __init__(self):
        self.template_dir = Path(__file__).parent / "templates"
        self.template_path = self.template_dir / "report_template.html"

    async def generate(
        self, dataset_id: str, include_charts: bool = True, preview: bool = False
    ) -> bytes:
        logger.info(f"Generating PDF report for dataset: {dataset_id}")

        dataset = await self._fetch_dataset_data(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_id}")

        story = await self._fetch_story(dataset_id, dataset)
        report_data = self._gather_report_data(dataset, story)
        html_content = self._render_template(report_data)

        if preview:
            return html_content

        return self._generate_pdf(html_content)

    # ──────────────────────────────────────────────────────────────────
    #  DATA FETCHING
    # ──────────────────────────────────────────────────────────────────

    async def _fetch_dataset_data(self, dataset_id: str) -> Optional[Dict]:
        try:
            db = get_database()
            try:
                dataset = await db.uploads.find_one({"_id": ObjectId(dataset_id)})
            except Exception:
                dataset = await db.uploads.find_one({"_id": dataset_id})
            return dataset
        except Exception as e:
            logger.error(f"Error fetching dataset: {e}")
            return None

    async def _fetch_story(self, dataset_id: str, dataset: Dict) -> Optional[Dict]:
        """
        Fetch story from the correct location.

        Priority order:
        1. db.datasets.insights_cache.story (primary cache, new path)
        2. dataset.cached_narrative_story (legacy fallback on db.uploads)
        3. dataset.insights.story (very old fallback)
        """
        try:
            db = get_database()

            # 1. Primary: db.datasets collection
            try:
                ds_doc = await db.datasets.find_one({"dataset_id": dataset_id})
                if not ds_doc:
                    ds_doc = await db.datasets.find_one({"_id": dataset_id})
                if not ds_doc:
                    try:
                        ds_doc = await db.datasets.find_one({"_id": ObjectId(dataset_id)})
                    except Exception:
                        pass

                if ds_doc:
                    cache = ds_doc.get("insights_cache", {}).get("story", {})
                    if cache:
                        story_data = cache.get("data", cache)
                        # story_data could be {"story": {...}} or the story object directly
                        story = story_data.get("story", story_data) if isinstance(story_data, dict) else None
                        if story and (story.get("findings") or story.get("opening") or story.get("title")):
                            logger.info("Story loaded from db.datasets.insights_cache.story")
                            return story
            except Exception as e:
                logger.warning(f"Could not fetch from db.datasets: {e}")

            # 2. Legacy: cached_narrative_story on uploads doc
            cached = dataset.get("cached_narrative_story")
            if cached:
                if isinstance(cached, dict):
                    story = cached.get("story", cached)
                    if story and isinstance(story, dict):
                        logger.info("Story loaded from cached_narrative_story")
                        return story

            # 3. Very old fallback: insights.story
            insights = dataset.get("insights", {})
            story = insights.get("story", insights.get("report"))
            if story and isinstance(story, dict) and (story.get("findings") or story.get("opening")):
                logger.info("Story loaded from insights.story")
                return story

            logger.info("No story found — report will use raw insights only")
            return None

        except Exception as e:
            logger.error(f"Error fetching story: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────
    #  DATA NORMALIZATION
    # ──────────────────────────────────────────────────────────────────

    def _normalize_story(self, story: Optional[Dict]) -> Dict:
        """
        Normalize story into a consistent format regardless of which generation
        path produced it.

        Handles two formats:
        A) New format (post _transform_to_frontend_format):
           {title, subtitle, opening: {hook, takeaway, why_matters},
            findings: [{title, narrative, evidence, importance}],
            complications: [{title, urgency, narrative, evidence, mitigation}],
            resolution: {story_conclusion, primary_action, secondary_actions, monitoring},
            metadata: {theme, overall_health, top_priority, ...}}

        B) Old format (raw LLM output, pre-fix):
           {headline: {title, subtitle, verdict}, opening_story, findings: [{headline, story, the_number, ...}],
            warnings: [{headline, story, urgency_label, what_to_do}],
            action_plan: {primary_action, supporting_actions},
            what_to_watch: [...], closing, metadata}
        """
        if not story:
            return {
                "title": "", "subtitle": "", "opening_hook": "", "takeaway": "",
                "why_matters": "", "findings": [], "complications": [],
                "primary_action": {}, "secondary_actions": [], "story_conclusion": "",
                "key_metrics_to_watch": [], "overall_health": "Unknown",
                "story_theme": "mixed", "top_priority": "", "reading_time": 3,
            }

        # Detect format by checking for new-format keys
        is_new_format = "opening" in story and isinstance(story.get("opening"), dict)

        if is_new_format:
            opening = story.get("opening", {})
            resolution = story.get("resolution", {})
            monitoring = resolution.get("monitoring", {})
            metadata = story.get("metadata", {})

            # Normalize findings
            findings = []
            for f in story.get("findings", []):
                findings.append({
                    "headline": f.get("title", f.get("headline", "")),
                    "narrative": f.get("narrative", f.get("story", "")),
                    "the_number": f.get("evidence", {}).get("key_metric", ""),
                    "what_it_means": "",
                    "importance": f.get("importance", 5),
                    "type": f.get("type", "discovery"),
                })

            # Normalize complications
            complications = []
            for c in story.get("complications", []):
                complications.append({
                    "headline": c.get("title", c.get("headline", "")),
                    "narrative": c.get("narrative", ""),
                    "urgency": c.get("urgency", "medium"),
                    "urgency_label": c.get("urgency", "medium").capitalize(),
                    "action": c.get("mitigation", ""),
                    "metric": c.get("evidence", {}).get("metric", ""),
                })

            # Normalize monitoring
            key_metrics = []
            for m in monitoring.get("key_metrics", []):
                key_metrics.append({
                    "metric": m,
                    "current": "",
                    "watch_for": monitoring.get("success_indicator", ""),
                    "frequency": monitoring.get("check_frequency", "weekly"),
                })

            primary_action = resolution.get("primary_action", {})
            secondary_actions = [
                {"what": a.get("title", ""), "why": a.get("description", ""), "when": ""}
                for a in resolution.get("secondary_actions", [])
            ]

            return {
                "title": story.get("title", ""),
                "subtitle": story.get("subtitle", ""),
                "opening_hook": opening.get("hook", ""),
                "takeaway": opening.get("takeaway", ""),
                "why_matters": opening.get("why_matters", ""),
                "findings": findings,
                "complications": complications,
                "primary_action": {
                    "what": primary_action.get("title", ""),
                    "why": primary_action.get("rationale", ""),
                    "expected_result": primary_action.get("impact", ""),
                    "when": "",
                    "effort": primary_action.get("effort", ""),
                },
                "secondary_actions": secondary_actions,
                "story_conclusion": resolution.get("story_conclusion", ""),
                "key_metrics_to_watch": key_metrics,
                "overall_health": metadata.get("overall_health", "Stable"),
                "story_theme": metadata.get("theme", "mixed"),
                "top_priority": metadata.get("top_priority", ""),
                "reading_time": metadata.get("reading_time_minutes", 3),
            }

        else:
            # Old format
            headline_block = story.get("headline", {})
            action_plan = story.get("action_plan", {})
            primary_raw = action_plan.get("primary_action", {})
            metadata = story.get("metadata", {})

            findings = []
            for f in story.get("findings", []):
                findings.append({
                    "headline": f.get("headline", f.get("title", "")),
                    "narrative": f.get("story", f.get("narrative", "")),
                    "the_number": f.get("the_number", ""),
                    "what_it_means": f.get("what_it_means", ""),
                    "importance": 5,
                    "type": "discovery",
                })

            complications = []
            for w in story.get("warnings", story.get("complications", [])):
                complications.append({
                    "headline": w.get("headline", w.get("title", "")),
                    "narrative": w.get("story", w.get("narrative", "")),
                    "urgency": w.get("urgency", "medium"),
                    "urgency_label": w.get("urgency_label", "Monitor"),
                    "action": w.get("what_to_do", w.get("mitigation", "")),
                    "metric": "",
                })

            watch_raw = story.get("what_to_watch", [])
            key_metrics = [
                {
                    "metric": w.get("metric", ""),
                    "current": w.get("right_now", ""),
                    "watch_for": w.get("watch_for", ""),
                    "frequency": w.get("how_often", "weekly"),
                }
                for w in watch_raw
            ]

            return {
                "title": headline_block.get("title", story.get("title", "")),
                "subtitle": headline_block.get("subtitle", story.get("subtitle", "")),
                "opening_hook": story.get("opening_story", ""),
                "takeaway": story.get("what_this_means", ""),
                "why_matters": headline_block.get("verdict", ""),
                "findings": findings,
                "complications": complications,
                "primary_action": {
                    "what": primary_raw.get("what", ""),
                    "why": primary_raw.get("why", ""),
                    "expected_result": primary_raw.get("expected_result", ""),
                    "when": primary_raw.get("when", ""),
                    "effort": primary_raw.get("effort", ""),
                },
                "secondary_actions": [
                    {"what": a.get("what", ""), "why": a.get("why", ""), "when": a.get("when", "")}
                    for a in action_plan.get("supporting_actions", [])
                ],
                "story_conclusion": story.get("closing", ""),
                "key_metrics_to_watch": key_metrics,
                "overall_health": metadata.get("overall_health", "Stable"),
                "story_theme": metadata.get("story_theme", metadata.get("theme", "mixed")),
                "top_priority": metadata.get("top_priority", ""),
                "reading_time": metadata.get("reading_time_minutes", 3),
            }

    def _gather_report_data(self, dataset: Dict, story: Optional[Dict]) -> Dict:
        """Gather and normalize all data for the report."""
        insights = dataset.get("insights", {})
        dq = insights.get("data_quality", dataset.get("data_quality", {}))
        norm = self._normalize_story(story)

        # Build a plain-English key_findings list from raw insights if story findings are empty
        raw_key_findings = self._get_safe_list(insights, "key_findings")
        if not norm["findings"] and raw_key_findings:
            norm["findings"] = [
                {
                    "headline": kf.get("title", kf.get("type", f"Finding {i+1}")),
                    "narrative": kf.get("plain_english", kf.get("description", "")),
                    "the_number": kf.get("impact", ""),
                    "what_it_means": "",
                    "importance": 7 if kf.get("severity") == "high" else 5,
                    "type": kf.get("category", "discovery"),
                }
                for i, kf in enumerate(raw_key_findings[:10])
            ]

        recommendations = self._get_safe_list(insights, "recommendations")
        if not norm["secondary_actions"] and recommendations:
            norm["secondary_actions"] = [
                {"what": r.get("action", r.get("title", "")), "why": r.get("rationale", r.get("reason", "")), "when": r.get("timeline", "")}
                for r in recommendations[:5]
            ]

        return {
            # Dataset meta
            "dataset_name": dataset.get("name", "Untitled Dataset"),
            "domain": (dataset.get("domain") or "General").capitalize(),
            "generated_date": datetime.now().strftime("%B %d, %Y"),
            "generated_time": datetime.now().strftime("%H:%M UTC"),
            "total_records": dataset.get("row_count", dataset.get("total_rows", 0)),
            "total_columns": dataset.get("column_count", dataset.get("total_columns", 0)),
            "time_period": self._extract_time_period(dataset),
            # Story narrative
            "story_title": norm["title"] or dataset.get("name", "Analysis Report"),
            "story_subtitle": norm["subtitle"],
            "opening_hook": norm["opening_hook"] or insights.get("executive_summary", ""),
            "takeaway": norm["takeaway"],
            "why_matters": norm["why_matters"],
            "overall_health": norm["overall_health"],
            "story_theme": norm["story_theme"],
            "top_priority": norm["top_priority"],
            "reading_time": norm["reading_time"],
            # Findings & risks
            "findings": norm["findings"],
            "complications": norm["complications"],
            # Action plan
            "primary_action": norm["primary_action"],
            "secondary_actions": norm["secondary_actions"],
            "story_conclusion": norm["story_conclusion"],
            "key_metrics_to_watch": norm["key_metrics_to_watch"],
            # Raw statistical analysis
            "correlations": self._get_safe_list(insights, "correlations"),
            "trends": self._get_safe_list(insights, "trends"),
            "anomalies": self._get_safe_list(insights, "anomalies"),
            "distributions": self._get_safe_list(insights, "distributions"),
            "segments": self._get_safe_list(insights, "segments"),
            "drivers": self._get_safe_list(insights, "driver_analysis"),
            "data_quality": dq,
            "column_stats": self._get_safe_list(insights, "column_statistics"),
            # Counts for cover page
            "count_findings": len(norm["findings"]),
            "count_correlations": len(self._get_safe_list(insights, "correlations")),
            "count_anomalies": len(self._get_safe_list(insights, "anomalies")),
            "count_trends": len(self._get_safe_list(insights, "trends")),
            "health_score": dq.get("health_score", 0),
        }

    # ──────────────────────────────────────────────────────────────────
    #  HELPERS
    # ──────────────────────────────────────────────────────────────────

    def _get_safe_list(self, data: Dict, key: str) -> List:
        v = data.get(key, [])
        return v if isinstance(v, list) else []

    def _extract_time_period(self, dataset: Dict) -> str:
        ti = dataset.get("time_info", {})
        if ti:
            s, e = ti.get("start", ""), ti.get("end", "")
            if s and e:
                return f"{s} – {e}"
        return "N/A"

    def _escape(self, text) -> str:
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
            .replace("\n", "<br>")
        )

    def _bold_to_html(self, text: str) -> str:
        """Convert **bold** markdown to <strong> tags, then escape rest."""
        if not text:
            return ""
        parts = text.split("**")
        result = []
        for i, part in enumerate(parts):
            escaped = (
                part.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    .replace("\n", "<br>")
            )
            if i % 2 == 1:
                result.append(f"<strong>{escaped}</strong>")
            else:
                result.append(escaped)
        return "".join(result)

    def _health_class(self, health: str) -> str:
        h = (health or "").lower()
        if "strong" in h:
            return "strong"
        if "critical" in h:
            return "critical"
        if "attention" in h or "concern" in h:
            return "warning"
        return "stable"

    def _urgency_class(self, urgency: str) -> str:
        u = (urgency or "").lower()
        if "today" in u or "critical" in u:
            return "critical"
        if "week" in u or "high" in u:
            return "high"
        return "medium"

    def _corr_strength(self, val: float) -> Tuple[str, str]:
        av = abs(val)
        if av >= 0.8:
            return "Very Strong", "strong"
        if av >= 0.6:
            return "Strong", "strong"
        if av >= 0.4:
            return "Moderate", "moderate"
        if av >= 0.2:
            return "Weak", "weak"
        return "Negligible", "weak"

    # ──────────────────────────────────────────────────────────────────
    #  HTML SECTION BUILDERS
    # ──────────────────────────────────────────────────────────────────

    def _build_cover_stats(self, data: Dict) -> str:
        health = data["health_score"]
        health_color = "#22c55e" if health >= 80 else "#f59e0b" if health >= 60 else "#ef4444"
        return f"""
        <div class="cover-stats">
            <div class="cover-stat">
                <div class="cover-stat-value">{int(data['total_records']):,}</div>
                <div class="cover-stat-label">Records Analyzed</div>
            </div>
            <div class="cover-stat">
                <div class="cover-stat-value">{data['total_columns']}</div>
                <div class="cover-stat-label">Variables</div>
            </div>
            <div class="cover-stat">
                <div class="cover-stat-value">{data['count_findings']}</div>
                <div class="cover-stat-label">Key Findings</div>
            </div>
            <div class="cover-stat">
                <div class="cover-stat-value" style="color:{health_color}">{health}%</div>
                <div class="cover-stat-label">Data Health</div>
            </div>
        </div>
        """

    def _build_findings(self, findings: List[Dict]) -> str:
        if not findings:
            return '<p class="empty">No narrative findings available for this dataset.</p>'

        parts = []
        for i, f in enumerate(findings):
            headline = self._escape(f.get("headline", f"Finding {i+1}"))
            narrative = self._bold_to_html(f.get("narrative", ""))
            the_number = self._escape(f.get("the_number", ""))
            what_it_means = self._escape(f.get("what_it_means", ""))
            importance = int(f.get("importance", 5))
            imp_class = "high" if importance >= 8 else "medium" if importance >= 6 else "normal"

            parts.append(f"""
            <div class="finding-card finding-{imp_class}">
                <div class="finding-meta">
                    <span class="finding-num">Finding {i+1:02d}</span>
                    {f'<span class="finding-importance imp-{imp_class}">{"High Priority" if imp_class == "high" else "Notable" if imp_class == "medium" else ""}</span>' if imp_class != "normal" else ""}
                </div>
                <h3 class="finding-headline">{headline}</h3>
                <p class="finding-narrative">{narrative}</p>
                {f'<div class="finding-number-box"><span class="fn-label">Key Number</span><span class="fn-value">{the_number}</span></div>' if the_number else ""}
                {f'<p class="finding-so-what"><em>{what_it_means}</em></p>' if what_it_means else ""}
            </div>
            """)
        return "\n".join(parts)

    def _build_complications(self, complications: List[Dict]) -> str:
        if not complications:
            return '<p class="empty">No risks or warnings identified.</p>'

        parts = []
        for c in complications:
            headline = self._escape(c.get("headline", "Risk identified"))
            narrative = self._bold_to_html(c.get("narrative", ""))
            urgency = c.get("urgency_label", c.get("urgency", "Monitor"))
            action = self._escape(c.get("action", ""))
            urg_class = self._urgency_class(urgency)

            parts.append(f"""
            <div class="risk-card risk-{urg_class}">
                <div class="risk-header">
                    <span class="risk-badge badge-{urg_class}">{urgency}</span>
                    <h3 class="risk-headline">{headline}</h3>
                </div>
                <p class="risk-narrative">{narrative}</p>
                {f'<div class="risk-action"><span class="ra-label">&#8594; Recommended Action</span><span class="ra-text">{action}</span></div>' if action else ""}
            </div>
            """)
        return "\n".join(parts)

    def _build_action_plan(self, data: Dict) -> str:
        primary = data.get("primary_action", {})
        secondary = data.get("secondary_actions", [])
        conclusion = data.get("story_conclusion", "")

        primary_html = ""
        if primary and primary.get("what"):
            what = self._escape(primary.get("what", ""))
            why = self._bold_to_html(primary.get("why", ""))
            result = self._escape(primary.get("expected_result", ""))
            when = self._escape(primary.get("when", ""))
            effort = self._escape(primary.get("effort", ""))
            primary_html = f"""
            <div class="action-primary">
                <div class="action-badge">Primary Action</div>
                <h3 class="action-title">{what}</h3>
                {f'<p class="action-why"><strong>Why:</strong> {why}</p>' if why else ""}
                {f'<p class="action-result"><strong>Expected result:</strong> {result}</p>' if result else ""}
                <div class="action-tags">
                    {f'<span class="atag">⏱ {when}</span>' if when else ""}
                    {f'<span class="atag">{effort}</span>' if effort else ""}
                </div>
            </div>
            """

        secondary_html = ""
        if secondary:
            items = []
            for a in secondary[:6]:
                what = self._escape(a.get("what", ""))
                why = self._escape(a.get("why", ""))
                when = self._escape(a.get("when", ""))
                if what:
                    items.append(f"""
                    <li class="sec-action">
                        <span class="sec-what">{what}</span>
                        {f'<span class="sec-why">{why}</span>' if why else ""}
                        {f'<span class="sec-when">({when})</span>' if when else ""}
                    </li>""")
            if items:
                secondary_html = f'<ul class="secondary-list">{"".join(items)}</ul>'

        conclusion_html = f'<div class="conclusion-box">{self._bold_to_html(conclusion)}</div>' if conclusion else ""

        if not primary_html and not secondary_html and not conclusion_html:
            return '<p class="empty">No action plan available.</p>'

        return f"""
        {primary_html}
        {f'<h4 class="secondary-heading">Supporting Actions</h4>{secondary_html}' if secondary_html else ""}
        {f'<h4 class="secondary-heading">Looking Ahead</h4>{conclusion_html}' if conclusion_html else ""}
        """

    def _build_watch_metrics(self, metrics: List[Dict]) -> str:
        if not metrics:
            return '<p class="empty">No monitoring metrics specified.</p>'
        rows = []
        for m in metrics:
            rows.append(f"""
            <tr>
                <td>{self._escape(m.get("metric", ""))}</td>
                <td class="num">{self._escape(m.get("current", "—"))}</td>
                <td>{self._escape(m.get("watch_for", ""))}</td>
                <td><span class="freq-badge">{self._escape(m.get("frequency", "weekly"))}</span></td>
            </tr>""")
        return f"""
        <table class="data-table">
            <thead><tr><th>Metric</th><th>Current Value</th><th>Act When</th><th>Frequency</th></tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>"""

    def _build_correlations(self, correlations: List[Dict]) -> str:
        if not correlations:
            return '<p class="empty">No correlations detected.</p>'
        rows = []
        for c in correlations[:20]:
            col1 = self._escape(c.get("column1", c.get("x", "—")))
            col2 = self._escape(c.get("column2", c.get("y", "—")))
            val = c.get("value", c.get("correlation", 0))
            try:
                val_f = float(val)
                val_str = f"{val_f:+.3f}"
            except (TypeError, ValueError):
                val_str = str(val)
                val_f = 0.0
            direction = "↑ Positive" if val_f > 0 else "↓ Negative"
            strength, sc = self._corr_strength(val_f)
            plain = self._escape(c.get("plain_english", ""))
            rows.append(f"""
            <tr>
                <td><strong>{col1}</strong></td>
                <td><strong>{col2}</strong></td>
                <td class="num">{val_str}</td>
                <td><span class="badge badge-{sc}">{strength}</span></td>
                <td>{direction}</td>
                <td style="font-size:8pt;color:#555">{plain[:90]+"…" if len(plain)>90 else plain}</td>
            </tr>""")
        return f"""
        <table class="data-table">
            <thead><tr><th>Variable A</th><th>Variable B</th><th>r</th><th>Strength</th><th>Direction</th><th>Interpretation</th></tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>"""

    def _build_trends(self, trends: List[Dict]) -> str:
        if not trends:
            return '<p class="empty">No trends detected.</p>'
        rows = []
        for t in trends[:15]:
            col = self._escape(t.get("column", t.get("metric", "—")))
            direction = t.get("direction", "unknown")
            dir_icon = "↑" if direction == "increasing" else "↓" if direction == "decreasing" else "→"
            dir_class = "up" if direction == "increasing" else "down" if direction == "decreasing" else "flat"
            rate = t.get("rate", t.get("change_rate", ""))
            try:
                rate_str = f"{float(rate):.2f}%" if rate != "" and rate is not None else "—"
            except (TypeError, ValueError):
                rate_str = str(rate) if rate else "—"
            sig = "Yes" if t.get("is_significant") else "No"
            plain = self._escape(t.get("plain_english", ""))
            rows.append(f"""
            <tr>
                <td><strong>{col}</strong></td>
                <td><span class="dir-{dir_class}">{dir_icon} {direction.capitalize()}</span></td>
                <td class="num">{rate_str}</td>
                <td>{sig}</td>
                <td style="font-size:8pt;color:#555">{plain[:80]+"…" if len(plain)>80 else plain}</td>
            </tr>""")
        return f"""
        <table class="data-table">
            <thead><tr><th>Metric</th><th>Direction</th><th>Rate</th><th>Significant</th><th>Plain English</th></tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>"""

    def _build_anomalies(self, anomalies: List[Dict]) -> str:
        if not anomalies:
            return '<p class="empty">No anomalies detected.</p>'
        rows = []
        for a in anomalies[:15]:
            col = self._escape(a.get("column", a.get("metric", "—")))
            count = a.get("count", "—")
            pct = a.get("percentage", "")
            pct_str = f"{float(pct):.1f}%" if pct not in ("", None) else "—"
            sev = a.get("severity", "medium")
            plain = self._escape(a.get("plain_english", ""))
            causes = self._escape(", ".join(a.get("possible_causes", [])[:2]))
            rows.append(f"""
            <tr>
                <td><strong>{col}</strong></td>
                <td class="num">{count}</td>
                <td class="num">{pct_str}</td>
                <td><span class="badge badge-{sev}">{sev.upper()}</span></td>
                <td style="font-size:8pt;color:#555">{plain[:80]+"…" if len(plain)>80 else plain}</td>
                <td style="font-size:8pt;color:#555">{causes}</td>
            </tr>""")
        return f"""
        <table class="data-table">
            <thead><tr><th>Column</th><th>Outliers</th><th>% Affected</th><th>Severity</th><th>Insight</th><th>Possible Causes</th></tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>"""

    def _build_data_quality(self, dq: Dict) -> str:
        if not dq:
            return '<p class="empty">No data quality metrics available.</p>'

        health = int(dq.get("health_score", 0))
        completeness = int(dq.get("completeness", 0))
        uniqueness = int(dq.get("uniqueness", 0))
        consistency = int(dq.get("consistency", 0))

        def bar(pct, color="#3b82f6"):
            return f'<div class="bar-bg"><div class="bar-fill" style="width:{min(pct,100)}%;background:{color}"></div></div>'

        health_color = "#22c55e" if health >= 80 else "#f59e0b" if health >= 60 else "#ef4444"
        flags = dq.get("data_quality_flags", dq.get("flags", dq.get("issues", [])))
        flags_html = ""
        if flags:
            items = []
            for flag in flags[:8]:
                if isinstance(flag, dict):
                    field = self._escape(flag.get("affected_field", flag.get("field", "")))
                    issue = self._escape(flag.get("issue", flag.get("description", "")))
                    impact = self._escape(flag.get("impact", ""))
                    items.append(f'<li><strong>{field}:</strong> {issue}{f" — {impact}" if impact else ""}</li>')
                elif isinstance(flag, str):
                    items.append(f"<li>{self._escape(flag)}</li>")
            flags_html = f'<ul class="flags-list">{"".join(items)}</ul>' if items else ""

        return f"""
        <div class="dq-grid">
            <div class="dq-card main">
                <div class="dq-score" style="color:{health_color}">{health}%</div>
                <div class="dq-label">Overall Health</div>
                {bar(health, health_color)}
            </div>
            <div class="dq-card">
                <div class="dq-score">{completeness}%</div>
                <div class="dq-label">Completeness</div>
                {bar(completeness)}
            </div>
            <div class="dq-card">
                <div class="dq-score">{uniqueness}%</div>
                <div class="dq-label">Uniqueness</div>
                {bar(uniqueness)}
            </div>
            <div class="dq-card">
                <div class="dq-score">{consistency}%</div>
                <div class="dq-label">Consistency</div>
                {bar(consistency)}
            </div>
        </div>
        {f'<div class="flags-section"><h4>Quality Flags</h4>{flags_html}</div>' if flags_html else ""}
        """

    def _build_column_stats(self, stats: List[Dict]) -> str:
        if not stats:
            return '<p class="empty">No column statistics available.</p>'
        rows = []
        for s in stats[:25]:
            col = self._escape(s.get("column", "—"))
            dtype = self._escape(s.get("dtype", s.get("type", "—")))
            count = s.get("count", s.get("non_null", "—"))
            mean = s.get("mean", "")
            std = s.get("std", s.get("std_dev", ""))
            mn = s.get("min", "")
            mx = s.get("max", "")

            def fmt(v):
                try:
                    return f"{float(v):.2f}"
                except (TypeError, ValueError):
                    return str(v) if v not in ("", None) else "—"

            rows.append(f"""
            <tr>
                <td><strong>{col}</strong></td>
                <td><span class="dtype">{dtype}</span></td>
                <td class="num">{f"{count:,}" if isinstance(count, int) else str(count)}</td>
                <td class="num">{fmt(mean)}</td>
                <td class="num">{fmt(std)}</td>
                <td class="num">{fmt(mn)}</td>
                <td class="num">{fmt(mx)}</td>
            </tr>""")
        return f"""
        <table class="data-table">
            <thead><tr><th>Column</th><th>Type</th><th>Count</th><th>Mean</th><th>Std Dev</th><th>Min</th><th>Max</th></tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>"""

    # ──────────────────────────────────────────────────────────────────
    #  RENDER
    # ──────────────────────────────────────────────────────────────────

    def _render_template(self, data: Dict) -> str:
        template = self.template_path.read_text(encoding="utf-8")

        replacements = {
            "{{DATASET_NAME}}": self._escape(data["dataset_name"]),
            "{{DOMAIN}}": self._escape(data["domain"]),
            "{{GENERATED_DATE}}": self._escape(data["generated_date"]),
            "{{GENERATED_TIME}}": self._escape(data["generated_time"]),
            "{{TOTAL_RECORDS}}": f"{int(data['total_records']):,}",
            "{{TOTAL_COLUMNS}}": str(data["total_columns"]),
            "{{TIME_PERIOD}}": self._escape(data["time_period"]),
            "{{STORY_TITLE}}": self._escape(data["story_title"]),
            "{{STORY_SUBTITLE}}": self._escape(data["story_subtitle"]),
            "{{OPENING_HOOK}}": self._bold_to_html(data["opening_hook"]),
            "{{TAKEAWAY}}": self._bold_to_html(data["takeaway"]),
            "{{WHY_MATTERS}}": self._bold_to_html(data["why_matters"]),
            "{{OVERALL_HEALTH}}": self._escape(data["overall_health"]),
            "{{HEALTH_CLASS}}": self._health_class(data["overall_health"]),
            "{{STORY_THEME}}": self._escape(data["story_theme"].replace("_", " ").capitalize()),
            "{{TOP_PRIORITY}}": self._escape(data["top_priority"]),
            "{{HEALTH_SCORE}}": str(data["health_score"]),
            "{{COUNT_FINDINGS}}": str(data["count_findings"]),
            "{{COUNT_CORRELATIONS}}": str(data["count_correlations"]),
            "{{COUNT_ANOMALIES}}": str(data["count_anomalies"]),
            "{{COUNT_TRENDS}}": str(data["count_trends"]),
            "{{COVER_STATS}}": self._build_cover_stats(data),
            "{{FINDINGS_SECTION}}": self._build_findings(data["findings"]),
            "{{COMPLICATIONS_SECTION}}": self._build_complications(data["complications"]),
            "{{ACTION_PLAN_SECTION}}": self._build_action_plan(data),
            "{{WATCH_SECTION}}": self._build_watch_metrics(data["key_metrics_to_watch"]),
            "{{CORRELATIONS_TABLE}}": self._build_correlations(data["correlations"]),
            "{{TRENDS_TABLE}}": self._build_trends(data["trends"]),
            "{{ANOMALIES_TABLE}}": self._build_anomalies(data["anomalies"]),
            "{{DATA_QUALITY_SECTION}}": self._build_data_quality(data["data_quality"]),
            "{{COLUMN_STATS_TABLE}}": self._build_column_stats(data["column_stats"]),
        }

        result = template
        for k, v in replacements.items():
            result = result.replace(k, v if v is not None else "")
        return result

    # ──────────────────────────────────────────────────────────────────
    #  PDF GENERATION
    # ──────────────────────────────────────────────────────────────────

    def _generate_pdf(self, html_content: str) -> bytes:
        try:
            from weasyprint import HTML
            return HTML(string=html_content).write_pdf()
        except ImportError:
            logger.error("WeasyPrint not installed. Run: pip install weasyprint")
            raise RuntimeError("PDF generation requires weasyprint.")
        except Exception as e:
            logger.error(f"PDF generation error: {e}")
            raise


async def generate_pdf_report(
    dataset_id: str, include_charts: bool = True, preview: bool = False
) -> bytes:
    generator = ReportGenerator()
    return await generator.generate(
        dataset_id=dataset_id, include_charts=include_charts, preview=preview
    )
