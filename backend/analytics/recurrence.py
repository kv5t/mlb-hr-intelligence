"""Window-local recurrence and cutoff-state suffixes over B07 opportunities."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, localcontext
from itertools import groupby
from uuid import UUID

from domain.models import (
    GameDataCoverage,
    HomeRunEvent,
    PlateAppearance,
    PlayerGameParticipation,
)

from .coverage import CoverageGate, assess_hr_integrity, assess_player_pa_integrity
from .values import MetricState, MetricValue
from .windows import CandidateObservation, MembershipState, SelectionResult


@dataclass(frozen=True)
class GapSeries:
    kpi_id: str
    state: MetricState
    values: tuple[int, ...]
    reason: str | None
    hr_game_count: int | None
    gap_count: int | None


@dataclass(frozen=True)
class RecurrenceResult:
    metrics: dict[str, MetricValue]
    gap_series: GapSeries


@dataclass(frozen=True)
class _Observation:
    candidate: CandidateObservation
    gate: CoverageGate
    pa_gate: CoverageGate
    hr_pas: tuple[bool, ...]
    pa_order_unverified: bool

    @property
    def hr_game(self) -> bool:
        return any(self.hr_pas)


def _gate(*gates: CoverageGate) -> CoverageGate:
    for state in (
        MetricState.UNKNOWN,
        MetricState.INCOMPLETE,
        MetricState.ORDER_UNVERIFIED,
    ):
        found = next((item for item in gates if item.state == state), None)
        if found is not None:
            return found
    return CoverageGate(MetricState.VALUE)


def _metric(
    value: int | Decimal,
    unit: str,
    *,
    reason: str | None = None,
    numerator: int | None = None,
    denominator: int | None = None,
) -> MetricValue:
    return MetricValue(
        MetricState.VALUE,
        value=value,
        unit=unit,
        numerator=numerator,
        denominator=denominator,
        reason=reason,
    )


def _unavailable(gate: CoverageGate, unit: str) -> MetricValue:
    return MetricValue(gate.state, unit=unit, reason=gate.reason)


def _no_games(unit: str) -> MetricValue:
    return MetricValue(MetricState.NOT_APPLICABLE, unit=unit, reason="NO_GAMES")


def _groups(observations: list[_Observation]):
    return [
        list(group)
        for _, group in groupby(observations, key=lambda item: item.candidate.order_key)
    ]


def _order_material(group: list[_Observation], *, pa: bool) -> bool:
    if len(group) < 2:
        return False
    if not pa:
        return len({item.hr_game for item in group}) > 1
    signatures = [item.hr_pas for item in group]
    if len(set(signatures)) == 1:
        return False
    # Unequal PA counts still commute when every PA has the same HR state.
    return len({is_hr for signature in signatures for is_hr in signature}) > 1


def _observations(selection: SelectionResult) -> dict[UUID, _Observation]:
    candidates = selection.full_scope_observations
    game_ids = [item.game_id for item in candidates]
    coverage = {
        (row.game_id, row.domain): row
        for row in GameDataCoverage.objects.filter(
            game_id__in=game_ids,
            domain__in=(
                GameDataCoverage.Domain.PLATE_APPEARANCES,
                GameDataCoverage.Domain.HR_EVENTS,
            ),
        )
    }
    all_pas = list(PlateAppearance.objects.filter(game_id__in=game_ids))
    all_events = list(
        HomeRunEvent.objects.filter(
            plate_appearance__game_id__in=game_ids
        ).select_related("plate_appearance")
    )
    pas_by_game: dict[UUID, list[PlateAppearance]] = defaultdict(list)
    events_by_game: dict[UUID, list[HomeRunEvent]] = defaultdict(list)
    for pa in all_pas:
        pas_by_game[pa.game_id].append(pa)
    for event in all_events:
        events_by_game[event.plate_appearance.game_id].append(event)
    row_ids = {
        row_id
        for item in candidates
        if item.entry
        for row_id in item.entry.participation_ids
    }
    rows = {
        row.id: row for row in PlayerGameParticipation.objects.filter(id__in=row_ids)
    }
    result = {}
    for item in candidates:
        if item.known_non_opportunity:
            continue
        if item.membership_state != MembershipState.RESOLVED or item.entry is None:
            state = (
                MetricState.UNKNOWN
                if item.membership_state == MembershipState.UNKNOWN
                else MetricState.INCOMPLETE
            )
            result[item.game_id] = _Observation(
                item, CoverageGate(state), CoverageGate(state), (), False
            )
            continue
        entry = item.entry
        scoped_pas = (
            [
                pa
                for pa in pas_by_game[item.game_id]
                if pa.batting_team_id == selection.subject_id
            ]
            if selection.subject_kind == "TEAM"
            else [
                pa
                for pa in pas_by_game[item.game_id]
                if pa.id in entry.plate_appearance_ids
            ]
        )
        pa_gate = CoverageGate(MetricState.VALUE)
        if selection.subject_kind == "PLAYER":
            expected_ids = set(entry.plate_appearance_ids)
            expected_rows = set(entry.participation_ids)
            if (
                {pa.id for pa in scoped_pas} != expected_ids
                or any(
                    pa.batter_id != selection.subject_id
                    or pa.batting_team_id not in entry.represented_team_ids
                    for pa in scoped_pas
                )
                or not expected_rows.issubset(rows)
                or any(
                    rows[row_id].game_id != item.game_id
                    or rows[row_id].player_id != selection.subject_id
                    or rows[row_id].team_id not in entry.represented_team_ids
                    for row_id in expected_rows
                )
            ):
                pa_gate = CoverageGate(MetricState.INCOMPLETE, "BOX_SCORE_PA_MISMATCH")
            else:
                pa_gate = assess_player_pa_integrity(
                    [rows[row_id] for row_id in expected_rows], scoped_pas
                )
            if entry.uncertain_team_ids:
                pa_gate = _gate(
                    pa_gate,
                    CoverageGate(
                        MetricState.UNKNOWN, "PARTICIPATION_POPULATION_UNVERIFIED"
                    ),
                )
        pa_state = coverage.get(
            (item.game_id, GameDataCoverage.Domain.PLATE_APPEARANCES)
        )
        hr_state = coverage.get((item.game_id, GameDataCoverage.Domain.HR_EVENTS))
        for row in (pa_state, hr_state):
            if row is None or row.state in (
                GameDataCoverage.State.UNKNOWN,
                GameDataCoverage.State.UNAVAILABLE,
            ):
                pa_gate = _gate(
                    pa_gate,
                    CoverageGate(MetricState.UNKNOWN, row.reason_code if row else None),
                )
            elif row.state == GameDataCoverage.State.PARTIAL:
                pa_gate = _gate(
                    pa_gate, CoverageGate(MetricState.INCOMPLETE, row.reason_code)
                )
        integrity = assess_hr_integrity(
            pas_by_game[item.game_id], events_by_game[item.game_id]
        )
        gate = _gate(pa_gate, integrity)
        event_ids = {
            event.plate_appearance_id for event in events_by_game[item.game_id]
        }
        scoped_pas.sort(
            key=lambda pa: (pa.game_pa_ordinal is None, pa.game_pa_ordinal or 0, pa.id)
        )
        hr_pas = tuple(pa.id in event_ids for pa in scoped_pas)
        pa_order_unverified = (
            len(scoped_pas) > 1
            and any(pa.game_pa_ordinal is None for pa in scoped_pas)
            and len(set(hr_pas)) > 1
        )
        result[item.game_id] = _Observation(
            item, gate, pa_gate, hr_pas, pa_order_unverified
        )
    return result


def _window_order_gate(
    observations: list[_Observation], *, pa: bool = False
) -> CoverageGate:
    for group in _groups(observations):
        if _order_material(group, pa=pa):
            return CoverageGate(MetricState.ORDER_UNVERIFIED, "ORDER_UNRESOLVED")
        if pa and any(item.pa_order_unverified for item in group):
            return CoverageGate(MetricState.ORDER_UNVERIFIED, "ORDER_UNRESOLVED")
    return CoverageGate(MetricState.VALUE)


def _current(
    observations: list[_Observation], *, target_hr: bool, pa: bool = False
) -> MetricValue:
    unit = "PA" if pa else "GAMES"
    if not observations:
        return _no_games(unit)
    count = 0
    for group in reversed(_groups(observations)):
        gate = _gate(*(item.gate for item in group))
        if gate.state != MetricState.VALUE:
            return _unavailable(gate, unit)
        if _order_material(group, pa=pa):
            return _unavailable(
                CoverageGate(MetricState.ORDER_UNVERIFIED, "ORDER_UNRESOLVED"), unit
            )
        for item in reversed(group):
            if pa and item.pa_order_unverified:
                return _unavailable(
                    CoverageGate(MetricState.ORDER_UNVERIFIED, "ORDER_UNRESOLVED"), unit
                )
            sequence = reversed(item.hr_pas) if pa else (item.hr_game,)
            for is_hr in sequence:
                if is_hr != target_hr:
                    return _metric(count, unit)
                count += 1
    return _metric(count, unit, reason="NO_HR_IN_SCOPE" if not target_hr else None)


def _calculate(selection: SelectionResult, subject_kind: str) -> RecurrenceResult:
    if selection.subject_kind != subject_kind:
        raise ValueError(
            f"{subject_kind} recurrence requires a {subject_kind} selection"
        )
    prefix = subject_kind.lower()
    observations_by_id = _observations(selection)
    full = [
        observations_by_id[item.game_id]
        for item in selection.full_scope_observations
        if not item.known_non_opportunity
    ]
    window = [observations_by_id[entry.game_id] for entry in selection.entries]
    local_names = (
        "avg_hr_gap_games",
        "median_hr_gap_games",
        "max_hr_drought_games",
        "max_hr_streak_games",
    )
    current_names = ("current_hr_drought_games", "current_hr_streak_games")
    if subject_kind == "PLAYER":
        local_names += ("max_hr_drought_pa",)
        current_names += ("current_hr_drought_pa",)
    units = {
        name: "PA" if name.endswith("_pa") else "GAMES"
        for name in local_names + current_names
    }
    metrics = {}
    selection_gate = {
        MembershipState.UNKNOWN: CoverageGate(MetricState.UNKNOWN),
        MembershipState.INCOMPLETE: CoverageGate(MetricState.INCOMPLETE),
        MembershipState.ORDER_UNVERIFIED: CoverageGate(
            MetricState.ORDER_UNVERIFIED, "ORDER_UNRESOLVED"
        ),
    }.get(selection.membership_state, CoverageGate(MetricState.VALUE))
    local_gate = _gate(selection_gate, *(item.gate for item in window))
    local_gate = (
        _gate(local_gate, _window_order_gate(window))
        if local_gate.state == MetricState.VALUE
        else local_gate
    )
    pa_local_gate = (
        _gate(local_gate, _window_order_gate(window, pa=True))
        if local_gate.state == MetricState.VALUE
        else local_gate
    )
    if local_gate.state != MetricState.VALUE:
        gaps = GapSeries(
            f"{prefix}.hr_gap_games",
            local_gate.state,
            (),
            local_gate.reason,
            None,
            None,
        )
        for name in local_names:
            metrics[f"{prefix}.{name}"] = _unavailable(local_gate, units[name])
    elif not window:
        gaps = GapSeries(
            f"{prefix}.hr_gap_games",
            MetricState.INSUFFICIENT_HISTORY,
            (),
            "INSUFFICIENT_HISTORY",
            0,
            0,
        )
        for name in local_names:
            metrics[f"{prefix}.{name}"] = (
                MetricValue(
                    MetricState.INSUFFICIENT_HISTORY,
                    unit=units[name],
                    reason="INSUFFICIENT_HISTORY",
                )
                if name in ("avg_hr_gap_games", "median_hr_gap_games")
                else _no_games(units[name])
            )
    else:
        indices = [index for index, item in enumerate(window) if item.hr_game]
        gap_values = tuple(
            right - left - 1 for left, right in zip(indices, indices[1:])
        )
        if len(indices) < 2:
            gaps = GapSeries(
                f"{prefix}.hr_gap_games",
                MetricState.INSUFFICIENT_HISTORY,
                (),
                "INSUFFICIENT_HISTORY",
                len(indices),
                0,
            )
            for name in ("avg_hr_gap_games", "median_hr_gap_games"):
                metrics[f"{prefix}.{name}"] = MetricValue(
                    MetricState.INSUFFICIENT_HISTORY,
                    unit="GAMES",
                    reason="INSUFFICIENT_HISTORY",
                )
        else:
            gaps = GapSeries(
                f"{prefix}.hr_gap_games",
                MetricState.VALUE,
                gap_values,
                None,
                len(indices),
                len(gap_values),
            )
            with localcontext() as context:
                context.prec = 50
                mean = Decimal(sum(gap_values)) / Decimal(len(gap_values))
            metrics[f"{prefix}.avg_hr_gap_games"] = _metric(
                mean, "GAMES", numerator=sum(gap_values), denominator=len(gap_values)
            )
            ordered = sorted(gap_values)
            middle = len(ordered) // 2
            if len(ordered) % 2:
                median = ordered[middle]
                metrics[f"{prefix}.median_hr_gap_games"] = _metric(median, "GAMES")
            else:
                numerator = ordered[middle - 1] + ordered[middle]
                metrics[f"{prefix}.median_hr_gap_games"] = _metric(
                    Decimal(numerator) / Decimal(2),
                    "GAMES",
                    numerator=numerator,
                    denominator=2,
                )
        drought = streak = max_drought = max_streak = 0
        for item in window:
            drought, streak = (0, streak + 1) if item.hr_game else (drought + 1, 0)
            max_drought = max(max_drought, drought)
            max_streak = max(max_streak, streak)
        metrics[f"{prefix}.max_hr_drought_games"] = _metric(
            max_drought,
            "GAMES",
            reason="NO_HR_IN_SCOPE" if not indices else None,
            numerator=max_drought,
        )
        metrics[f"{prefix}.max_hr_streak_games"] = _metric(
            max_streak, "GAMES", numerator=max_streak
        )
        if subject_kind == "PLAYER":
            if pa_local_gate.state != MetricState.VALUE:
                metrics[f"{prefix}.max_hr_drought_pa"] = _unavailable(
                    pa_local_gate, "PA"
                )
            else:
                pa_run = pa_max = pa_hr = 0
                for item in window:
                    for is_hr in item.hr_pas:
                        pa_hr += int(is_hr)
                        pa_run = 0 if is_hr else pa_run + 1
                        pa_max = max(pa_max, pa_run)
                metrics[f"{prefix}.max_hr_drought_pa"] = _metric(
                    pa_max,
                    "PA",
                    reason="NO_HR_IN_SCOPE" if pa_hr == 0 else None,
                    numerator=pa_max,
                )
    unknown_date = selection.resolved_cutoff is None or any(
        game_id not in observations_by_id
        for game_id in selection.uncertain_candidate_ids
    )
    if unknown_date:
        current_gate = CoverageGate(MetricState.UNKNOWN)
    else:
        current_gate = CoverageGate(MetricState.VALUE)
    # A game-ID cutoff inside an ID-only tie has no proven terminal member.
    if (
        selection.cutoff_request.kind == "GAME"
        and selection.membership_state == MembershipState.ORDER_UNVERIFIED
    ):
        current_gate = CoverageGate(MetricState.ORDER_UNVERIFIED, "ORDER_UNRESOLVED")
    for name in current_names:
        if current_gate.state != MetricState.VALUE:
            metrics[f"{prefix}.{name}"] = _unavailable(current_gate, units[name])
        elif name == "current_hr_drought_games":
            metrics[f"{prefix}.{name}"] = _current(full, target_hr=False)
        elif name == "current_hr_streak_games":
            metrics[f"{prefix}.{name}"] = _current(full, target_hr=True)
        else:
            metrics[f"{prefix}.{name}"] = _current(full, target_hr=False, pa=True)
    return RecurrenceResult(metrics, gaps)


def compute_team_recurrence(selection: SelectionResult) -> RecurrenceResult:
    return _calculate(selection, "TEAM")


def compute_player_recurrence(selection: SelectionResult) -> RecurrenceResult:
    return _calculate(selection, "PLAYER")
