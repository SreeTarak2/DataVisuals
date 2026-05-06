from db.schemas_pipeline import (
    ComparisonType,
    DatasetProfile,
    PrimitiveSpec,
    PrimitiveType,
    TimeGrain,
)


def _pick_grain(date_range_days: int | None) -> TimeGrain:
    if date_range_days is None or date_range_days >= 365:
        return TimeGrain.month
    if date_range_days >= 90:
        return TimeGrain.week
    return TimeGrain.day


def _pick_comparison(date_range_days: int | None) -> ComparisonType:
    if date_range_days is None or date_range_days < 14:
        return ComparisonType.none
    if date_range_days >= 730:
        return ComparisonType.prior_year
    return ComparisonType.prior_period


def classify(profile: DatasetProfile) -> list[PrimitiveSpec]:
    s = profile.structures
    grain = _pick_grain(profile.date_range_days)
    comparison = _pick_comparison(profile.date_range_days)
    specs: list[PrimitiveSpec] = []

    # coverage_quality — always runs when there is a time column
    if s.has_time and s.has_measure:
        specs.append(PrimitiveSpec(
            primitive=PrimitiveType.coverage_quality,
            kpi_id=f"coverage_quality__{s.time_cols[0]}__{s.measure_cols[0]}",
            measure_col=s.measure_cols[0],
            time_col=s.time_cols[0],
        ))

    # entity_concentration — entity_id + measure
    if s.has_entity_id and s.has_measure:
        for entity_col in s.entity_cols[:2]:
            for measure_col in s.measure_cols[:2]:
                specs.append(PrimitiveSpec(
                    primitive=PrimitiveType.entity_concentration,
                    kpi_id=f"entity_concentration__{entity_col}__{measure_col}",
                    entity_col=entity_col,
                    measure_col=measure_col,
                    time_col=s.time_cols[0] if s.time_cols else None,
                    comparison=comparison if s.time_cols else ComparisonType.none,
                ))

    # period_delta — measure + time
    if s.has_measure and s.has_time:
        for measure_col in s.measure_cols[:3]:
            specs.append(PrimitiveSpec(
                primitive=PrimitiveType.period_delta,
                kpi_id=f"period_delta__{measure_col}__{grain.value}",
                measure_col=measure_col,
                time_col=s.time_cols[0],
                grain=grain,
                comparison=comparison,
            ))

    # segment_mix — dimension + measure
    if s.has_dimension and s.has_measure:
        for dim_col in s.dimension_cols[:3]:
            for measure_col in s.measure_cols[:2]:
                specs.append(PrimitiveSpec(
                    primitive=PrimitiveType.segment_mix,
                    kpi_id=f"segment_mix__{dim_col}__{measure_col}",
                    dimension_col=dim_col,
                    measure_col=measure_col,
                ))

    # trend_stability — measure + time + ≥14 days
    if s.has_measure and s.has_time and (profile.date_range_days or 0) >= 14:
        for measure_col in s.measure_cols[:2]:
            specs.append(PrimitiveSpec(
                primitive=PrimitiveType.trend_stability,
                kpi_id=f"trend_stability__{measure_col}__{grain.value}",
                measure_col=measure_col,
                time_col=s.time_cols[0],
                grain=grain,
            ))

    # cohort_behavior — entity_id + time + transaction grain (repeat rows per entity)
    if s.has_entity_id and s.has_time and profile.grain == "transaction":
        for entity_col in s.entity_cols[:1]:
            for measure_col in s.measure_cols[:1]:
                specs.append(PrimitiveSpec(
                    primitive=PrimitiveType.cohort_behavior,
                    kpi_id=f"cohort_behavior__{entity_col}__{measure_col}",
                    entity_col=entity_col,
                    measure_col=measure_col,
                    time_col=s.time_cols[0],
                ))

    # anomaly_detection — measure + time + ≥90 days
    if s.has_measure and s.has_time and (profile.date_range_days or 0) >= 90:
        for measure_col in s.measure_cols[:2]:
            specs.append(PrimitiveSpec(
                primitive=PrimitiveType.anomaly_detection,
                kpi_id=f"anomaly_detection__{measure_col}__{grain.value}",
                measure_col=measure_col,
                time_col=s.time_cols[0],
                grain=grain,
            ))

    return specs
