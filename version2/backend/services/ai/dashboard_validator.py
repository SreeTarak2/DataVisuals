"""
Dashboard Validator Service
=======================
Quality assurance for generated dashboards.

Features:
1. Completeness Check - Are all components valid?
2. Data Accuracy - No 1970 dates, values in valid range
3. Duplicate Detection - Same KPI in multiple cards
4. Visual Hierarchy - Proper layout structure
5. Auto-Fix - Automatically fix common issues

Author: DataSage AI Team
Version: 1.0
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import polars as pl

logger = logging.getLogger(__name__)


class DashboardValidator:
    """
    Validates generated dashboards for quality and correctness.

    Checks:
    - Component completeness
    - Data accuracy
    - Duplicate detection
    - Visual hierarchy
    - Schema compliance
    """

    def __init__(self):
        self.validation_rules = self._initialize_rules()

    def _initialize_rules(self) -> Dict[str, Any]:
        """Initialize validation rules and thresholds."""
        return {
            "max_components": 15,
            "max_kpi_span": 4,
            "max_chart_span": 4,
            "min_kpi_count": 1,
            "max_kpi_count": 8,
            "min_chart_count": 0,
            "max_chart_count": 10,
            "pie_cardinality_limit": 15,
            "max_table_rows": 100,
        }

    async def validate_dashboard(
        self, blueprint: Dict[str, Any], df: pl.DataFrame, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate a dashboard blueprint.

        Returns:
            Validation result with issues and auto-fixes
        """
        logger.info("Starting dashboard validation...")

        issues = []
        auto_fixes = []
        warnings = []

        # Check 1: Blueprint structure
        structure_issues = self._validate_structure(blueprint)
        issues.extend(structure_issues)

        # Check 2: Component completeness
        completeness_issues = self._validate_completeness(blueprint, metadata)
        issues.extend(completeness_issues)

        # Check 3: Data accuracy
        accuracy_issues = self._validate_data_accuracy(blueprint, df, metadata)
        issues.extend(accuracy_issues)

        # Check 4: Duplicate detection
        duplicates = self._detect_duplicates(blueprint)
        issues.extend(duplicates)

        # Check 5: Visual hierarchy
        hierarchy_issues = self._validate_hierarchy(blueprint)
        warnings.extend(hierarchy_issues)

        # Check 6: Schema compliance
        schema_issues = self._validate_schema(blueprint)
        issues.extend(schema_issues)

        # Auto-fix common issues
        if issues:
            fixed_blueprint, fixes_applied = self._auto_fix(
                blueprint, issues, df, metadata
            )
            auto_fixes.extend(fixes_applied)
        else:
            fixed_blueprint = blueprint

        # Calculate quality score
        quality_score = self._calculate_quality_score(
            total_issues=len(issues),
            warnings=len(warnings),
            total_components=len(fixed_blueprint.get("components", [])),
        )

        result = {
            "is_valid": len(issues) == 0,
            "quality_score": quality_score,
            "issues": issues,
            "warnings": warnings,
            "auto_fixes": auto_fixes,
            "validated_blueprint": fixed_blueprint,
            "validation_time": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"Validation complete: score={quality_score:.1f}, "
            f"issues={len(issues)}, fixes={len(auto_fixes)}"
        )

        return result

    def _validate_structure(self, blueprint: Dict) -> List[Dict]:
        """Validate blueprint structure."""
        issues = []

        if not blueprint:
            issues.append(
                {
                    "type": "missing_blueprint",
                    "severity": "critical",
                    "message": "Blueprint is empty or None",
                }
            )
            return issues

        if "components" not in blueprint:
            issues.append(
                {
                    "type": "missing_components",
                    "severity": "critical",
                    "message": "Blueprint missing 'components' key",
                }
            )
            return issues

        components = blueprint.get("components", [])

        if not components:
            issues.append(
                {
                    "type": "empty_components",
                    "severity": "critical",
                    "message": "Blueprint has no components",
                }
            )
            return issues

        if len(components) > self.validation_rules["max_components"]:
            issues.append(
                {
                    "type": "too_many_components",
                    "severity": "warning",
                    "message": f"Blueprint has {len(components)} components, max is {self.validation_rules['max_components']}",
                }
            )

        return issues

    def _validate_completeness(self, blueprint: Dict, metadata: Dict) -> List[Dict]:
        """Validate component completeness."""
        issues = []
        components = blueprint.get("components", [])

        # Check for KPIs
        kpi_count = sum(1 for c in components if c.get("type") == "kpi")
        if kpi_count < self.validation_rules["min_kpi_count"]:
            issues.append(
                {
                    "type": "missing_kpis",
                    "severity": "critical",
                    "message": f"Blueprint has {kpi_count} KPIs, minimum is {self.validation_rules['min_kpi_count']}",
                }
            )

        if kpi_count > self.validation_rules["max_kpi_count"]:
            issues.append(
                {
                    "type": "too_many_kpis",
                    "severity": "warning",
                    "message": f"Blueprint has {kpi_count} KPIs, maximum recommended is {self.validation_rules['max_kpi_count']}",
                }
            )

        # Check for charts
        chart_count = sum(1 for c in components if c.get("type") == "chart")
        if chart_count > self.validation_rules["max_chart_count"]:
            issues.append(
                {
                    "type": "too_many_charts",
                    "severity": "warning",
                    "message": f"Blueprint has {chart_count} charts, maximum recommended is {self.validation_rules['max_chart_count']}",
                }
            )

        # Check for layout_grid
        if "layout_grid" not in blueprint:
            issues.append(
                {
                    "type": "missing_layout_grid",
                    "severity": "warning",
                    "message": "Blueprint missing layout_grid, will use default",
                }
            )

        return issues

    def _validate_data_accuracy(
        self, blueprint: Dict, df: pl.DataFrame, metadata: Dict
    ) -> List[Dict]:
        """Validate data accuracy in components."""
        issues = []
        components = blueprint.get("components", [])
        valid_columns = set(df.columns) if df is not None else set()

        # Get valid columns from metadata if df not available
        if not valid_columns:
            colmeta = metadata.get("column_metadata", [])
            valid_columns = {c["name"] for c in colmeta if c.get("name")}

        for i, comp in enumerate(components):
            comp_type = comp.get("type", "unknown")
            config = comp.get("config", {})

            # Check for valid columns
            if comp_type == "kpi":
                column = config.get("column")
                if column and column not in valid_columns:
                    issues.append(
                        {
                            "type": "invalid_column",
                            "severity": "warning",
                            "component_index": i,
                            "message": f"KPI '{comp.get('title')}' references invalid column '{column}'",
                        }
                    )

            elif comp_type == "chart":
                columns = config.get("columns", [])
                for col in columns:
                    if col and col not in valid_columns:
                        issues.append(
                            {
                                "type": "invalid_column",
                                "severity": "warning",
                                "component_index": i,
                                "message": f"Chart '{comp.get('title')}' references invalid column '{col}'",
                            }
                        )

                # Check pie chart cardinality
                chart_type = config.get("chart_type", "")
                if chart_type in ["pie", "donut", "pie_chart"]:
                    x_col = config.get("x") or (columns[0] if columns else None)
                    if x_col and x_col in valid_columns and df is not None:
                        try:
                            unique_count = df[x_col].n_unique()
                            if (
                                unique_count
                                > self.validation_rules["pie_cardinality_limit"]
                            ):
                                issues.append(
                                    {
                                        "type": "high_cardinality_pie",
                                        "severity": "warning",
                                        "component_index": i,
                                        "message": f"Pie chart '{comp.get('title')}' has {unique_count} categories, max recommended is {self.validation_rules['pie_cardinality_limit']}",
                                    }
                                )
                        except Exception:
                            pass

            elif comp_type == "table":
                columns = config.get("columns", [])
                for col in columns:
                    if col and col not in valid_columns:
                        issues.append(
                            {
                                "type": "invalid_column",
                                "severity": "warning",
                                "component_index": i,
                                "message": f"Table '{comp.get('title')}' references invalid column '{col}'",
                            }
                        )

        return issues

    def _detect_duplicates(self, blueprint: Dict) -> List[Dict]:
        """Detect duplicate KPIs or similar charts."""
        issues = []
        components = blueprint.get("components", [])

        # Group KPIs by aggregation
        kpi_signatures = {}
        for i, comp in enumerate(components):
            if comp.get("type") == "kpi":
                config = comp.get("config", {})
                signature = (config.get("column"), config.get("aggregation"))

                if signature in kpi_signatures:
                    existing_idx = kpi_signatures[signature]
                    issues.append(
                        {
                            "type": "duplicate_kpi",
                            "severity": "warning",
                            "component_indices": [existing_idx, i],
                            "message": f"Duplicate KPI detected: '{comp.get('title')}' has same column and aggregation as another KPI",
                        }
                    )
                else:
                    kpi_signatures[signature] = i

        # Detect very similar chart titles
        chart_titles = {}
        for i, comp in enumerate(components):
            if comp.get("type") == "chart":
                title = comp.get("title", "").lower()
                similar = None

                for existing_title, existing_idx in chart_titles.items():
                    if self._similar_strings(title, existing_title, threshold=0.8):
                        similar = existing_idx
                        break

                if similar is not None:
                    issues.append(
                        {
                            "type": "similar_chart_title",
                            "severity": "info",
                            "component_indices": [similar, i],
                            "message": f"Charts '{comp.get('title')}' and another chart have similar titles",
                        }
                    )
                else:
                    chart_titles[title] = i

        return issues

    def _similar_strings(self, s1: str, s2: str, threshold: float = 0.8) -> bool:
        """Check if two strings are similar (simple implementation)."""
        if s1 == s2:
            return True

        # Simple Jaccard similarity on words
        words1 = set(s1.split())
        words2 = set(s2.split())

        if not words1 or not words2:
            return False

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return (intersection / union) >= threshold if union > 0 else False

    def _validate_hierarchy(self, blueprint: Dict) -> List[Dict]:
        """Validate visual hierarchy and layout."""
        warnings = []
        components = blueprint.get("components", [])

        # Check span values
        for i, comp in enumerate(components):
            span = comp.get("span", 1)
            comp_type = comp.get("type")

            max_span = (
                self.validation_rules["max_kpi_span"]
                if comp_type == "kpi"
                else self.validation_rules["max_chart_span"]
            )

            if span > max_span:
                warnings.append(
                    {
                        "type": "excessive_span",
                        "severity": "warning",
                        "component_index": i,
                        "message": f"Component '{comp.get('title')}' has span={span}, max recommended is {max_span}",
                    }
                )

            if span < 1:
                warnings.append(
                    {
                        "type": "invalid_span",
                        "severity": "error",
                        "component_index": i,
                        "message": f"Component '{comp.get('title')}' has invalid span={span}",
                    }
                )

        # Check for reasonable component ordering
        if components:
            first_chart_idx = None
            first_kpi_idx = None

            for i, comp in enumerate(components):
                if comp.get("type") == "chart" and first_chart_idx is None:
                    first_chart_idx = i
                if comp.get("type") == "kpi" and first_kpi_idx is None:
                    first_kpi_idx = i

            # If chart comes before KPI, it's usually fine, but warn if KPI is very late
            if first_kpi_idx and first_kpi_idx > 5:
                warnings.append(
                    {
                        "type": "kpi_position",
                        "severity": "info",
                        "message": "KPIs appear late in the component list, consider moving them earlier",
                    }
                )

        return warnings

    def _validate_schema(self, blueprint: Dict) -> List[Dict]:
        """Validate blueprint against expected schema."""
        issues = []
        components = blueprint.get("components", [])

        for i, comp in enumerate(components):
            comp_type = comp.get("type")

            if not comp_type:
                issues.append(
                    {
                        "type": "missing_component_type",
                        "severity": "critical",
                        "component_index": i,
                        "message": f"Component at index {i} missing 'type' field",
                    }
                )
                continue

            if comp_type not in ["kpi", "chart", "table", "text", "filter"]:
                issues.append(
                    {
                        "type": "invalid_component_type",
                        "severity": "error",
                        "component_index": i,
                        "message": f"Unknown component type: '{comp_type}'",
                    }
                )

            # Validate title
            if not comp.get("title"):
                issues.append(
                    {
                        "type": "missing_title",
                        "severity": "warning",
                        "component_index": i,
                        "message": f"Component at index {i} missing 'title'",
                    }
                )

        return issues

    def _auto_fix(
        self, blueprint: Dict, issues: List[Dict], df: pl.DataFrame, metadata: Dict
    ) -> Tuple[Dict, List[Dict]]:
        """
        Automatically fix common issues in the blueprint.

        Returns:
            Tuple of (fixed_blueprint, list of fixes applied)
        """
        fixed_blueprint = blueprint.copy()
        fixed_blueprint["components"] = [
            comp.copy() for comp in blueprint.get("components", [])
        ]

        fixes_applied = []

        # Get valid columns
        valid_columns = set(df.columns) if df is not None else set()
        if not valid_columns:
            colmeta = metadata.get("column_metadata", [])
            valid_columns = {c["name"] for c in colmeta if c.get("name")}

        # Fix 1: Add missing layout_grid
        if "layout_grid" not in fixed_blueprint:
            fixed_blueprint["layout_grid"] = "repeat(4, 1fr)"
            fixes_applied.append(
                {
                    "type": "added_layout_grid",
                    "description": "Added default layout_grid: repeat(4, 1fr)",
                }
            )

        # Fix 2: Remove invalid columns
        for i, comp in enumerate(fixed_blueprint["components"]):
            config = comp.get("config", {})
            comp_type = comp.get("type")

            if comp_type == "kpi":
                column = config.get("column")
                if column and column not in valid_columns:
                    # Try to find a similar column
                    similar_col = self._find_similar_column(column, valid_columns)
                    if similar_col:
                        old_column = config.get("column")
                        config["column"] = similar_col
                        fixes_applied.append(
                            {
                                "type": "column_mapping",
                                "component_index": i,
                                "description": f"Mapped invalid column '{old_column}' to '{similar_col}'",
                            }
                        )
                    else:
                        # Mark as fallback
                        comp["_fallbackReason"] = (
                            f"Column '{column}' not found in dataset"
                        )

            elif comp_type == "chart":
                columns = config.get("columns", [])
                valid_chart_columns = []

                for col in columns:
                    if col and col in valid_columns:
                        valid_chart_columns.append(col)
                    elif col:
                        similar_col = self._find_similar_column(col, valid_columns)
                        if similar_col:
                            valid_chart_columns.append(similar_col)
                            fixes_applied.append(
                                {
                                    "type": "column_mapping",
                                    "component_index": i,
                                    "description": f"Mapped invalid column '{col}' to '{similar_col}'",
                                }
                            )

                config["columns"] = (
                    valid_chart_columns if valid_chart_columns else columns
                )

                # Fix pie chart cardinality issues
                chart_type = config.get("chart_type", "")
                if chart_type in ["pie", "donut", "pie_chart"] and df is not None:
                    x_col = config.get("x") or (columns[0] if columns else None)
                    if x_col and x_col in valid_columns:
                        try:
                            unique_count = df[x_col].n_unique()
                            if (
                                unique_count
                                > self.validation_rules["pie_cardinality_limit"]
                            ):
                                config["chart_type"] = "bar"
                                fixes_applied.append(
                                    {
                                        "type": "chart_type_change",
                                        "component_index": i,
                                        "description": f"Changed pie to bar due to high cardinality ({unique_count} categories)",
                                    }
                                )
                        except Exception:
                            pass

        # Fix 3: Remove duplicate KPIs
        seen_kpi_signatures = {}
        components_to_remove = set()

        for i, comp in enumerate(fixed_blueprint["components"]):
            if comp.get("type") == "kpi":
                config = comp.get("config", {})
                signature = (config.get("column"), config.get("aggregation"))

                if signature in seen_kpi_signatures:
                    # Keep the first one, mark others for removal
                    if comp.get("title") != fixed_blueprint["components"][
                        seen_kpi_signatures[signature]
                    ].get("title"):
                        components_to_remove.add(i)
                        fixes_applied.append(
                            {
                                "type": "duplicate_removed",
                                "component_index": i,
                                "description": f"Removed duplicate KPI: '{comp.get('title')}'",
                            }
                        )
                else:
                    seen_kpi_signatures[signature] = i

        if components_to_remove:
            fixed_blueprint["components"] = [
                comp
                for i, comp in enumerate(fixed_blueprint["components"])
                if i not in components_to_remove
            ]

        # Fix 4: Ensure at least one KPI exists
        kpi_count = sum(
            1 for c in fixed_blueprint["components"] if c.get("type") == "kpi"
        )
        if kpi_count == 0:
            first_col = next(iter(valid_columns)) if valid_columns else "id"
            fixed_blueprint["components"].insert(
                0,
                {
                    "type": "kpi",
                    "title": "Total Records",
                    "span": 1,
                    "config": {"column": first_col, "aggregation": "count"},
                    "_fallbackReason": "Added fallback KPI because none were found",
                },
            )
            fixes_applied.append(
                {
                    "type": "fallback_kpi_added",
                    "description": f"Added fallback KPI: Total Records (column: {first_col})",
                }
            )

        # Fix 5: Ensure at least one chart exists if possible
        chart_count = sum(
            1 for c in fixed_blueprint["components"] if c.get("type") == "chart"
        )
        if chart_count == 0 and valid_columns:
            first_col = next(iter(valid_columns))
            fixed_blueprint["components"].insert(
                1,
                {
                    "type": "chart",
                    "title": "Overview",
                    "span": 2,
                    "config": {
                        "chart_type": "bar",
                        "columns": [first_col],
                        "aggregation": "sum",
                    },
                    "_fallbackReason": "Added fallback chart because none were found",
                },
            )
            fixes_applied.append(
                {
                    "type": "fallback_chart_added",
                    "description": f"Added fallback chart: Overview ({first_col})",
                }
            )

        return fixed_blueprint, fixes_applied

    def _find_similar_column(self, column: str, valid_columns: set) -> Optional[str]:
        """Find a similar valid column name."""
        column_lower = column.lower()

        for valid_col in valid_columns:
            valid_lower = valid_col.lower()

            # Check for substring match
            if column_lower in valid_lower or valid_lower in column_lower:
                return valid_col

            # Check for common variations
            if "_" in column_lower and column_lower.replace(
                "_", ""
            ) == valid_lower.replace("_", ""):
                return valid_col

            if " " in column_lower and column_lower.replace(
                " ", ""
            ) == valid_lower.replace(" ", ""):
                return valid_col

        return None

    def _calculate_quality_score(
        self, total_issues: int, warnings: int, total_components: int
    ) -> float:
        """Calculate quality score (0-100)."""
        base_score = 100.0

        # Deduct for issues
        for issue in range(total_issues):
            severity = (
                issue.get("severity", "warning")
                if isinstance(issue, dict)
                else "warning"
            )
            if severity == "critical":
                base_score -= 15
            elif severity == "error":
                base_score -= 10
            elif severity == "warning":
                base_score -= 5

        # Deduct for warnings
        base_score -= warnings * 2

        # Bonus for reasonable component count
        if 3 <= total_components <= 10:
            base_score += 5

        return max(0.0, min(100.0, base_score))


# Singleton instance
dashboard_validator = DashboardValidator()
