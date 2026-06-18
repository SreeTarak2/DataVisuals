"""
Query Parser — Natural Language to Graph Query Translator
==========================================================

Translates natural language analytical queries into:
1. Entity references (recognized from the knowledge graph entity types)
2. Intent classification (trend, compare, anomaly, breakdown, describe, list)
3. Cypher query templates parameterized by extracted entities

Used by GraphRAGService to determine what to retrieve from the knowledge graph
and how to traverse relationships.

Key capabilities:
- Intent classification via keyword/pattern matching (no LLM needed for simple queries)
- Entity recognition against known EntityType values + column name fuzzy matching
- Parameterized Cypher query generation with safe parameter binding
- Fallback to generic graph context when intent/entity is unclear
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from .models import EntityType

logger = logging.getLogger(__name__)


# ── Intent Types ──────────────────────────────────────────────────────────────


class QueryIntent(str, Enum):
    """The analytical intent behind a user query."""

    TREND = "trend"               # "How has revenue changed over time?"
    COMPARE = "compare"           # "Compare revenue between segments"
    ANOMALY = "anomaly"           # "Which metrics are anomalous?"
    BREAKDOWN = "breakdown"       # "Show me revenue by product category"
    DESCRIBE = "describe"         # "What is the customer churn rate?"
    LIST = "list"                 # "Show top customers by revenue"
    CORRELATION = "correlation"   # "What drives revenue growth?"
    FORECAST = "forecast"         # "What will revenue be next month?"
    GENERAL = "general"           # Catch-all for ambiguous queries


# ── Query Intent Patterns ────────────────────────────────────────────────────

_INTENT_PATTERNS: List[Tuple[re.Pattern, QueryIntent]] = [
    # Trend
    (re.compile(r"(trend|change|over time|history|historically|trajectory|moving|direction|pattern)"), QueryIntent.TREND),
    (re.compile(r"(how has|how did|how (much|many) .+ (changed|changed|grown|declined))"), QueryIntent.TREND),
    # Compare
    (re.compile(r"(compare|comparison|vs\.|versus|against|differen|difference between)"), QueryIntent.COMPARE),
    (re.compile(r"(better|worse|outperform|underperform)"), QueryIntent.COMPARE),
    # Anomaly
    (re.compile(r"(anomal(y|ies)|outlier|unusual|abnormal|unexpected|surprising|irregular|spike|drop|sudden)"), QueryIntent.ANOMALY),
    # Breakdown
    (re.compile(r"(breakdown|by |per |split|segment|group|category|categorize|distribution)"), QueryIntent.BREAKDOWN),
    (re.compile(r"(show .+ by|break .+ by|group .+ by|slice|drill)"), QueryIntent.BREAKDOWN),
    # Correlation/Driver
    (re.compile(r"(correlation|correlate|driver|drives|relationship|relate|impact|cause|reason|because|influence)"), QueryIntent.CORRELATION),
    # Forecast
    (re.compile(r"(forecast|predict|projection|project|estimate|next (month|quarter|year)|future)"), QueryIntent.FORECAST),
    # Describe
    (re.compile(r"(what is|what are|show me|tell me about|describe|give me|list|find|get|retrieve)"), QueryIntent.DESCRIBE),
    # List
    (re.compile(r"(top |bottom |highest|lowest|largest|smallest|most|least|rank|sorted|ordered)"), QueryIntent.LIST),
]


# ── Entity Recognition Patterns ──────────────────────────────────────────────

# Maps natural language terms → EntityType
_ENTITY_KEYWORDS: Dict[str, EntityType] = {
    # Transaction
    "transaction": EntityType.TRANSACTION,
    "transactions": EntityType.TRANSACTION,
    "order": EntityType.ORDER,
    "orders": EntityType.ORDER,
    "purchase": EntityType.TRANSACTION,
    "purchases": EntityType.TRANSACTION,
    "sale": EntityType.TRANSACTION,
    "sales": EntityType.TRANSACTION,
    "invoice": EntityType.INVOICE,
    "invoices": EntityType.INVOICE,
    # Customer
    "customer": EntityType.CUSTOMER,
    "customers": EntityType.CUSTOMER,
    "client": EntityType.CUSTOMER,
    "clients": EntityType.CUSTOMER,
    "buyer": EntityType.CUSTOMER,
    "buyers": EntityType.CUSTOMER,
    # Product
    "product": EntityType.PRODUCT,
    "products": EntityType.PRODUCT,
    "item": EntityType.PRODUCT,
    "items": EntityType.PRODUCT,
    "sku": EntityType.PRODUCT,
    # People
    "person": EntityType.PERSON,
    "people": EntityType.PERSON,
    "employee": EntityType.EMPLOYEE,
    "employees": EntityType.EMPLOYEE,
    "staff": EntityType.EMPLOYEE,
    "patient": EntityType.PATIENT,
    "patients": EntityType.PATIENT,
    # Organization
    "organization": EntityType.ORGANIZATION,
    "organizations": EntityType.ORGANIZATION,
    "company": EntityType.COMPANY,
    "companies": EntityType.COMPANY,
    "vendor": EntityType.VENDOR,
    "vendors": EntityType.VENDOR,
    "supplier": EntityType.SUPPLIER,
    "suppliers": EntityType.SUPPLIER,
    # Geography
    "region": EntityType.GEOGRAPHY,
    "regions": EntityType.GEOGRAPHY,
    "country": EntityType.GEOGRAPHY,
    "countries": EntityType.GEOGRAPHY,
    "city": EntityType.GEOGRAPHY,
    "cities": EntityType.GEOGRAPHY,
    "state": EntityType.GEOGRAPHY,
    "states": EntityType.GEOGRAPHY,
    "location": EntityType.GEOGRAPHY,
    "locations": EntityType.GEOGRAPHY,
    # Time
    "date": EntityType.TIMEDIMENSION,
    "dates": EntityType.TIMEDIMENSION,
    "time": EntityType.TIMEDIMENSION,
    "month": EntityType.TIMEDIMENSION,
    "months": EntityType.TIMEDIMENSION,
    "quarter": EntityType.TIMEDIMENSION,
    "quarters": EntityType.TIMEDIMENSION,
    "year": EntityType.TIMEDIMENSION,
    "years": EntityType.TIMEDIMENSION,
    "period": EntityType.TIMEDIMENSION,
    "periods": EntityType.TIMEDIMENSION,
    # Measures
    "revenue": EntityType.METRIC,
    "cost": EntityType.METRIC,
    "profit": EntityType.METRIC,
    "margin": EntityType.METRIC,
    "kpi": EntityType.METRIC,
    "kpis": EntityType.METRIC,
    "metric": EntityType.METRIC,
    "metrics": EntityType.METRIC,
    "amount": EntityType.AMOUNT,
    "amounts": EntityType.AMOUNT,
    "quantity": EntityType.QUANTITY,
    "quantities": EntityType.QUANTITY,
    "count": EntityType.QUANTITY,
    # Classification
    "category": EntityType.CATEGORY,
    "categories": EntityType.CATEGORY,
    "type": EntityType.CLASSIFICATION,
    "types": EntityType.CLASSIFICATION,
    "status": EntityType.STATUS,
    "statuses": EntityType.STATUS,
    "segment": EntityType.CLASSIFICATION,
    "segments": EntityType.CLASSIFICATION,
    "class": EntityType.CLASSIFICATION,
    "classification": EntityType.CLASSIFICATION,
}


# ── Cypher Query Templates ───────────────────────────────────────────────────

# Parameterized Cypher templates. Parameters are filled at query time.
# Entity labels and relationship types follow the knowledge graph schema.

_CYPHER_TEMPLATES: Dict[QueryIntent, str] = {
    QueryIntent.DESCRIBE: """
        MATCH (entity:{entity_type})
        WHERE entity.dataset_id = $dataset_id
        OPTIONAL MATCH (entity)-[r]-(related)
        RETURN entity, type(r) as rel_type, related
        LIMIT $limit
    """,
    QueryIntent.LIST: """
        MATCH (entity:{entity_type})
        WHERE entity.dataset_id = $dataset_id
        OPTIONAL MATCH (entity)-[r]-(related)
        WITH entity, collect(DISTINCT {{rel: type(r), related: related}}) as relationships
        RETURN entity, relationships
        ORDER BY entity.confidence DESC
        LIMIT $limit
    """,
    QueryIntent.TREND: """
        MATCH (time:{time_type})
        WHERE time.dataset_id = $dataset_id
        MATCH (time)-[:MEASURES]->(metric)
        WHERE metric.dataset_id = $dataset_id AND metric.column_name = $metric_column
        RETURN time, metric
        ORDER BY time.column_name
        LIMIT $limit
    """,
    QueryIntent.COMPARE: """
        MATCH (a:{entity_type})
        WHERE a.dataset_id = $dataset_id
        MATCH (b:{entity_type})
        WHERE b.dataset_id = $dataset_id
        MATCH (a)-[r1]-(metric)
        MATCH (b)-[r2]-(metric)
        WHERE metric.dataset_id = $dataset_id
        AND NOT a = b
        RETURN a, b, metric, type(r1) as rel_a, type(r2) as rel_b
        LIMIT $limit
    """,
    QueryIntent.BREAKDOWN: """
        MATCH (entity:{entity_type})
        WHERE entity.dataset_id = $dataset_id
        MATCH (entity)-[r]->(dimension)
        WHERE dimension.dataset_id = $dataset_id
        RETURN entity, r, dimension
        LIMIT $limit
    """,
    QueryIntent.ANOMALY: """
        MATCH (metric)
        WHERE metric.dataset_id = $dataset_id
        AND metric.is_anomaly = true
        OPTIONAL MATCH (metric)-[r]-(related)
        RETURN metric, r, related
        LIMIT $limit
    """,
    QueryIntent.CORRELATION: """
        MATCH (metric1)-[r]-(metric2)
        WHERE metric1.dataset_id = $dataset_id
        AND metric2.dataset_id = $dataset_id
        AND NOT metric1 = metric2
        AND r.correlation IS NOT NULL
        RETURN metric1, metric2, r.correlation as strength
        ORDER BY abs(r.correlation) DESC
        LIMIT $limit
    """,
}


# ── Parser Output ────────────────────────────────────────────────────────────


@dataclass
class ParsedQuery:
    """Result of parsing a natural language query."""

    original_query: str
    intent: QueryIntent = QueryIntent.GENERAL
    entities: List[EntityType] = field(default_factory=list)
    entity_keywords: List[str] = field(default_factory=list)
    metric_column: Optional[str] = None
    dimension_column: Optional[str] = None
    time_column: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    cypher_query: Optional[str] = None
    cypher_params: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    requires_llm: bool = False


# ── Parser ───────────────────────────────────────────────────────────────────


class QueryParser:
    """
    Parses natural language queries into structured graph query instructions.

    Supports:
    - Intent classification via keyword patterns
    - Entity type recognition from NL terms
    - Column name fuzzy matching against extracted entities
    - Parameterized Cypher query generation
    - Fallback to general context retrieval when parsing is uncertain
    """

    # Thresholds for confident parsing
    MIN_INTENT_CONFIDENCE = 0.4
    MIN_ENTITY_CONFIDENCE = 0.5
    MAX_CYPHER_RESULTS = 100

    def __init__(self) -> None:
        logger.info("QueryParser initialized")

    # ── Intent Classification ────────────────────────────────────────────────

    def classify_intent(self, query: str) -> Tuple[QueryIntent, float]:
        """
        Classify the analytical intent of a query using keyword pattern matching.

        Priority-based resolution:
        - LIST wins over BREAKDOWN when query starts with "show/list" + contains ranking words
        - ANOMALY wins over all when anomaly keywords present
        - TREND wins over DESCRIBE when temporal keywords present

        Returns:
            Tuple of (QueryIntent, confidence score 0-1)
        """
        query_lower = query.lower().strip()

        scores: Dict[QueryIntent, float] = {intent: 0.0 for intent in QueryIntent}

        for pattern, intent in _INTENT_PATTERNS:
            if pattern.search(query_lower):
                scores[intent] += 0.3

        # Boost specific patterns for higher precision
        # DESCRIBE: "what is/are" queries
        if re.search(r"^(what|who) (is|are|was|were) ", query_lower):
            scores[QueryIntent.DESCRIBE] += 0.4

        # LIST: starts with "show" or "list"
        if re.search(r"^(show|list|get|find|display) ", query_lower):
            scores[QueryIntent.LIST] += 0.3

        # COMPARE: explicit comparison words
        if re.search(r" vs[.\s]| versus |difference between|compare|better|worse", query_lower):
            scores[QueryIntent.COMPARE] += 0.3

        # TREND: temporal keywords
        if re.search(r"(monthly|quarterly|yearly|daily|weekly|over time|trend|trajectory)", query_lower):
            scores[QueryIntent.TREND] += 0.3

        # ANOMALY: detection keywords
        if re.search(r"(anomal|outlier|unusual|spike|drop|sudden|abnormal)", query_lower):
            scores[QueryIntent.ANOMALY] += 0.3

        # ── Priority resolution rules ────────────────────────────────────────
        # Rule 1: LIST trumps BREAKDOWN when ranking keywords present with "show"
        if (scores[QueryIntent.LIST] > 0 and scores[QueryIntent.BREAKDOWN] > 0
                and re.search(r"^(show|list|get|find|display) .*(top|bottom|highest|lowest|largest|smallest)", query_lower)):
            scores[QueryIntent.BREAKDOWN] = 0.0

        # Rule 2: ANOMALY is highest priority when clearly present
        has_strong_anomaly = bool(re.search(r"(anomaly|anomalies|outlier)", query_lower))
        if has_strong_anomaly:
            scores[QueryIntent.ANOMALY] += 0.5

        # Rule 3: COMPARE trumps BREAKDOWN for explicit comparison phrases
        if re.search(r"compare |vs[. ]| versus |difference between", query_lower):
            # Don't let "by" in phrases like "compare X by Y" trigger BREAKDOWN
            if scores[QueryIntent.BREAKDOWN] > 0:
                scores[QueryIntent.BREAKDOWN] = max(0.1, scores[QueryIntent.BREAKDOWN] - 0.1)

        max_score = max(scores.values(), default=0)

        if max_score == 0:
            # No intent patterns matched — default to DESCRIBE for "what/which" queries
            if re.search(r"\b(what|which|how)\b", query_lower):
                return QueryIntent.DESCRIBE, 0.3
            return QueryIntent.GENERAL, 0.1

        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        # Normalize confidence to 0-1 range
        confidence = min(best_score / max_score, 1.0)

        return best_intent, confidence

    # ── Entity Recognition ───────────────────────────────────────────────────

    def extract_entities(self, query: str) -> List[Tuple[EntityType, str, float]]:
        """
        Extract entity type references from a natural language query.

        Uses keyword matching against _ENTITY_KEYWORDS. Each keyword maps to
        an EntityType. Returns all matches with the matched keyword and a
        confidence score based on match specificity.

        Returns:
            List of (EntityType, matched_keyword, confidence)
        """
        query_lower = query.lower()
        results: List[Tuple[EntityType, str, float]] = []

        # Sort by length descending to match longer, more specific terms first
        for keyword, entity_type in sorted(
            _ENTITY_KEYWORDS.items(), key=lambda x: -len(x[0])
        ):
            if keyword in query_lower:
                # Check it's a word boundary match (not just a substring)
                pattern = re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
                if pattern.search(query):
                    # Confidence: longer matches = more specific = higher confidence
                    confidence = min(0.5 + (len(keyword) / 20), 0.95)
                    results.append((entity_type, keyword, confidence))

        # Deduplicate by entity type, keeping the highest confidence match
        seen: Dict[EntityType, Tuple[str, float]] = {}
        for entity_type, keyword, confidence in results:
            if entity_type not in seen or confidence > seen[entity_type][1]:
                seen[entity_type] = (keyword, confidence)

        return [
            (entity_type, keyword, confidence)
            for entity_type, (keyword, confidence) in seen.items()
        ]

    # ── Column Matching ─────────────────────────────────────────────────────

    @staticmethod
    def _get_entity_type_value(entity_type: Any) -> str:
        """Safely extract the string value from an EntityType enum or string."""
        if isinstance(entity_type, str):
            return entity_type
        if hasattr(entity_type, 'value'):
            return entity_type.value
        return str(entity_type)

    def match_entity_to_column(
        self,
        entity_type: Any,
        extracted_entities: List[Dict[str, Any]],
    ) -> Optional[str]:
        """
        Match an entity type to an actual column name from the extraction results.

        Uses the column_name and entity_type fields from extracted entities.
        Accepts both EntityType enum values and strings.

        Args:
            entity_type: The EntityType enum or string value to match
            extracted_entities: List of entity dicts from EntityExtractor (must have
                               'column_name' and 'entity_type' fields)

        Returns:
            Column name if matched, None otherwise
        """
        target_value = self._get_entity_type_value(entity_type).lower()

        # First pass: exact match
        for entity in extracted_entities:
            if isinstance(entity, dict):
                detected = entity.get("entity_type", "")
                detected_value = self._get_entity_type_value(detected).lower()
                if detected_value == target_value:
                    return entity.get("column_name")

        # Second pass: partial match (target is substring of detected type)
        for entity in extracted_entities:
            if isinstance(entity, dict):
                detected = entity.get("entity_type", "")
                detected_value = self._get_entity_type_value(detected).lower()
                if target_value in detected_value:
                    return entity.get("column_name")

        return None

    def _find_metric_columns(
        self, extracted_entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Find all metric/measure columns from extracted entities."""
        metric_types = {EntityType.METRIC.value.lower(), EntityType.AMOUNT.value.lower(), EntityType.QUANTITY.value.lower()}
        columns = []
        for entity in extracted_entities:
            if isinstance(entity, dict):
                et = entity.get("entity_type", "")
                if isinstance(et, str) and et.lower() in metric_types:
                    col = entity.get("column_name")
                    if col:
                        columns.append(col)
        return columns

    def _find_dimension_columns(
        self, extracted_entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Find all dimension/classification columns from extracted entities."""
        dim_types = {
            EntityType.CATEGORY.value.lower(), EntityType.CLASSIFICATION.value.lower(),
            EntityType.GEOGRAPHY.value.lower(), EntityType.STATUS.value.lower(),
        }
        columns = []
        for entity in extracted_entities:
            if isinstance(entity, dict):
                et = entity.get("entity_type", "")
                if isinstance(et, str) and et.lower() in dim_types:
                    col = entity.get("column_name")
                    if col:
                        columns.append(col)
        return columns

    # ── Cypher Query Building ───────────────────────────────────────────────

    def build_cypher_query(
        self,
        intent: Any,
        entity_types: List[EntityType],
        extracted_entities: List[Dict[str, Any]],
        dataset_id: str,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Build a parameterized Cypher query from parsed intent and entities.

        Args:
            intent: The classified query intent (QueryIntent or string)
            entity_types: List of recognized entity types
            extracted_entities: Column → EntityType mappings from EntityExtractor
            dataset_id: Dataset ID for filtering

        Returns:
            Tuple of (cypher_query_string, parameters_dict) or (None, {}) if no query can be built
        """
        # Ensure intent is a QueryIntent (handle string values)
        if isinstance(intent, str):
            try:
                intent = QueryIntent(intent)
            except ValueError:
                intent = QueryIntent.GENERAL

        template = _CYPHER_TEMPLATES.get(intent)
        if not template:
            # Fall back to a generic entity query
            return self._build_generic_query(extracted_entities, dataset_id)

        params: Dict[str, Any] = {
            "dataset_id": dataset_id,
            "limit": self.MAX_CYPHER_RESULTS,
        }

        # Determine primary entity type for the template
        primary_entity = self._get_primary_entity_type(entity_types, intent)

        # Map entity types to actual columns if possible
        metric_cols = self._find_metric_columns(extracted_entities)
        dim_cols = self._find_dimension_columns(extracted_entities)

        if metric_cols:
            params["metric_column"] = metric_cols[0]
        if dim_cols:
            params["dimension_column"] = dim_cols[0]

        # Find time column
        time_cols = []
        for entity in extracted_entities:
            if isinstance(entity, dict):
                if entity.get("entity_type", "").lower() == EntityType.TIMEDIMENSION.value.lower():
                    col = entity.get("column_name")
                    if col:
                        time_cols.append(col)
        if time_cols:
            params["time_column"] = time_cols[0]

        # Fill the template
        entity_type_str = primary_entity.value if primary_entity else "Entity"
        time_type_str = EntityType.TIMEDIMENSION.value

        try:
            query = template.format(
                entity_type=entity_type_str,
                time_type=time_type_str,
            )
            return query, params
        except KeyError as e:
            logger.warning(f"Cypher template formatting failed (missing key {e})")
            return self._build_generic_query(extracted_entities, dataset_id)

    def _get_primary_entity_type(
        self, entity_types: List[EntityType], intent: QueryIntent
    ) -> Optional[EntityType]:
        """Choose the most relevant entity type for the query intent."""
        if not entity_types:
            return None

        # For breakdown/introspection queries, prefer dimension types
        if intent in (QueryIntent.BREAKDOWN, QueryIntent.COMPARE):
            for et in entity_types:
                if et in (EntityType.CUSTOMER, EntityType.PRODUCT, EntityType.GEOGRAPHY,
                          EntityType.CATEGORY, EntityType.ORGANIZATION, EntityType.CLASSIFICATION):
                    return et

        # For trend/forecast, prefer metric or time
        if intent in (QueryIntent.TREND, QueryIntent.FORECAST):
            for et in entity_types:
                if et in (EntityType.METRIC, EntityType.AMOUNT, EntityType.TIMEDIMENSION):
                    return et

        # For list/describe, prefer the most specific entity type
        priority = [
            EntityType.CUSTOMER, EntityType.PRODUCT, EntityType.ORGANIZATION,
            EntityType.TRANSACTION, EntityType.ORDER, EntityType.EMPLOYEE,
            EntityType.PATIENT, EntityType.GEOGRAPHY, EntityType.INVOICE,
        ]
        for et in priority:
            if et in entity_types:
                return et

        # Default to first entity found
        return entity_types[0]

    def _build_generic_query(
        self,
        extracted_entities: List[Dict[str, Any]],
        dataset_id: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """Build a fallback query that retrieves general graph context."""
        # Collect entity types present
        entity_labels = set()
        for entity in extracted_entities:
            if isinstance(entity, dict):
                et = entity.get("entity_type", "")
                if isinstance(et, str) and et not in ("", "GenericEntity", "GenericReference", "GenericAttribute"):
                    entity_labels.add(et)

        if entity_labels:
            labels_str = ":".join(sorted(entity_labels))
            query = f"""
                MATCH (n:{labels_str})
                WHERE n.dataset_id = $dataset_id
                OPTIONAL MATCH (n)-[r]-(related)
                RETURN n, type(r) as rel_type, related
                LIMIT $limit
            """
        else:
            # Broadest fallback: get all entities for this dataset
            query = """
                MATCH (n:Entity)
                WHERE n.dataset_id = $dataset_id
                RETURN n
                LIMIT $limit
            """

        return query, {"dataset_id": dataset_id, "limit": self.MAX_CYPHER_RESULTS}

    # ── Main Entry Point ────────────────────────────────────────────────────

    async def parse(
        self,
        query: str,
        extracted_entities: Optional[List[Dict[str, Any]]] = None,
        dataset_id: Optional[str] = None,
    ) -> ParsedQuery:
        """
        Parse a natural language query into a structured ParsedQuery.

        Combines intent classification, entity extraction, and Cypher query building.

        Args:
            query: The user's natural language query
            extracted_entities: Optional list of entity dicts from EntityExtractor
                               (each with 'column_name' and 'entity_type')
            dataset_id: Optional dataset ID for Cypher query filtering

        Returns:
            ParsedQuery with intent, entities, Cypher query, and confidence
        """
        parsed = ParsedQuery(original_query=query)

        # Step 1: Classify intent
        intent, intent_conf = self.classify_intent(query)
        parsed.intent = intent
        parsed.confidence = intent_conf

        # Step 2: Extract entity types from query
        entity_matches = self.extract_entities(query)
        parsed.entities = [et for et, _, _ in entity_matches]
        parsed.entity_keywords = [kw for _, kw, _ in entity_matches]

        # Step 3: Match entities to columns if extraction results available
        extracted_entities_list = extracted_entities or []
        for et, keyword, _ in entity_matches:
            col = self.match_entity_to_column(et, extracted_entities_list)
            if col:
                if et in (EntityType.METRIC, EntityType.AMOUNT, EntityType.QUANTITY):
                    parsed.metric_column = col
                elif et in (EntityType.CATEGORY, EntityType.CLASSIFICATION, EntityType.GEOGRAPHY, EntityType.STATUS):
                    parsed.dimension_column = col
                elif et == EntityType.TIMEDIMENSION:
                    parsed.time_column = col

        # Step 4: If we have a dataset_id, build the Cypher query
        if dataset_id:
            cypher, params = self.build_cypher_query(
                intent, parsed.entities, extracted_entities_list, dataset_id
            )
            parsed.cypher_query = cypher
            parsed.cypher_params = params

        # Step 5: Determine if LLM is needed for refinement
        # If confidence is low or intent is GENERAL, LLM can help disambiguate
        if intent_conf < self.MIN_INTENT_CONFIDENCE or intent == QueryIntent.GENERAL:
            parsed.requires_llm = True

        logger.debug(
            f"Parsed query: intent={intent.value} ({intent_conf:.2f}), "
            f"entities={[e.value for e in parsed.entities]}, "
            f"has_cypher={parsed.cypher_query is not None}, "
            f"needs_llm={parsed.requires_llm}"
        )
        return parsed

    # ── Batch Parse for Multiple Datasets ───────────────────────────────────

    async def parse_batch(
        self,
        query: str,
        dataset_entities: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, ParsedQuery]:
        """
        Parse the same query against multiple datasets.

        Args:
            query: The user's natural language query
            dataset_entities: Dict of dataset_id → list of extracted entity dicts

        Returns:
            Dict of dataset_id → ParsedQuery
        """
        results = {}
        for dataset_id, entities in dataset_entities.items():
            results[dataset_id] = await self.parse(
                query, extracted_entities=entities, dataset_id=dataset_id
            )
        return results


# Singleton
query_parser = QueryParser()

__all__ = [
    "QueryParser",
    "QueryIntent",
    "ParsedQuery",
    "query_parser",
]
