"""
KPI Templates
==============
Pre-built dashboard templates for all supported domains.
Includes: SaaS, E-commerce, Finance, Healthcare, Real Estate, HR,
Marketing, Education, Manufacturing, Logistics.
"""

from db.schemas_kpi import KPICategory, KPITemplate, KPITemplateComponent

# ── Existing templates ────────────────────────────────────────────────────────

SAAS_TEMPLATE = KPITemplate(
    id="saas-metrics",
    name="SaaS Metrics Dashboard",
    description="Essential KPIs for SaaS businesses: MRR, ARR, Churn, LTV, CAC, Runway",
    category=KPICategory.SAAS,
    kpis=[
        KPITemplateComponent(kpi_id="mrr", position=1, span=2),
        KPITemplateComponent(kpi_id="arr", position=2, span=2),
        KPITemplateComponent(kpi_id="churn_rate", position=3, span=1),
        KPITemplateComponent(kpi_id="nrr", position=4, span=1),
        KPITemplateComponent(kpi_id="ltv", position=5, span=1),
        KPITemplateComponent(kpi_id="cac", position=6, span=1),
        KPITemplateComponent(kpi_id="ltv_cac_ratio", position=7, span=1),
        KPITemplateComponent(kpi_id="arpu", position=8, span=1),
        KPITemplateComponent(kpi_id="burn_rate", position=9, span=1),
        KPITemplateComponent(kpi_id="runway", position=10, span=1),
    ],
    required_columns=["revenue", "date"],
    optional_columns=["customer_id", "cost", "churn", "cash"],
    icon="line-chart",
)

ECOMMERCE_TEMPLATE = KPITemplate(
    id="ecommerce-metrics",
    name="E-commerce Dashboard",
    description="Key metrics for online stores: Revenue, AOV, Orders, Margin",
    category=KPICategory.ECOMMERCE,
    kpis=[
        KPITemplateComponent(kpi_id="total_revenue", position=1, span=2),
        KPITemplateComponent(kpi_id="order_count", position=2, span=1),
        KPITemplateComponent(kpi_id="aov", position=3, span=1),
        KPITemplateComponent(kpi_id="gross_margin", position=4, span=2),
    ],
    required_columns=["revenue", "transaction_id"],
    optional_columns=["date", "cost", "quantity"],
    icon="shopping-bag",
)

FINANCE_TEMPLATE = KPITemplate(
    id="finance-metrics",
    name="Financial Overview",
    description="Core financial metrics: Profit, Expenses, Cash Flow",
    category=KPICategory.FINANCE,
    kpis=[
        KPITemplateComponent(kpi_id="gross_profit", position=1, span=2),
        KPITemplateComponent(kpi_id="net_profit", position=2, span=2),
        KPITemplateComponent(kpi_id="operating_expenses", position=3, span=1),
        KPITemplateComponent(kpi_id="net_cash_flow", position=4, span=1),
        KPITemplateComponent(kpi_id="ar_aging", position=5, span=2),
    ],
    required_columns=["revenue", "cost"],
    optional_columns=["date", "cash"],
    icon="bar-chart-2",
)


# ═══════════════════════════════════════════════════════════════════════════════
# NEW DOMAIN TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

HEALTHCARE_TEMPLATE = KPITemplate(
    id="healthcare-metrics",
    name="Healthcare Dashboard",
    description="Key healthcare metrics: Treatment Costs, Length of Stay, Readmission Rate, Patient Volume",
    category=KPICategory.HEALTHCARE,
    kpis=[
        KPITemplateComponent(kpi_id="total_treatment_cost", position=1, span=2),
        KPITemplateComponent(kpi_id="patient_volume", position=2, span=1),
        KPITemplateComponent(kpi_id="avg_cost_per_patient", position=3, span=1),
        KPITemplateComponent(kpi_id="avg_length_of_stay", position=4, span=1),
        KPITemplateComponent(kpi_id="readmission_rate", position=5, span=1),
        KPITemplateComponent(kpi_id="medication_count_avg", position=6, span=2),
    ],
    required_columns=["patient_id", "date"],
    optional_columns=["cost", "diagnosis", "length_of_stay", "readmission"],
    icon="activity",
)

