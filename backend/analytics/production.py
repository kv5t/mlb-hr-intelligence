"""B09 production and frequency KPIs over an already selected game window."""

from collections import defaultdict
from decimal import Decimal, localcontext

from domain.models import GameDataCoverage, HomeRunEvent, PlateAppearance

from .coverage import CoverageGate, assess_hr_integrity, evaluate_selection_coverage
from .values import MetricState, MetricValue
from .windows import MembershipState, SelectionResult

_UNITS = {
    "hr": "HR",
    "pa": "PA",
    "hr_per_pa": "HR/PA",
    "pa_per_hr": "PA/HR",
    "hr_per_game": "HR/GAME",
    "hr_games": "GAMES",
    "hr_game_pct": "PERCENT",
    "multi_hr_games": "GAMES",
}
_PA_DEPENDENT = {"pa", "hr_per_pa", "pa_per_hr"}


def _divide(numerator: int, denominator: int) -> Decimal:
    # Counts stay exact; presentation can round this high-precision ratio later.
    with localcontext() as context:
        context.prec = 50
        return Decimal(numerator) / Decimal(denominator)


def _stronger_gate(*gates: CoverageGate) -> CoverageGate:
    for state in (
        MetricState.UNKNOWN,
        MetricState.INCOMPLETE,
        MetricState.ORDER_UNVERIFIED,
    ):
        match = next((gate for gate in gates if gate.state == state), None)
        if match is not None:
            return match
    return CoverageGate(MetricState.VALUE)


def _unavailable(gate: CoverageGate, unit: str) -> MetricValue:
    return MetricValue(gate.state, unit=unit, reason=gate.reason)


def _value(value: int | Decimal, unit: str, numerator: int, denominator=None):
    return MetricValue(
        MetricState.VALUE,
        value=value,
        unit=unit,
        numerator=numerator,
        denominator=denominator,
    )


def _not_applicable(unit: str, reason: str, numerator: int, denominator: int):
    return MetricValue(
        MetricState.NOT_APPLICABLE,
        unit=unit,
        numerator=numerator,
        denominator=denominator,
        reason=reason,
    )


def _metrics(
    prefix: str,
    *,
    pa_gate: CoverageGate,
    hr_gate: CoverageGate,
    pa_count: int = 0,
    hr_by_game: dict | None = None,
    game_count: int | None = None,
) -> dict[str, MetricValue]:
    combined = _stronger_gate(pa_gate, hr_gate)
    results = {}
    for name, unit in _UNITS.items():
        gate = (
            pa_gate if name == "pa" else combined if name in _PA_DEPENDENT else hr_gate
        )
        if gate.state != MetricState.VALUE:
            results[f"{prefix}.{name}"] = _unavailable(gate, unit)
    if pa_gate.state == MetricState.VALUE:
        results[f"{prefix}.pa"] = _value(pa_count, "PA", pa_count)
    if hr_gate.state != MetricState.VALUE:
        return results

    hr_by_game = hr_by_game or {}
    hr_count = sum(hr_by_game.values())
    hr_games = sum(count >= 1 for count in hr_by_game.values())
    multi_hr_games = sum(count >= 2 for count in hr_by_game.values())
    results[f"{prefix}.hr"] = _value(hr_count, "HR", hr_count)
    results[f"{prefix}.hr_games"] = _value(hr_games, "GAMES", hr_games)
    results[f"{prefix}.multi_hr_games"] = _value(
        multi_hr_games, "GAMES", multi_hr_games
    )
    if game_count is None:
        raise ValueError("Resolved HR metrics require an actual game count")
    if game_count == 0:
        results[f"{prefix}.hr_per_game"] = _not_applicable(
            "HR/GAME", "NO_GAMES", hr_count, 0
        )
        results[f"{prefix}.hr_game_pct"] = _not_applicable(
            "PERCENT", "NO_GAMES", hr_games, 0
        )
    else:
        results[f"{prefix}.hr_per_game"] = _value(
            _divide(hr_count, game_count), "HR/GAME", hr_count, game_count
        )
        results[f"{prefix}.hr_game_pct"] = _value(
            _divide(100 * hr_games, game_count),
            "PERCENT",
            hr_games,
            game_count,
        )

    if combined.state != MetricState.VALUE:
        return results
    if pa_count == 0:
        results[f"{prefix}.hr_per_pa"] = _not_applicable(
            "HR/PA", "ZERO_DENOMINATOR", hr_count, 0
        )
    else:
        results[f"{prefix}.hr_per_pa"] = _value(
            _divide(hr_count, pa_count), "HR/PA", hr_count, pa_count
        )
    if hr_count == 0:
        results[f"{prefix}.pa_per_hr"] = _not_applicable(
            "PA/HR", "NO_HOME_RUNS_IN_SCOPE", pa_count, 0
        )
    else:
        results[f"{prefix}.pa_per_hr"] = _value(
            _divide(pa_count, hr_count), "PA/HR", pa_count, hr_count
        )
    return results


