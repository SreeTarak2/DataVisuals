"""
KPI Service - Financial Metrics Calculation Engine
==================================================
Calculates business KPIs from dataset columns:
- SaaS metrics (MRR, ARR, Churn, LTV, CAC, NRR, Burn Rate, Runway)
- E-commerce metrics (Revenue, AOV, Conversion Rate, Cart Abandonment)
- Finance metrics (Gross Profit, Net Profit, OPEX, EBITDA, Cash Flow)

Features:
- Auto-detect financial columns from dataset
- Suggest appropriate KPIs based on column types
- Calculate KPIs with period comparisons (MoM, YoY)
- Support custom KPI formulas

Target: Financial Services (Fintechs, Accounting Firms)
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import polars as pl

from db.schemas_kpi import (
    KPICategory,
    AggregationType,
    TrendDirection,
    ComparisonPeriod,
    KPIDefinition,
    KPIFormula,
    KPIThreshold,
    KPIColumnMapping,
    KPICalculationResult,
    KPICalculateResponse,
    ColumnTypeDetection,
    KPISuggestion,
    KPISuggestResponse,
    KPITemplate,
    KPITemplateComponent,
    SavedKPIConfig,
)

from .patterns import COLUMN_PATTERNS
from .evaluator import safe_eval as _safe_arithmetic_eval
from .definitions import ALL_KPIS, SAAS_KPIS, ECOMMERCE_KPIS, FINANCE_KPIS
from .templates import ALL_TEMPLATES

logger = logging.getLogger(__name__)


class KPIService:
    """
    KPI calculation and suggestion service.
    Handles:
    - Auto-detection of financial columns
    - KPI suggestions based on data
    - KPI calculations with period comparisons
    - Template management
    """

    def __init__(self, db=None):
        self.db = db
        self._kpi_configs_collection = None

    @property
    def kpi_configs(self):
        """Lazy load KPI configs collection."""
        if self._kpi_configs_collection is None and self.db:
            self._kpi_configs_collection = self.db["kpi_configs"]
        return self._kpi_configs_collection

    # ---------------------------------------------------
    # Column Detection
    # ---------------------------------------------------
    def detect_column_types(
        self, df: pl.DataFrame, columns: List[str]
    ) -> List[ColumnTypeDetection]:
        """
        Detect financial column types from column names and data.

        Args:
            df: Polars DataFrame
            columns: List of column names to analyze

        Returns:
            List of ColumnTypeDetection with detected types
        """
        detections = []

        for col_name in columns:
            detection = self._detect_single_column(df, col_name)
            if detection:
                detections.append(detection)

        return detections

    def _detect_single_column(
        self, df: pl.DataFrame, col_name: str
    ) -> Optional[ColumnTypeDetection]:
        """Detect type for a single column."""
        col_lower = col_name.lower().replace("_", " ").replace("-", " ")

        best_match = None
        best_confidence = 0.0

        for col_type, patterns in COLUMN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, col_lower, re.IGNORECASE):
                    # Base confidence from pattern match
                    confidence = 0.7

                    # Boost confidence based on data type
                    try:
                        col_dtype = str(df.schema[col_name])

                        # Numeric columns more likely to be metrics
                        if col_type in [
                            "revenue",
                            "cost",
                            "profit",
                            "quantity",
                            "cash",
                        ]:
                            if (
                                "float" in col_dtype.lower()
                                or "int" in col_dtype.lower()
                            ):
                                confidence += 0.2

                        # Date columns
                        if col_type == "date":
                            if (
                                "date" in col_dtype.lower()
                                or "time" in col_dtype.lower()
                            ):
                                confidence += 0.3

                        # ID columns typically have high cardinality
                        if col_type in ["customer_id", "transaction_id"]:
                            unique_ratio = df.select(
                                pl.col(col_name).n_unique()
                            ).item() / len(df)
                            if unique_ratio > 0.5:
                                confidence += 0.2

                    except Exception:
                        pass

                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = col_type

        if best_match:
            # Get sample values
            try:
                samples = df.select(col_name).head(5).to_series().to_list()
            except Exception:
                samples = []

            return ColumnTypeDetection(
                column_name=col_name,
                detected_type=best_match,
                confidence=min(best_confidence, 1.0),
                sample_values=samples[:5],
            )

        return None

    # ---------------------------------------------------
    # KPI Suggestions
    # ---------------------------------------------------
    def suggest_kpis(
        self, df: pl.DataFrame, dataset_id: str, columns: Optional[List[str]] = None
    ) -> KPISuggestResponse:
        """
        Suggest appropriate KPIs based on detected column types.

        Args:
            df: Polars DataFrame
            dataset_id: Dataset ID
            columns: Optional list of columns (defaults to all)

        Returns:
            KPISuggestResponse with suggestions
        """
        if columns is None:
            columns = df.columns

        # Detect column types
        detected_columns = self.detect_column_types(df, columns)
        detected_types = {d.column_name: d.detected_type for d in detected_columns}

        suggestions = []

        # Check which KPIs can be calculated
        has_revenue = any(d.detected_type == "revenue" for d in detected_columns)
        has_cost = any(d.detected_type == "cost" for d in detected_columns)
        has_customer = any(
            d.detected_type in ["customer_id", "customer_count"]
            for d in detected_columns
        )
        has_date = any(d.detected_type == "date" for d in detected_columns)
        has_transaction = any(
            d.detected_type == "transaction_id" for d in detected_columns
        )
        has_churn = any(d.detected_type == "churn" for d in detected_columns)
        has_cash = any(d.detected_type == "cash" for d in detected_columns)

        # Revenue-based KPIs
        if has_revenue:
            revenue_col = next(
                (
                    d.column_name
                    for d in detected_columns
                    if d.detected_type == "revenue"
                ),
                None,
            )

            # MRR / Total Revenue
            suggestions.append(
                KPISuggestion(
                    kpi=SAAS_KPIS["mrr"]
                    if has_date
                    else ECOMMERCE_KPIS["total_revenue"],
                    suggested_mappings={"revenue": revenue_col} if revenue_col else {},
                    confidence=0.9 if has_date else 0.8,
                    reason="Revenue column detected - can calculate recurring or total revenue",
                )
            )

            # ARPU if we have customers
            if has_customer:
                customer_col = next(
                    (
                        d.column_name
                        for d in detected_columns
                        if d.detected_type in ["customer_id", "customer_count"]
                    ),
                    None,
                )
                suggestions.append(
                    KPISuggestion(
                        kpi=SAAS_KPIS["arpu"],
                        suggested_mappings={
                            "revenue": revenue_col,
                            "customer_id": customer_col,
                        },
                        confidence=0.85,
                        reason="Revenue and customer columns detected - can calculate ARPU",
                    )
                )

            # AOV if we have transactions
            if has_transaction:
                transaction_col = next(
                    (
                        d.column_name
                        for d in detected_columns
                        if d.detected_type == "transaction_id"
                    ),
                    None,
                )
                suggestions.append(
                    KPISuggestion(
                        kpi=ECOMMERCE_KPIS["aov"],
                        suggested_mappings={
                            "revenue": revenue_col,
                            "transaction_id": transaction_col,
                        },
                        confidence=0.9,
                        reason="Revenue and transaction columns detected - can calculate AOV",
                    )
                )

        # Cost-based KPIs
        if has_revenue and has_cost:
            revenue_col = next(
                (
                    d.column_name
                    for d in detected_columns
                    if d.detected_type == "revenue"
                ),
                None,
            )
            cost_col = next(
                (d.column_name for d in detected_columns if d.detected_type == "cost"),
                None,
            )

            suggestions.append(
                KPISuggestion(
                    kpi=FINANCE_KPIS["gross_profit"],
                    suggested_mappings={"revenue": revenue_col, "cogs": cost_col},
                    confidence=0.85,
                    reason="Revenue and cost columns detected - can calculate Gross Profit",
                )
            )

            suggestions.append(
                KPISuggestion(
                    kpi=ECOMMERCE_KPIS["gross_margin"],
                    suggested_mappings={"revenue": revenue_col, "cogs": cost_col},
                    confidence=0.85,
                    reason="Revenue and cost columns detected - can calculate Gross Margin",
                )
            )

        # Churn Rate if we have customer + churn indicator
        if has_customer and has_churn:
            customer_col = next(
                (
                    d.column_name
                    for d in detected_columns
                    if d.detected_type in ["customer_id", "customer_count"]
                ),
                None,
            )
            churn_col = next(
                (d.column_name for d in detected_columns if d.detected_type == "churn"),
                None,
            )

            suggestions.append(
                KPISuggestion(
                    kpi=SAAS_KPIS["churn_rate"],
                    suggested_mappings={
                        "churned_customers": churn_col,
                        "total_customers": customer_col,
                    },
                    confidence=0.9,
                    reason="Customer and churn columns detected - can calculate Churn Rate",
                )
            )

        # Burn Rate & Runway if we have revenue, cost, and cash
        if has_revenue and has_cost and has_cash:
            revenue_col = next(
                (
                    d.column_name
                    for d in detected_columns
                    if d.detected_type == "revenue"
                ),
                None,
            )
            cost_col = next(
                (d.column_name for d in detected_columns if d.detected_type == "cost"),
                None,
            )
            cash_col = next(
                (d.column_name for d in detected_columns if d.detected_type == "cash"),
                None,
            )

            suggestions.append(
                KPISuggestion(
                    kpi=SAAS_KPIS["burn_rate"],
                    suggested_mappings={
                        "total_revenue": revenue_col,
                        "total_expenses": cost_col,
                    },
                    confidence=0.8,
                    reason="Revenue and cost columns detected - can calculate Burn Rate",
                )
            )

            suggestions.append(
                KPISuggestion(
                    kpi=SAAS_KPIS["runway"],
                    suggested_mappings={
                        "cash_balance": cash_col,
                        "burn_rate": "calculated",  # From burn_rate KPI
                    },
                    confidence=0.75,
                    reason="Cash and expense columns detected - can calculate Runway",
                )
            )

        # Sort by confidence
        suggestions.sort(key=lambda x: x.confidence, reverse=True)

        # Suggest best matching template
        suggested_template = self._suggest_template(detected_columns)

        return KPISuggestResponse(
            dataset_id=dataset_id,
            detected_columns=detected_columns,
            suggested_kpis=suggestions,
            suggested_template=suggested_template,
        )

    def _suggest_template(
        self, detected_columns: List[ColumnTypeDetection]
    ) -> Optional[KPITemplate]:
        """Suggest the best matching template based on detected columns."""
        detected_types = set(d.detected_type for d in detected_columns)

        template_scores = {}

        for template_id, template in ALL_TEMPLATES.items():
            score = 0

            # Check required columns
            required_found = 0
            for req in template.required_columns:
                if req in detected_types:
                    required_found += 1

            if required_found == len(template.required_columns):
                score += 50  # All required columns found
            elif required_found > 0:
                score += 20 * (required_found / len(template.required_columns))

            # Check optional columns
            for opt in template.optional_columns:
                if opt in detected_types:
                    score += 5

            template_scores[template_id] = score

        # Return highest scoring template
        if template_scores:
            best_template = max(template_scores, key=template_scores.get)
            if template_scores[best_template] >= 30:  # Minimum threshold
                return ALL_TEMPLATES[best_template]

        return None

    # ---------------------------------------------------
    # KPI Calculation
    # ---------------------------------------------------
    def calculate_kpis(
        self,
        df: pl.DataFrame,
        dataset_id: str,
        kpi_ids: List[str],
        column_mappings: List[KPIColumnMapping],
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        comparison_period: Optional[ComparisonPeriod] = None,
        date_column: Optional[str] = None,
    ) -> KPICalculateResponse:
        """
        Calculate specified KPIs from dataset.

        Args:
            df: Polars DataFrame
            dataset_id: Dataset ID
            kpi_ids: List of KPI IDs to calculate
            column_mappings: Column mappings for each KPI
            from_date: Optional start date filter
            to_date: Optional end date filter
            comparison_period: Period for trend comparison
            date_column: Column to use for date filtering

        Returns:
            KPICalculateResponse with calculated values
        """
        results = []
        mapping_dict = {m.kpi_id: m for m in column_mappings}

        # Apply date filter if specified
        filtered_df = df
        previous_df = None

        if date_column and (from_date or to_date):
            try:
                if from_date:
                    filtered_df = filtered_df.filter(pl.col(date_column) >= from_date)
                if to_date:
                    filtered_df = filtered_df.filter(pl.col(date_column) <= to_date)

                # Get previous period for comparison
                if comparison_period and from_date:
                    prev_from, prev_to = self._get_previous_period(
                        from_date, to_date, comparison_period
                    )
                    previous_df = df.filter(
                        (pl.col(date_column) >= prev_from)
                        & (pl.col(date_column) <= prev_to)
                    )
            except Exception as e:
                logger.warning(f"Date filtering failed: {e}")

        # Calculate each KPI
        for kpi_id in kpi_ids:
            kpi_def = ALL_KPIS.get(kpi_id)
            if not kpi_def:
                logger.warning(f"Unknown KPI: {kpi_id}")
                continue

            mapping = mapping_dict.get(kpi_id)
            if not mapping:
                logger.warning(f"No column mapping for KPI: {kpi_id}")
                continue

            try:
                result = self._calculate_single_kpi(
                    filtered_df, previous_df, kpi_def, mapping.column_mappings
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error calculating KPI {kpi_id}: {e}")
                results.append(
                    KPICalculationResult(
                        kpi_id=kpi_id,
                        kpi_name=kpi_def.name,
                        value=0.0,
                        formatted_value="N/A",
                        status="critical",
                    )
                )

        # Count statuses
        healthy = sum(1 for r in results if r.status == "healthy")
        warning = sum(1 for r in results if r.status == "warning")
        critical = sum(1 for r in results if r.status == "critical")

        return KPICalculateResponse(
            dataset_id=dataset_id,
            calculated_at=datetime.utcnow(),
            results=results,
            healthy_count=healthy,
            warning_count=warning,
            critical_count=critical,
        )

    def _calculate_single_kpi(
        self,
        df: pl.DataFrame,
        previous_df: Optional[pl.DataFrame],
        kpi: KPIDefinition,
        column_mappings: Dict[str, str],
    ) -> KPICalculationResult:
        """Calculate a single KPI value."""
        formula = kpi.formula
        value = 0.0
        previous_value = None

        if formula.formula_type == "simple":
            # Simple aggregation
            col = column_mappings.get(formula.column or list(column_mappings.keys())[0])
            if col and col in df.columns:
                value = self._aggregate(df, col, formula.aggregation)
                if previous_df is not None and col in previous_df.columns:
                    previous_value = self._aggregate(
                        previous_df, col, formula.aggregation
                    )

        elif formula.formula_type == "ratio":
            # Ratio calculation
            num_col = column_mappings.get(
                "numerator", column_mappings.get(formula.numerator_column, "")
            )
            den_col = column_mappings.get(
                "denominator", column_mappings.get(formula.denominator_column, "")
            )

            if num_col and den_col:
                numerator = self._aggregate(df, num_col, formula.numerator_aggregation)
                denominator = self._aggregate(
                    df, den_col, formula.denominator_aggregation
                )

                if denominator and denominator != 0:
                    value = numerator / denominator
                    if kpi.format == "percentage":
                        value *= 100

                if previous_df is not None:
                    prev_num = self._aggregate(
                        previous_df, num_col, formula.numerator_aggregation
                    )
                    prev_den = self._aggregate(
                        previous_df, den_col, formula.denominator_aggregation
                    )
                    if prev_den and prev_den != 0:
                        previous_value = prev_num / prev_den
                        if kpi.format == "percentage":
                            previous_value *= 100

        elif formula.formula_type == "custom":
            # Custom expression (simplified evaluation)
            value = self._evaluate_custom_formula(
                df, formula.custom_expression, column_mappings
            )
            if previous_df is not None:
                previous_value = self._evaluate_custom_formula(
                    previous_df, formula.custom_expression, column_mappings
                )

        # Calculate change
        change_value = None
        change_percentage = None
        trend = None

        if previous_value is not None and previous_value != 0:
            change_value = value - previous_value
            change_percentage = (change_value / abs(previous_value)) * 100

            if abs(change_percentage) < 1:
                trend = "stable"
            elif change_value > 0:
                trend = "up"
            else:
                trend = "down"

        # Determine status
        status = self._determine_status(value, kpi)

        # Format value
        formatted_value = self._format_value(value, kpi)

        return KPICalculationResult(
            kpi_id=kpi.id or kpi.name.lower().replace(" ", "_"),
            kpi_name=kpi.name,
            value=value,
            formatted_value=formatted_value,
            previous_value=previous_value,
            change_value=change_value,
            change_percentage=change_percentage,
            trend=trend,
            status=status,
        )

    def _aggregate(
        self, df: pl.DataFrame, column: str, aggregation: Optional[AggregationType]
    ) -> float:
        """Apply aggregation to a column."""
        if column not in df.columns:
            return 0.0

        agg = aggregation or AggregationType.SUM

        try:
            if agg == AggregationType.SUM:
                return df.select(pl.col(column).sum()).item() or 0.0
            elif agg == AggregationType.MEAN:
                return df.select(pl.col(column).mean()).item() or 0.0
            elif agg == AggregationType.COUNT:
                return float(len(df))
            elif agg == AggregationType.NUNIQUE:
                return float(df.select(pl.col(column).n_unique()).item() or 0)
            elif agg == AggregationType.MIN:
                return df.select(pl.col(column).min()).item() or 0.0
            elif agg == AggregationType.MAX:
                return df.select(pl.col(column).max()).item() or 0.0
            elif agg == AggregationType.MEDIAN:
                return df.select(pl.col(column).median()).item() or 0.0
            elif agg == AggregationType.FIRST:
                return df.select(pl.col(column).first()).item() or 0.0
            elif agg == AggregationType.LAST:
                return df.select(pl.col(column).last()).item() or 0.0
        except Exception as e:
            logger.warning(f"Aggregation error for {column}: {e}")
            return 0.0

        return 0.0

    def _evaluate_custom_formula(
        self,
        df: pl.DataFrame,
        expression: Optional[str],
        column_mappings: Dict[str, str],
    ) -> float:
        """Evaluate a custom formula expression using safe AST-based arithmetic."""
        if not expression:
            return 0.0

        context = {}
        for var_name, col_name in column_mappings.items():
            if col_name in df.columns:
                try:
                    context[var_name] = df.select(pl.col(col_name).sum()).item() or 0.0
                except Exception:
                    context[var_name] = 0.0

        try:
            expr = expression
            for var, val in context.items():
                expr = re.sub(rf"\b{var}\b", str(val), expr)

            if re.match(r"^[\d\s\+\-\*\/\(\)\.\,]+$", expr):
                return _safe_arithmetic_eval(expr)
        except Exception as e:
            logger.warning(f"Formula evaluation error: {e}")

        return 0.0

    def _get_previous_period(
        self, from_date: datetime, to_date: Optional[datetime], period: ComparisonPeriod
    ) -> Tuple[datetime, datetime]:
        """Calculate previous period date range."""
        to_date = to_date or datetime.utcnow()
        duration = to_date - from_date

        if period == ComparisonPeriod.DAY:
            delta = timedelta(days=1)
        elif period == ComparisonPeriod.WEEK:
            delta = timedelta(weeks=1)
        elif period == ComparisonPeriod.MONTH:
            try:
                from dateutil.relativedelta import relativedelta

                prev_to = from_date - relativedelta(months=1)
                prev_from = prev_to - relativedelta(months=1)
                return prev_from, prev_to
            except ImportError:
                delta = timedelta(days=30)
        elif period == ComparisonPeriod.QUARTER:
            try:
                from dateutil.relativedelta import relativedelta

                prev_to = from_date - relativedelta(months=3)
                prev_from = prev_to - relativedelta(months=3)
                return prev_from, prev_to
            except ImportError:
                delta = timedelta(days=90)
        elif period == ComparisonPeriod.YEAR:
            try:
                from dateutil.relativedelta import relativedelta

                prev_to = from_date - relativedelta(years=1)
                prev_from = prev_to - relativedelta(years=1)
                return prev_from, prev_to
            except ImportError:
                delta = timedelta(days=365)
        else:
            delta = duration

        prev_to = from_date - timedelta(days=1)
        prev_from = prev_to - delta

        return prev_from, prev_to

    def _determine_status(self, value: float, kpi: KPIDefinition) -> str:
        """Determine KPI health status based on thresholds."""
        if not kpi.thresholds:
            return "healthy"

        t = kpi.thresholds

        # Check critical thresholds
        if t.critical_min is not None and value < t.critical_min:
            return "critical"
        if t.critical_max is not None and value > t.critical_max:
            return "critical"

        # Check warning thresholds
        if t.warning_min is not None and value < t.warning_min:
            return "warning"
        if t.warning_max is not None and value > t.warning_max:
            return "warning"

        return "healthy"

    def _format_value(self, value: float, kpi: KPIDefinition) -> str:
        """Format KPI value for display."""
        decimals = kpi.decimals

        if kpi.format == "currency":
            prefix = kpi.prefix or "$"
            if abs(value) >= 1_000_000:
                return f"{prefix}{value / 1_000_000:,.{decimals}f}M"
            elif abs(value) >= 1_000:
                return f"{prefix}{value / 1_000:,.{decimals}f}K"
            else:
                return f"{prefix}{value:,.{decimals}f}"

        elif kpi.format == "percentage":
            return f"{value:.{decimals}f}%"

        elif kpi.format == "number":
            suffix = kpi.suffix or ""
            if abs(value) >= 1_000_000:
                return f"{value / 1_000_000:,.{decimals}f}M{suffix}"
            elif abs(value) >= 1_000:
                return f"{value / 1_000:,.{decimals}f}K{suffix}"
            else:
                return f"{value:,.{decimals}f}{suffix}"

        return f"{value:,.{decimals}f}"

    # ---------------------------------------------------
    # Template & Config Management
    # ---------------------------------------------------
    def get_templates(self) -> List[KPITemplate]:
        """Get all available KPI templates."""
        return list(ALL_TEMPLATES.values())

    def get_template(self, template_id: str) -> Optional[KPITemplate]:
        """Get a specific template by ID."""
        return ALL_TEMPLATES.get(template_id)

    def get_kpi_definition(self, kpi_id: str) -> Optional[KPIDefinition]:
        """Get a specific KPI definition."""
        return ALL_KPIS.get(kpi_id)

    def get_all_kpis(self) -> Dict[str, KPIDefinition]:
        """Get all available KPI definitions."""
        return ALL_KPIS

    async def save_config(
        self, user_id: str, dataset_id: str, config: SavedKPIConfig
    ) -> str:
        """Save a KPI configuration for a dataset."""
        if not self.kpi_configs:
            raise ValueError("Database not initialized")

        from bson import ObjectId

        config_dict = config.model_dump()
        config_dict["user_id"] = user_id
        config_dict["dataset_id"] = dataset_id
        config_dict["updated_at"] = datetime.utcnow()

        if config.id:
            filter_id = (
                ObjectId(config.id) if ObjectId.is_valid(config.id) else config.id
            )
            await self.kpi_configs.update_one(
                {"_id": filter_id, "user_id": user_id},
                {"$set": config_dict},
                upsert=False,
            )
            return config.id
        else:
            config_dict["created_at"] = datetime.utcnow()
            result = await self.kpi_configs.insert_one(config_dict)
            return str(result.inserted_id)

    async def get_config(
        self, user_id: str, dataset_id: str
    ) -> Optional[SavedKPIConfig]:
        """Get saved KPI config for a dataset."""
        if not self.kpi_configs:
            return None

        doc = await self.kpi_configs.find_one(
            {"user_id": user_id, "dataset_id": dataset_id}
        )

        if doc:
            doc["id"] = str(doc.pop("_id"))
            return SavedKPIConfig(**doc)

        return None


# Singleton instance
kpi_service = KPIService()