REAL_ESTATE_TEMPLATE = KPITemplate(
    id="real-estate-metrics",
    name="Real Estate Dashboard",
    description="Property market metrics: Sale Price, Days on Market, Price per SqFt",
    category=KPICategory.REAL_ESTATE,
    kpis=[
        KPITemplateComponent(kpi_id="avg_sale_price", position=1, span=2),
        KPITemplateComponent(kpi_id="total_sales_volume", position=2, span=2),
        KPITemplateComponent(kpi_id="days_on_market", position=3, span=1),
        KPITemplateComponent(kpi_id="price_per_sqft", position=4, span=1),
        KPITemplateComponent(kpi_id="listing_count", position=5, span=1),
        KPITemplateComponent(kpi_id="avg_bedrooms", position=6, span=1),
    ],
    required_columns=["property_id", "date"],
    optional_columns=["price", "square_feet", "bedrooms", "bathrooms", "days_on_market"],
    icon="home",
)

HR_TEMPLATE = KPITemplate(
    id="hr-metrics",
    name="HR Dashboard",
    description="Workforce analytics: Headcount, Salary, Turnover, Tenure",
    category=KPICategory.HR,
    kpis=[
        KPITemplateComponent(kpi_id="headcount", position=1, span=1),
        KPITemplateComponent(kpi_id="total_salary_cost", position=2, span=2),
        KPITemplateComponent(kpi_id="avg_salary", position=3, span=1),
        KPITemplateComponent(kpi_id="turnover_rate", position=4, span=1),
        KPITemplateComponent(kpi_id="avg_tenure", position=5, span=1),
        KPITemplateComponent(kpi_id="avg_performance_score", position=6, span=2),
    ],
    required_columns=["employee_id"],
    optional_columns=["salary", "date", "churn", "tenure", "performance", "customer_count"],
    icon="users",
)

MARKETING_TEMPLATE = KPITemplate(
    id="marketing-metrics",
    name="Marketing Dashboard",
    description="Campaign performance: Spend, ROAS, Conversion Rate, Impressions",
    category=KPICategory.MARKETING,
    kpis=[
        KPITemplateComponent(kpi_id="total_spend", position=1, span=1),
        KPITemplateComponent(kpi_id="total_revenue_marketing", position=2, span=2),
        KPITemplateComponent(kpi_id="roas", position=3, span=1),
        KPITemplateComponent(kpi_id="total_impressions", position=4, span=1),
        KPITemplateComponent(kpi_id="total_clicks", position=5, span=1),
        KPITemplateComponent(kpi_id="conversion_rate_marketing", position=6, span=1),
        KPITemplateComponent(kpi_id="cpc", position=7, span=1),
    ],
    required_columns=["revenue", "cost", "date"],
    optional_columns=["impressions", "clicks", "conversions", "acquisition_cost"],
    icon="target",
)

EDUCATION_TEMPLATE = KPITemplate(
    id="education-metrics",
    name="Education Dashboard",
    description="Academic performance: Enrollment, GPA, Graduation Rate, Attendance",
    category=KPICategory.EDUCATION,
    kpis=[
        KPITemplateComponent(kpi_id="enrollment_count", position=1, span=2),
        KPITemplateComponent(kpi_id="avg_gpa", position=2, span=1),
        KPITemplateComponent(kpi_id="avg_grade", position=3, span=1),
        KPITemplateComponent(kpi_id="graduation_rate", position=4, span=2),
        KPITemplateComponent(kpi_id="attendance_rate", position=5, span=2),
    ],
    required_columns=["student_id", "date"],
    optional_columns=["grade", "gpa", "attendance"],
    icon="book-open",
)

