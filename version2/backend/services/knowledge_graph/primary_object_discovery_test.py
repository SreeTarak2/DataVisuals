"""
Tests for Primary Business Object Discovery + Participating Entity Discovery
================================================================================

Three test suites:
1. Clean datasets — obvious primary object with clear participants
2. Denormalized datasets — multiple candidates, picks right primary
3. Adversarial — must NOT hallucinate meaning from weak signals
"""

import pytest
import logging
from typing import List, Dict

from services.knowledge_graph.models import (
    DiscoveredEntity,
    PrimaryObjectResult,
    ParticipatingEntity,
)
from services.knowledge_graph.primary_object_discovery import (
    PrimaryObjectDiscovery,
    primary_object_discovery,
    PRIMARY_OBJECT_WEIGHTS,
    PRIMARY_OBJECT_MIN_CONFIDENCE,
)
from services.knowledge_graph.participation_discovery import (
    ParticipationDiscovery,
    participation_discovery,
    PARTICIPATION_MIN,
    NAMING_WEIGHT,
    ENTITY_CONF_WEIGHT,
)

logger = logging.getLogger(__name__)


# ============================================================================
# FIXTURES
# ============================================================================


def make_entity(
    label: str,
    columns: List[str],
    identifier: str,
    entity_conf: float,
    role_counts: Dict[str, int],
    is_valid: bool = True,
) -> DiscoveredEntity:
    return DiscoveredEntity(
        label=label,
        columns=columns,
        identifier_column=identifier,
        role_counts=role_counts,
        role_confidence=entity_conf,
        candidate_confidence=entity_conf,
        entity_confidence=entity_conf,
        confidence=entity_conf,
        is_valid=is_valid,
        validation_notes=[],
    )


@pytest.fixture
def clean_orders_dataset() -> tuple:
    """A clean orders dataset with obvious structure.

    Columns: order_id, order_date, customer_id, customer_name, product_id,
             product_name, amount, quantity, status
    """
    entities = [
        make_entity(
            label="order",
            columns=["order_id", "order_date", "amount", "quantity", "status"],
            identifier="order_id",
            entity_conf=0.92,
            role_counts={
                "IDENTIFIER": 1,
                "DATE": 1,
                "AMOUNT": 1,
                "QUANTITY": 1,
                "STATUS": 1,
            },
        ),
        make_entity(
            label="customer",
            columns=["customer_id", "customer_name"],
            identifier="customer_id",
            entity_conf=0.88,
            role_counts={"IDENTIFIER": 1, "NAME": 1},
        ),
        make_entity(
            label="product",
            columns=["product_id", "product_name"],
            identifier="product_id",
            entity_conf=0.85,
            role_counts={"IDENTIFIER": 1, "NAME": 1},
        ),
    ]
    return entities, "orders_export_2025", 9


@pytest.fixture
def denormalized_dataset() -> tuple:
    """A denormalized dataset with multiple strong candidates.

    Columns: id, patient_name, diagnosis, doctor_name, hospital, room,
             admission_date, discharge_date, bill_amount, insurance_id
    """
    entities = [
        make_entity(
            label="patient",
            columns=["patient_id", "patient_name", "diagnosis"],
            identifier="patient_id",
            entity_conf=0.90,
            role_counts={"IDENTIFIER": 1, "NAME": 1, "CATEGORY": 1},
        ),
        make_entity(
            label="doctor",
            columns=["doctor_name"],
            identifier="doctor_name",
            entity_conf=0.65,
            role_counts={"NAME": 1},
        ),
        make_entity(
            label="hospital",
            columns=["hospital", "room"],
            identifier="hospital",
            entity_conf=0.55,
            role_counts={"LOCATION": 1, "CATEGORY": 1},
        ),
        make_entity(
            label="admission",
            columns=["admission_date", "discharge_date", "bill_amount", "insurance_id"],
            identifier="admission_id",
            entity_conf=0.60,
            role_counts={"DATE": 2, "AMOUNT": 1, "IDENTIFIER": 1},
        ),
    ]
    return entities, "patient_records", 10


@pytest.fixture
def adversarial_generic_dataset() -> tuple:
    """
    THE critical adversarial dataset.
    Columns: id, name, status, date

    Every AI system wants to hallucinate meaning here. Signal must not.
    """
    entities = [
        make_entity(
            label="generic",
            columns=["id", "name", "status", "date"],
            identifier="id",
            entity_conf=0.25,
            role_counts={"IDENTIFIER": 1, "NAME": 1, "STATUS": 1, "DATE": 1},
            is_valid=False,
        ),
    ]
    return entities, "dataset_export", 4


@pytest.fixture
def single_entity_dataset() -> tuple:
    """Only one entity — it must become the primary object."""
    entities = [
        make_entity(
            label="customer",
            columns=["customer_id", "customer_name", "email", "phone", "signup_date", "tier"],
            identifier="customer_id",
            entity_conf=0.95,
            role_counts={
                "IDENTIFIER": 1,
                "NAME": 1,
                "EMAIL": 1,
                "PHONE": 1,
                "DATE": 1,
                "CATEGORY": 1,
            },
        ),
    ]
    return entities, "customers", 6


