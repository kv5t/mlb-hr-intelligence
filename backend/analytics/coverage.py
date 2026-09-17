"""Current canonical evidence gates and matrix cell states, without KPI formulas."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from django.db.models import Q

from domain.models import (
    Game,
    GameDataCoverage,
    HomeRunEvent,
    PlateAppearance,
    Player,
    PlayerGameParticipation,
    PlayerTeamAffiliation,
    Team,
)

from .values import MetricState
from .windows import MembershipState, OrderState, SelectionResult


@dataclass(frozen=True)
class CoverageEvidence:
    game_id: UUID
    domain: str
    state: str
    metric_state: MetricState
    reason: str | None = None


@dataclass(frozen=True)
class CoverageGate:
    state: MetricState
    reason: str | None = None
    evidence: tuple[CoverageEvidence, ...] = ()


@dataclass(frozen=True)
class ZeroEvidence:
    state: MetricState
    is_zero: bool | None
    reason: str | None
    observed_hr_event_ids: tuple[UUID, ...]

    def __post_init__(self):
        if (self.state == MetricState.VALUE) != (self.is_zero is not None):
            raise ValueError("Only complete zero evidence may be Boolean")


class MatrixCellState(StrEnum):
    HR_COUNT = "HR_COUNT"
    KNOWN_ZERO = "KNOWN_ZERO"
    DNP = "DNP"
    ZERO_PA_APPEARANCE = "ZERO_PA_APPEARANCE"
    NOT_WITH_TEAM = "NOT_WITH_TEAM"
    UNKNOWN = "UNKNOWN"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class MatrixCellEvidence:
    state: MatrixCellState
    hr_count: int | None = None
    hr_event_ids: tuple[UUID, ...] = ()
    reason: str | None = None

    def __post_init__(self):
        if not isinstance(self.state, MatrixCellState):
            raise ValueError("Invalid matrix cell state")
        if self.state == MatrixCellState.HR_COUNT:
            if (
                not isinstance(self.hr_count, int)
                or isinstance(self.hr_count, bool)
                or self.hr_count < 1
                or len(self.hr_event_ids) != self.hr_count
            ):
                raise ValueError("HR_COUNT requires a positive event count")
        elif self.state == MatrixCellState.KNOWN_ZERO:
            if (
                self.hr_count != 0
                or isinstance(self.hr_count, bool)
                or self.hr_event_ids
            ):
                raise ValueError("KNOWN_ZERO requires numeric zero")
        elif self.hr_count is not None:
            raise ValueError("Unavailable or non-batting cells have no HR count")
        if (
            self.state
            not in (
                MatrixCellState.INCOMPLETE,
                MatrixCellState.UNKNOWN,
                MatrixCellState.HR_COUNT,
            )
            and self.hr_event_ids
        ):
            raise ValueError("Only positive or uncertain HR evidence may carry events")


def _validate_domains(domains):
    allowed = tuple(GameDataCoverage.Domain.values)
    requested = tuple(domains)
    if not requested or any(domain not in allowed for domain in requested):
        raise ValueError("At least one valid coverage domain is required")
    # A current HR completeness assertion depends on current reconciled PA
    # completeness; callers cannot bypass that prerequisite by requesting HR only.
    required = set(requested)
    if GameDataCoverage.Domain.HR_EVENTS in required:
        required.add(GameDataCoverage.Domain.PLATE_APPEARANCES)
    return tuple(domain for domain in allowed if domain in required)


def _evidence(
    game: Game, domain: str, row: GameDataCoverage | None
) -> CoverageEvidence:
    state = row.state if row is not None else GameDataCoverage.State.UNKNOWN
    reason = row.reason_code if row is not None else None
    if (
        state == GameDataCoverage.State.COMPLETE
        and domain
        in (
            GameDataCoverage.Domain.PLATE_APPEARANCES,
            GameDataCoverage.Domain.HR_EVENTS,
        )
        and game.finality != Game.Finality.FINAL
    ):
        return CoverageEvidence(
            game.id, domain, state, MetricState.UNKNOWN, "FINALITY_UNKNOWN"
        )
    metric_state = {
        GameDataCoverage.State.COMPLETE: MetricState.VALUE,
        GameDataCoverage.State.PARTIAL: MetricState.INCOMPLETE,
        GameDataCoverage.State.UNKNOWN: MetricState.UNKNOWN,
        GameDataCoverage.State.UNAVAILABLE: MetricState.UNKNOWN,
    }[state]
    return CoverageEvidence(game.id, domain, state, metric_state, reason)


def _gate(
    evidence: tuple[CoverageEvidence, ...], order_unverified=False
) -> CoverageGate:
    # Unknown/unavailable dominates partial evidence; neither becomes zero.
    for state in (MetricState.UNKNOWN, MetricState.INCOMPLETE):
        first = next((item for item in evidence if item.metric_state == state), None)
        if first is not None:
            return CoverageGate(state, first.reason, evidence)
    if order_unverified:
        return CoverageGate(MetricState.ORDER_UNVERIFIED, "ORDER_UNRESOLVED", evidence)
    return CoverageGate(MetricState.VALUE, evidence=evidence)


def evaluate_game_coverage(game: Game, domains) -> CoverageGate:
    """Read current per-domain assessments; rows and finality are separate proof."""
    required = _validate_domains(domains)
    rows = {
        row.domain: row
        for row in GameDataCoverage.objects.filter(game=game, domain__in=required)
    }
    return _gate(
        tuple(_evidence(game, domain, rows.get(domain)) for domain in required)
    )


def evaluate_selection_coverage(
    selection: SelectionResult, domains, *, order_sensitive: bool = False
) -> CoverageGate:
    """Gate selected games in bulk; selection uncertainty precedes computation."""
    required = _validate_domains(domains)
    selection_state = {
        MembershipState.UNKNOWN: MetricState.UNKNOWN,
        MembershipState.INCOMPLETE: MetricState.INCOMPLETE,
        MembershipState.ORDER_UNVERIFIED: MetricState.ORDER_UNVERIFIED,
    }.get(selection.membership_state)
    if selection_state is not None:
        return CoverageGate(
            selection_state,
            "ORDER_UNRESOLVED"
            if selection_state == MetricState.ORDER_UNVERIFIED
            else None,
        )
    games = {
        game.id: game
        for game in Game.objects.filter(
            id__in=[entry.game_id for entry in selection.entries]
        )
    }
    rows = {
        (row.game_id, row.domain): row
        for row in GameDataCoverage.objects.filter(
            game_id__in=games, domain__in=required
        )
    }
    evidence = tuple(
        _evidence(games[entry.game_id], domain, rows.get((entry.game_id, domain)))
        for entry in selection.entries
        for domain in required
    )
    return _gate(
        evidence,
        order_unverified=order_sensitive
        and selection.order_state != OrderState.VERIFIED,
    )


def assess_hr_integrity(
    pas: list[PlateAppearance], events: list[HomeRunEvent]
) -> CoverageGate:
    """Check canonical HR PA/event identity and outcome consistency in one scope."""
    hr_pa_ids = {
        pa.id for pa in pas if pa.outcome_category == PlateAppearance.Outcome.HOME_RUN
    }
    event_pa_ids = {event.plate_appearance_id for event in events}
    if hr_pa_ids != event_pa_ids or any(
        pa.outcome_category == PlateAppearance.Outcome.UNKNOWN for pa in pas
    ):
        return CoverageGate(MetricState.INCOMPLETE, "BOX_SCORE_HR_MISMATCH")
    return CoverageGate(MetricState.VALUE)


def assess_player_pa_integrity(
    rows: list[PlayerGameParticipation], pas: list[PlateAppearance]
) -> CoverageGate:
    """Reconcile known reported counts with canonical PAs per represented team."""
    counts: dict[tuple[UUID, UUID, UUID], int] = {}
    for pa in pas:
        key = (pa.game_id, pa.batter_id, pa.batting_team_id)
        counts[key] = counts.get(key, 0) + 1
    for row in rows:
        if (
            row.pa_coverage == PlayerGameParticipation.Coverage.COMPLETE
            and row.reported_pa_count is not None
            and row.reported_pa_count
            != counts.get((row.game_id, row.player_id, row.team_id), 0)
        ):
            return CoverageGate(MetricState.INCOMPLETE, "BOX_SCORE_PA_MISMATCH")
    return CoverageGate(MetricState.VALUE)


def assess_hr_zero(
    game: Game, *, team: Team | None = None, player: Player | None = None
) -> ZeroEvidence:
    """Prove game, represented-team or player HR absence without a KPI total."""
    if team is not None and team.id not in (game.home_team_id, game.away_team_id):
        raise ValueError("Team must participate in the game")
    if player is not None:
        if team is None:
            raise ValueError("Player zero proof requires represented team")
        cell = resolve_matrix_cell(game, player, team)
        if cell.state == MatrixCellState.KNOWN_ZERO:
            return ZeroEvidence(MetricState.VALUE, True, None, ())
        if cell.state == MatrixCellState.HR_COUNT:
            return ZeroEvidence(MetricState.VALUE, False, None, cell.hr_event_ids)
        state = {
            MatrixCellState.INCOMPLETE: MetricState.INCOMPLETE,
            MatrixCellState.UNKNOWN: MetricState.UNKNOWN,
        }.get(cell.state, MetricState.NOT_APPLICABLE)
        return ZeroEvidence(state, None, cell.reason, cell.hr_event_ids)
    event_rows = list(
        HomeRunEvent.objects.filter(plate_appearance__game=game)
        .select_related("plate_appearance")
        .order_by("id")
    )
    scoped_events = [
        event
        for event in event_rows
        if team is None or event.plate_appearance.batting_team_id == team.id
    ]
    events = tuple(event.id for event in scoped_events)
    gate = evaluate_game_coverage(
        game,
        (GameDataCoverage.Domain.PLATE_APPEARANCES, GameDataCoverage.Domain.HR_EVENTS),
    )
    if gate.state != MetricState.VALUE:
        return ZeroEvidence(gate.state, None, gate.reason, events)
    integrity = assess_hr_integrity(
        list(PlateAppearance.objects.filter(game=game)), event_rows
    )
    if integrity.state != MetricState.VALUE:
        return ZeroEvidence(integrity.state, None, integrity.reason, events)
    return ZeroEvidence(MetricState.VALUE, not events, None, events)


def assess_game_hr_zero(game: Game) -> ZeroEvidence:
    """Compatibility spelling for a whole-game zero proof."""
    return assess_hr_zero(game)


def _affirmatively_not_with_team(game: Game, player: Player, team: Team) -> bool:
    """Require a precise departure and a dated different-team affiliation.

    One appearance elsewhere, absent rows or current metadata never suffices.
    A positive game-specific row/PA is checked before this temporal fallback.
    """
    if game.official_date is None:
        return False
    affiliations = list(
        PlayerTeamAffiliation.objects.filter(player=player).filter(
            Q(season=game.season) | Q(season__isnull=True)
        )
    )
    day = game.official_date
    if any(
        row.team_id == team.id
        and (
            row.boundary_precision != PlayerTeamAffiliation.BoundaryPrecision.DATE
            or (
                (row.effective_from_date is None or row.effective_from_date <= day)
                and (
                    row.effective_to_date_exclusive is None
                    or day < row.effective_to_date_exclusive
                )
            )
        )
        for row in affiliations
    ):
        return False
    departed = any(
        row.team_id == team.id
        and row.boundary_precision == PlayerTeamAffiliation.BoundaryPrecision.DATE
        and row.effective_to_date_exclusive is not None
        and row.effective_to_date_exclusive <= day
        for row in affiliations
    )
    with_other_team = any(
        row.team_id != team.id
        and row.boundary_precision == PlayerTeamAffiliation.BoundaryPrecision.DATE
        and row.effective_from_date is not None
        and row.effective_from_date <= day
        and (
            row.effective_to_date_exclusive is None
            or day < row.effective_to_date_exclusive
        )
        for row in affiliations
    )
    return departed and with_other_team


def resolve_matrix_cell(game: Game, player: Player, team: Team) -> MatrixCellEvidence:
    """Resolve one team-game cell from affirmative participation and current proof."""
    if team.id not in (game.home_team_id, game.away_team_id):
        raise ValueError("Matrix team must participate in the game")
    row = PlayerGameParticipation.objects.filter(
        game=game, player=player, team=team
    ).first()
    pas = list(
        PlateAppearance.objects.filter(game=game, batter=player, batting_team=team)
    )
    events = list(
        HomeRunEvent.objects.filter(plate_appearance_id__in=[pa.id for pa in pas])
    )
    event_ids = tuple(sorted(event.id for event in events))
    if (
        row is not None
        and row.participation_state == PlayerGameParticipation.State.DID_NOT_APPEAR
    ):
        if pas:
            return MatrixCellEvidence(
                MatrixCellState.INCOMPLETE,
                hr_event_ids=event_ids,
                reason="TEAM_ATTRIBUTION_CONFLICT",
            )
        return MatrixCellEvidence(MatrixCellState.DNP)
    if row is None:
        if pas:
            return MatrixCellEvidence(
                MatrixCellState.INCOMPLETE,
                hr_event_ids=event_ids,
                reason="PARTICIPATION_POPULATION_UNVERIFIED",
            )
        if _affirmatively_not_with_team(game, player, team):
            return MatrixCellEvidence(MatrixCellState.NOT_WITH_TEAM)
        participation = evaluate_game_coverage(
            game, (GameDataCoverage.Domain.PARTICIPATION,)
        )
        state = (
            MatrixCellState.INCOMPLETE
            if participation.state == MetricState.INCOMPLETE
            else MatrixCellState.UNKNOWN
        )
        return MatrixCellEvidence(state, reason=participation.reason)
    if row.participation_state != PlayerGameParticipation.State.APPEARED:
        if pas:
            return MatrixCellEvidence(
                MatrixCellState.INCOMPLETE,
                hr_event_ids=event_ids,
                reason="TEAM_ATTRIBUTION_CONFLICT",
            )
        return MatrixCellEvidence(MatrixCellState.UNKNOWN)
    gate = evaluate_game_coverage(
        game,
        (GameDataCoverage.Domain.PLATE_APPEARANCES, GameDataCoverage.Domain.HR_EVENTS),
    )
    if gate.state == MetricState.UNKNOWN:
        return MatrixCellEvidence(
            MatrixCellState.UNKNOWN, hr_event_ids=event_ids, reason=gate.reason
        )
    if row.pa_coverage not in (
        PlayerGameParticipation.Coverage.COMPLETE,
        PlayerGameParticipation.Coverage.PARTIAL,
    ):
        return MatrixCellEvidence(MatrixCellState.UNKNOWN, hr_event_ids=event_ids)
    if (
        gate.state == MetricState.INCOMPLETE
        or row.pa_coverage == PlayerGameParticipation.Coverage.PARTIAL
    ):
        return MatrixCellEvidence(
            MatrixCellState.INCOMPLETE, hr_event_ids=event_ids, reason=gate.reason
        )
    pa_integrity = assess_player_pa_integrity([row], pas)
    if pa_integrity.state != MetricState.VALUE:
        return MatrixCellEvidence(
            MatrixCellState.INCOMPLETE,
            hr_event_ids=event_ids,
            reason=pa_integrity.reason,
        )
    integrity = assess_hr_integrity(pas, events)
    if integrity.state != MetricState.VALUE:
        return MatrixCellEvidence(
            MatrixCellState.INCOMPLETE,
            hr_event_ids=event_ids,
            reason=integrity.reason,
        )
    if not pas:
        return MatrixCellEvidence(MatrixCellState.ZERO_PA_APPEARANCE)
    if events:
        return MatrixCellEvidence(MatrixCellState.HR_COUNT, len(events), event_ids)
    return MatrixCellEvidence(MatrixCellState.KNOWN_ZERO, 0)
