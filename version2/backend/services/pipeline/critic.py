import math

from db.schemas_pipeline import ComputeResult, CriticCheck, CriticStatus, PrimitiveType


def _finite(v: float | None) -> bool:
    return v is not None and not math.isnan(v) and not math.isinf(v)


def _check_magnitude_sanity(result: ComputeResult) -> CriticCheck:
    if result.compute_error:
        return CriticCheck(
            name="magnitude_sanity",
            status=CriticStatus.fail,
            detail=result.compute_error,
        )
    if not _finite(result.current_value):
        return CriticCheck(
            name="magnitude_sanity",
            status=CriticStatus.fail,
            detail="Non-finite value",
        )
    return CriticCheck(name="magnitude_sanity", status=CriticStatus.pass_)


def _check_denominator_stable(result: ComputeResult) -> CriticCheck:
    if result.cov is None:
        return CriticCheck(
            name="denominator_stable", status=CriticStatus.pass_, detail="N/A"
        )
    if not _finite(result.cov):
        return CriticCheck(
            name="denominator_stable",
            status=CriticStatus.warning,
            detail="CoV is non-finite — denominator may be near zero",
        )
    if result.cov > 0.5:
        return CriticCheck(
            name="denominator_stable",
            status=CriticStatus.fail,
            detail=f"CoV={result.cov:.2f} exceeds threshold 0.5",
        )
    if result.cov > 0.3:
        return CriticCheck(
            name="denominator_stable",
            status=CriticStatus.warning,
            detail=f"CoV={result.cov:.2f} exceeds warning threshold 0.3",
        )
    return CriticCheck(name="denominator_stable", status=CriticStatus.pass_)


def _check_coverage_adequate(result: ComputeResult) -> CriticCheck:
    if result.coverage_pct < 0.7:
        return CriticCheck(
            name="coverage_adequate",
            status=CriticStatus.fail,
            detail=f"Coverage {result.coverage_pct:.1%} below 70%",
        )
    if result.coverage_pct < 0.9:
        return CriticCheck(
            name="coverage_adequate",
            status=CriticStatus.warning,
            detail=f"Coverage {result.coverage_pct:.1%} below 90%",
        )
    return CriticCheck(name="coverage_adequate", status=CriticStatus.pass_)


def _check_minimum_data(result: ComputeResult) -> CriticCheck:
    if result.row_count < 10:
        return CriticCheck(
            name="minimum_data",
            status=CriticStatus.fail,
            detail=f"Only {result.row_count} rows — unreliable",
        )
    if result.row_count < 30:
        return CriticCheck(
            name="minimum_data",
            status=CriticStatus.warning,
            detail=f"Low row count: {result.row_count}",
        )
    return CriticCheck(name="minimum_data", status=CriticStatus.pass_)


def _check_delta_significance(result: ComputeResult) -> CriticCheck:
    if result.primitive != PrimitiveType.period_delta:
        return CriticCheck(name="delta_significance", status=CriticStatus.pass_, detail="N/A")
    if result.comparison_value is None:
        return CriticCheck(
            name="delta_significance",
            status=CriticStatus.warning,
            detail="No prior period available for comparison",
        )
    if not _finite(result.delta_pct):
        return CriticCheck(
            name="delta_significance",
            status=CriticStatus.warning,
            detail="Delta pct non-finite — prior period may be zero",
        )
    return CriticCheck(name="delta_significance", status=CriticStatus.pass_)


def _check_single(result: ComputeResult) -> ComputeResult:
    checks = [
        _check_magnitude_sanity(result),
        _check_denominator_stable(result),
        _check_coverage_adequate(result),
        _check_minimum_data(result),
        _check_delta_significance(result),
    ]
    return result.model_copy(update={"critic_checks": checks})


def check_all(results: list[ComputeResult]) -> list[ComputeResult]:
    tagged = [_check_single(r) for r in results]

    # Redundancy: flag specs that produce the same value for the same primitive
    seen: dict[str, str] = {}
    final: list[ComputeResult] = []
    for r in tagged:
        sig = (
            f"{r.primitive.value}__{r.current_value:.6f}"
            if _finite(r.current_value)
            else r.primitive.value
        )
        existing = seen.get(sig)
        redundancy = CriticCheck(
            name="redundancy",
            status=CriticStatus.warning if existing else CriticStatus.pass_,
            detail=f"Duplicate of {existing}" if existing else None,
        )
        seen.setdefault(sig, r.kpi_id)
        final.append(r.model_copy(update={"critic_checks": list(r.critic_checks) + [redundancy]}))

    return final