@pytest.fixture
def participation_test_entities() -> tuple:
    """Fixture specifically for participation discovery tests.

    The `product_id` case from the critique:
    - order is primary (high confidence, many columns)
    - product is participant (single column, moderate entity_confidence)
    """
    entities = [
        make_entity(
            label="order",
            columns=["order_id", "order_date", "amount"],
            identifier="order_id",
            entity_conf=0.95,
            role_counts={"IDENTIFIER": 1, "DATE": 1, "AMOUNT": 1},
        ),
        make_entity(
            label="product",
            columns=["product_id"],
            identifier="product_id",
            entity_conf=0.40,
            role_counts={"IDENTIFIER": 1},
        ),
        make_entity(
            label="customer",
            columns=["customer_id"],
            identifier="customer_id",
            entity_conf=0.38,
            role_counts={"IDENTIFIER": 1},
        ),
    ]
    return entities, "orders", 5


# ============================================================================
# PRIMARY OBJECT DISCOVERY TESTS
# ============================================================================


class TestPrimaryObjectDiscovery:
    def test_clean_orders_picks_order(self, clean_orders_dataset):
        entities, table_name, total_cols = clean_orders_dataset
        result = primary_object_discovery.discover(entities, table_name, total_cols)

        assert result.is_valid
        assert result.label == "order"
        assert result.confidence >= 0.70

    def test_clean_orders_score_breakdown(self, clean_orders_dataset):
        entities, table_name, total_cols = clean_orders_dataset
        result = primary_object_discovery.discover(entities, table_name, total_cols)

        # TABLE_NAME = 0.10 → "orders_export_2025" → "order" matches
        assert result.table_name_score > 0

        # Order entity has 5/9 columns + identifier + measures → dominant
        assert result.column_dominance_score > 0.30

        # Order has high entity_confidence
        assert result.entity_confidence_score >= 0.90

    def test_denormalized_picks_patient(self, denormalized_dataset):
        entities, table_name, total_cols = denormalized_dataset
        result = primary_object_discovery.discover(entities, table_name, total_cols)

        assert result.is_valid
        assert result.label == "patient"

    def test_adversarial_low_confidence(self, adversarial_generic_dataset):
        """The critical test: id, name, status, date must NOT produce valid primary object."""
        entities, table_name, total_cols = adversarial_generic_dataset
        result = primary_object_discovery.discover(entities, table_name, total_cols)

        assert result.is_valid is False
        assert result.confidence < PRIMARY_OBJECT_MIN_CONFIDENCE

    def test_single_entity_is_primary(self, single_entity_dataset):
        entities, table_name, total_cols = single_entity_dataset
        result = primary_object_discovery.discover(entities, table_name, total_cols)

        assert result.is_valid
        assert result.label == "customer"
        assert result.confidence >= 0.80

    def test_empty_entities_returns_invalid(self):
        result = primary_object_discovery.discover([], "", 0)

        assert result.is_valid is False
        assert result.label == "unknown"
        assert result.confidence == 0.0

    def test_table_name_signal_is_weak(self):
        """Verify TABLE_NAME=0.10 weighting — a table name match alone can't
        overcome poor entity confidence or column dominance."""
        # Entity with label "order" but only 1 column and low confidence
        entities = [
            make_entity(
                label="order",
                columns=["order_id"],
                identifier="order_id",
                entity_conf=0.30,
                role_counts={"IDENTIFIER": 1},
                is_valid=False,
            ),
            make_entity(
                label="customer",
                columns=["customer_id", "customer_name", "email", "phone"],
                identifier="customer_id",
                entity_conf=0.85,
                role_counts={"IDENTIFIER": 1, "NAME": 1, "EMAIL": 1, "PHONE": 1},
            ),
        ]
        result = primary_object_discovery.discover(entities, "orders_export", 5)

        # Customer should win over Order despite table name matching "order"
        assert result.label == "customer"

    def test_table_name_score_calculation(self):
        entity = make_entity("product", ["product_id"], "product_id", 0.90, {"IDENTIFIER": 1})
        discovery = PrimaryObjectDiscovery()

        # Exact match
        exact = discovery._score_table_name(entity, "product")
        assert exact == 1.0

        # Entity label in table name
        partial = discovery._score_table_name(entity, "products_export")
        assert partial == 0.8

        # No match
        none = discovery._score_table_name(entity, "customers")
        assert none == 0.0

    def test_column_dominance_score_calculation(self):
        entity = make_entity(
            "order",
            ["order_id", "date", "amount"],
            "order_id",
            0.90,
            {"IDENTIFIER": 1, "DATE": 1, "AMOUNT": 1},
        )
        discovery = PrimaryObjectDiscovery()

        # (3/5 cols + id bonus(0.15) + measure bonus(0.10)) * entity_conf(0.90)
        # = (0.60 + 0.25) * 0.90 = 0.765
        score = discovery._score_column_dominance(entity, 5)
        assert pytest.approx(score, abs=0.01) == 0.765

        # No columns
        score_zero = discovery._score_column_dominance(entity, 0)
        assert score_zero == 0.0