def _validate_selection(selection: SelectionResult, subject_kind: str) -> None:
    if selection.subject_kind != subject_kind:
        raise ValueError(f"{subject_kind} metrics require a {subject_kind} selection")
    if selection.membership_state == MembershipState.RESOLVED and (
        selection.actual_game_count is None
        or selection.actual_game_count != len(selection.entries)
    ):
        raise ValueError("Resolved selection needs its definitive game count")


def _subject_pas(
    selection: SelectionResult,
) -> tuple[list[PlateAppearance], CoverageGate]:
    if selection.subject_kind == "TEAM":
        return (
            list(
                PlateAppearance.objects.filter(
                    game_id__in=[entry.game_id for entry in selection.entries],
                    batting_team_id=selection.subject_id,
                )
            ),
            evaluate_selection_coverage(
                selection, (GameDataCoverage.Domain.PLATE_APPEARANCES,)
            ),
        )
    ids_by_game = {
        entry.game_id: set(entry.plate_appearance_ids) for entry in selection.entries
    }
    represented_teams_by_game = {
        entry.game_id: set(entry.represented_team_ids) for entry in selection.entries
    }
    pa_ids = {pa_id for ids in ids_by_game.values() for pa_id in ids}
    pas = list(PlateAppearance.objects.filter(id__in=pa_ids))
    loaded_ids = {pa.id for pa in pas}
    consistent = loaded_ids == pa_ids and all(
        pa.id in ids_by_game.get(pa.game_id, set())
        and pa.batter_id == selection.subject_id
        and (
            selection.team_filter_id is None
            or pa.batting_team_id == selection.team_filter_id
        )
        and pa.batting_team_id in represented_teams_by_game.get(pa.game_id, set())
        for pa in pas
    )
    if not consistent:
        return pas, CoverageGate(MetricState.INCOMPLETE, "BOX_SCORE_PA_MISMATCH")
    # B07 already required complete PA evidence for each selected player row.
    return pas, CoverageGate(MetricState.VALUE)


def _hr_integrity_and_counts(
    selection: SelectionResult, subject_pas: list[PlateAppearance]
) -> tuple[CoverageGate, dict]:
    game_ids = [entry.game_id for entry in selection.entries]
    all_pas = list(PlateAppearance.objects.filter(game_id__in=game_ids))
    all_events = list(
        HomeRunEvent.objects.filter(
            plate_appearance__game_id__in=game_ids
        ).select_related("plate_appearance")
    )
    pas_by_game: dict = defaultdict(list)
    events_by_game: dict = defaultdict(list)
    for pa in all_pas:
        pas_by_game[pa.game_id].append(pa)
    for event in all_events:
        events_by_game[event.plate_appearance.game_id].append(event)
    for entry in selection.entries:
        integrity = assess_hr_integrity(
            pas_by_game[entry.game_id], events_by_game[entry.game_id]
        )
        if integrity.state != MetricState.VALUE:
            return integrity, {}
    subject_pa_ids = {pa.id for pa in subject_pas}
    hr_by_game: dict = defaultdict(int)
    for event in all_events:
        if event.plate_appearance_id in subject_pa_ids:
            hr_by_game[event.plate_appearance.game_id] += 1
    return CoverageGate(MetricState.VALUE), hr_by_game


def _compute(selection: SelectionResult, subject_kind: str) -> dict[str, MetricValue]:
    _validate_selection(selection, subject_kind)
    prefix = subject_kind.lower()
    selection_gate = evaluate_selection_coverage(
        selection, (GameDataCoverage.Domain.HR_EVENTS,)
    )
    if selection.membership_state != MembershipState.RESOLVED:
        return _metrics(prefix, pa_gate=selection_gate, hr_gate=selection_gate)

    subject_pas, pa_gate = _subject_pas(selection)
    coverage_gate = selection_gate
    if coverage_gate.state == MetricState.VALUE:
        integrity_gate, hr_by_game = _hr_integrity_and_counts(selection, subject_pas)
    else:
        integrity_gate, hr_by_game = CoverageGate(MetricState.VALUE), {}
    hr_gate = _stronger_gate(coverage_gate, integrity_gate, pa_gate)
    return _metrics(
        prefix,
        pa_gate=pa_gate,
        hr_gate=hr_gate,
        pa_count=len(subject_pas),
        hr_by_game=hr_by_game,
        game_count=selection.actual_game_count,
    )


def compute_team_production_metrics(
    selection: SelectionResult,
) -> dict[str, MetricValue]:
    """Calculate eight team KPIs from the exact B07 team-game selection."""
    return _compute(selection, "TEAM")


def compute_player_production_metrics(
    selection: SelectionResult,
) -> dict[str, MetricValue]:
    """Calculate eight player KPIs from exact B07 scoped PA identities."""
    return _compute(selection, "PLAYER")