MANUFACTURING_TEMPLATE = KPITemplate(
    id="manufacturing-metrics",
    name="Manufacturing Dashboard",
    description="Production metrics: Output, Defect Rate, Yield, Cycle Time",
    category=KPICategory.MANUFACTURING,
    kpis=[
        KPITemplateComponent(kpi_id="total_units_produced", position=1, span=2),
        KPITemplateComponent(kpi_id="yield_rate", position=2, span=1),
        KPITemplateComponent(kpi_id="defect_rate", position=3, span=1),
        KPITemplateComponent(kpi_id="avg_cycle_time", position=4, span=1),
        KPITemplateComponent(kpi_id="total_cost_manufacturing", position=5, span=2),
        KPITemplateComponent(kpi_id="cost_per_unit", position=6, span=1),
        KPITemplateComponent(kpi_id="defect_count", position=7, span=1),
    ],
    required_columns=["date", "quantity"],
    optional_columns=["cost", "defect", "cycle_time", "yield"],
    icon="package",
)

LOGISTICS_TEMPLATE = KPITemplate(
    id="logistics-metrics",
    name="Logistics Dashboard",
    description="Shipping metrics: Cost, Volume, Delivery Time, On-Time Rate",
    category=KPICategory.LOGISTICS,
    kpis=[
        KPITemplateComponent(kpi_id="total_shipping_cost", position=1, span=2),
        KPITemplateComponent(kpi_id="shipment_volume", position=2, span=1),
        KPITemplateComponent(kpi_id="on_time_rate", position=3, span=1),
        KPITemplateComponent(kpi_id="avg_delivery_time", position=4, span=1),
        KPITemplateComponent(kpi_id="cost_per_mile", position=5, span=1),
        KPITemplateComponent(kpi_id="total_weight", position=6, span=1),
        KPITemplateComponent(kpi_id="total_distance", position=7, span=1),
    ],
    required_columns=["shipment_id", "cost", "date"],
    optional_columns=["weight", "distance", "delivery_time", "carrier"],
    icon="truck",
)


# ═══════════════════════════════════════════════════════════════════════════════
# All templates registry
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# AUTOMOTIVE TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════════

AUTOMOTIVE_TEMPLATE = KPITemplate(
    id="automotive-metrics",
    name="Automotive Dashboard",
    description="Vehicle inventory & sales metrics: Price, Mileage, Engine Size, MPG, Listings",
    category=KPICategory.AUTOMOTIVE,
    kpis=[
        KPITemplateComponent(kpi_id="avg_price", position=1, span=2),
        KPITemplateComponent(kpi_id="listing_count", position=2, span=1),
        KPITemplateComponent(kpi_id="avg_mileage", position=3, span=1),
        KPITemplateComponent(kpi_id="avg_engine_size", position=4, span=1),
        KPITemplateComponent(kpi_id="avg_mpg", position=5, span=1),
        KPITemplateComponent(kpi_id="oldest_year", position=6, span=1),
        KPITemplateComponent(kpi_id="avg_horsepower", position=7, span=1),
        KPITemplateComponent(kpi_id="avg_tax", position=8, span=1),
    ],
    required_columns=["mileage"],
    optional_columns=["price", "engine_size", "fuel_type", "transmission", "mpg", "horsepower", "vehicle_model"],
    icon="zap",
)


# ═══════════════════════════════════════════════════════════════════════════════
# All templates registry
# ═══════════════════════════════════════════════════════════════════════════════

ALL_TEMPLATES: dict[str, KPITemplate] = {
    "saas-metrics": SAAS_TEMPLATE,
    "ecommerce-metrics": ECOMMERCE_TEMPLATE,
    "finance-metrics": FINANCE_TEMPLATE,
    "healthcare-metrics": HEALTHCARE_TEMPLATE,
    "real-estate-metrics": REAL_ESTATE_TEMPLATE,
    "hr-metrics": HR_TEMPLATE,
    "marketing-metrics": MARKETING_TEMPLATE,
    "education-metrics": EDUCATION_TEMPLATE,
    "manufacturing-metrics": MANUFACTURING_TEMPLATE,
    "logistics-metrics": LOGISTICS_TEMPLATE,
    "automotive-metrics": AUTOMOTIVE_TEMPLATE,
}