# ============================================================================
# PARTICIPATING ENTITY DISCOVERY TESTS
# ============================================================================


class TestParticipationDiscovery:
    def test_clean_orders_discovers_participants(self, clean_orders_dataset):
        entities, table_name, total_cols = clean_orders_dataset
        primary = primary_object_discovery.discover(entities, table_name, total_cols)

        participants = participation_discovery.discover(entities, primary)

        assert len(participants) == 2
        assert participants[0].participation_score >= participants[1].participation_score

        labels = {p.label for p in participants}
        assert "customer" in labels
        assert "product" in labels

    def test_product_id_survives_participation_threshold(self, participation_test_entities):
        """
        The critical bugfix test:
        product_id with naming_evidence=0.95 and entity_confidence=0.40
        must produce participation_score > PARTICIPATION_MIN (0.50).

        Old formula: 0.95 * 0.40 = 0.38 → FAILS
        New formula: 0.60 * 0.95 + 0.40 * 0.40 = 0.73 → PASSES
        """
        entities, table_name, total_cols = participation_test_entities
        primary = primary_object_discovery.discover(entities, table_name, total_cols)

        column_naming = {
            "product_id": 0.95,
            "customer_id": 0.95,
        }
        participants = participation_discovery.discover(entities, primary, column_naming)

        product_participant = next((p for p in participants if p.label == "product"), None)
        assert product_participant is not None, "Product must be a participant"
        assert product_participant.is_valid, "Product must pass participation threshold"
        assert product_participant.participation_score >= PARTICIPATION_MIN

        # Verify the weighted sum formula: 0.60 * 0.95 + 0.40 * 0.40 = 0.73
        expected = round(0.60 * 0.95 + 0.40 * 0.40, 3)
        assert product_participant.participation_score == expected

    def test_customer_low_conf_still_participates(self, participation_test_entities):
        """
        customer_id with naming_evidence=0.95 and entity_confidence=0.38
        should still pass the participation threshold.
        """
        entities, table_name, total_cols = participation_test_entities
        primary = primary_object_discovery.discover(entities, table_name, total_cols)

        column_naming = {
            "product_id": 0.95,
            "customer_id": 0.95,
        }
        participants = participation_discovery.discover(entities, primary, column_naming)

        customer_participant = next((p for p in participants if p.label == "customer"), None)
        assert customer_participant is not None
        assert customer_participant.is_valid

        # 0.60 * 0.95 + 0.40 * 0.38 = 0.57 + 0.152 = 0.722
        expected = round(0.60 * 0.95 + 0.40 * 0.38, 3)
        assert customer_participant.participation_score == expected

    def test_adversarial_no_participants(self, adversarial_generic_dataset):
        """id, name, status, date must discover NO participants."""
        entities, table_name, total_cols = adversarial_generic_dataset
        primary = primary_object_discovery.discover(entities, table_name, total_cols)

        participants = participation_discovery.discover(entities, primary)

        assert len(participants) == 0

    def test_no_primary_produces_no_participants(self):
        result = participation_discovery.discover(
            [],
            PrimaryObjectResult(
                label="unknown",
                entity_label="unknown",
                confidence=0.0,
                is_valid=False,
            ),
        )
        assert result == []

    def test_participants_sorted_by_score(self, clean_orders_dataset):
        entities, table_name, total_cols = clean_orders_dataset
        primary = primary_object_discovery.discover(entities, table_name, total_cols)

        column_naming = {
            "customer_id": 0.95,
            "product_id": 0.95,
        }
        participants = participation_discovery.discover(entities, primary, column_naming)

        for i in range(len(participants) - 1):
            assert participants[i].participation_score >= participants[i + 1].participation_score

    def test_primary_object_not_in_participants(self, clean_orders_dataset):
        entities, table_name, total_cols = clean_orders_dataset
        primary = primary_object_discovery.discover(entities, table_name, total_cols)

        column_naming = {"customer_id": 0.95, "product_id": 0.95}
        participants = participation_discovery.discover(entities, primary, column_naming)

        participant_labels = {p.label for p in participants}
        assert primary.label not in participant_labels

    def test_naming_evidence_fallback_no_explicit_map(self, participation_test_entities):
        """When no column_naming_conf provided, fallback inference should work."""
        entities, table_name, total_cols = participation_test_entities
        primary = primary_object_discovery.discover(entities, table_name, total_cols)

        participants = participation_discovery.discover(entities, primary)

        assert len(participants) > 0
        for p in participants:
            assert p.naming_evidence >= 0.30

    def test_participation_score_bounds(self, participation_test_entities):
        entities, table_name, total_cols = participation_test_entities
        primary = primary_object_discovery.discover(entities, table_name, total_cols)

        column_naming = {"product_id": 0.95, "customer_id": 0.95}
        participants = participation_discovery.discover(entities, primary, column_naming)

        for p in participants:
            assert 0.0 <= p.participation_score <= 1.0
            assert p.participation_score == p.confidence
