"""Deterministic game/opportunity selection without KPI or HR coverage logic."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum
from uuid import UUID

from django.db.models import Q

from domain.models import (
    Game,
    GameDataCoverage,
    PlateAppearance,
    Player,
    PlayerGameParticipation,
    PlayerTeamAffiliation,
    Season,
    Team,
)


class SelectionError(ValueError):
    """Deterministic input error; B11 will map its code to an HTTP error."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class MembershipState(StrEnum):
    RESOLVED = "RESOLVED"
    UNKNOWN = "UNKNOWN"
    INCOMPLETE = "INCOMPLETE"
    ORDER_UNVERIFIED = "ORDER_UNVERIFIED"


class OrderState(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"


class CutoffKind(StrEnum):
    LATEST = "LATEST"
    DATE = "DATE"
    GAME = "GAME"


@dataclass(frozen=True)
class Cutoff:
    kind: CutoffKind
    official_date: date | None = None
    game_id: UUID | None = None

    @classmethod
    def latest(cls):
        return cls(CutoffKind.LATEST)

    @classmethod
    def on_date(cls, value: date):
        if isinstance(value, datetime) or not isinstance(value, date):
            raise SelectionError("INVALID_CUTOFF")
        return cls(CutoffKind.DATE, official_date=value)

    @classmethod
    def through_game(cls, value: UUID):
        if not isinstance(value, UUID):
            raise SelectionError("INVALID_CUTOFF")
        return cls(CutoffKind.GAME, game_id=value)


@dataclass(frozen=True)
class SelectionEntry:
    game_id: UUID
    official_date: date
    represented_team_ids: tuple[UUID, ...]
    participation_ids: tuple[UUID, ...] = ()
    plate_appearance_ids: tuple[UUID, ...] = ()
    uncertain_team_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class SelectionResult:
    subject_kind: str
    subject_id: UUID
    season_id: UUID
    season_year: int
    window: str
    requested_n: int | None
    team_filter_id: UUID | None
    home_away: str
    cutoff_request: Cutoff
    resolved_cutoff: Cutoff | None
    membership_state: MembershipState
    order_state: OrderState
    entries: tuple[SelectionEntry, ...]
    known_core_entries: tuple[SelectionEntry, ...]
    known_eligible_game_count: int
    actual_game_count: int | None
    ambiguous_candidate_ids: tuple[UUID, ...]
    uncertain_candidate_ids: tuple[UUID, ...]
    unverified_order_groups: tuple[tuple[UUID, ...], ...]


WINDOW_SIZES = {"7G": 7, "15G": 15, "30G": 30, "60G": 60, "SEASON": None}
HOME_AWAY = {"ALL", "HOME", "AWAY"}


def _resolve_season(value: Season | int) -> Season:
    if isinstance(value, Season):
        season = Season.objects.filter(pk=value.pk).first()
    elif isinstance(value, int) and not isinstance(value, bool):
        season = Season.objects.filter(year=value).first()
    else:
        season = None
    if season is None:
        raise SelectionError("SEASON_NOT_FOUND")
    return season


def _resolve_entity(model, value, code):
    try:
        pk = value.pk if isinstance(value, model) else UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise SelectionError(code) from None
    entity = model.objects.filter(pk=pk).first()
    if entity is None:
        raise SelectionError(code)
    return entity


def _parse_cutoff(value: Cutoff | str | date | UUID) -> Cutoff:
    if isinstance(value, Cutoff):
        if (
            value.kind == CutoffKind.LATEST
            and value.official_date is None
            and value.game_id is None
        ):
            return value
        if (
            value.kind == CutoffKind.DATE
            and value.official_date
            and value.game_id is None
        ):
            return Cutoff.on_date(value.official_date)
        if (
            value.kind == CutoffKind.GAME
            and value.game_id
            and value.official_date is None
        ):
            return Cutoff.through_game(value.game_id)
        raise SelectionError("INVALID_CUTOFF")
    if value == "LATEST":
        return Cutoff.latest()
    if isinstance(value, UUID):
        return Cutoff.through_game(value)
    if isinstance(value, date) and not isinstance(value, datetime):
        return Cutoff.on_date(value)
    if isinstance(value, str):
        try:
            if len(value) == 10:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() == value:
                    return Cutoff.on_date(parsed)
            return Cutoff.through_game(UUID(value))
        except ValueError:
            pass
    raise SelectionError("INVALID_CUTOFF")


def _validate_scope(window: str, home_away: str) -> int | None:
    if not isinstance(window, str) or window not in WINDOW_SIZES:
        raise SelectionError("INVALID_WINDOW")
    if not isinstance(home_away, str) or home_away not in HOME_AWAY:
        raise SelectionError("INVALID_HOME_AWAY")
    return WINDOW_SIZES[window]


def _start_key(game: Game):
    instant = game.scheduled_start_at_utc or game.actual_start_at_utc
    return (instant is None, instant or datetime.max.replace(tzinfo=timezone.utc))


def _meaningful_order_key(game: Game):
    return (
        game.official_date,
        game.scheduled_game_number is None,
        game.scheduled_game_number if game.scheduled_game_number is not None else 0,
        *_start_key(game),
    )


def _order_key(game: Game):
    return (*_meaningful_order_key(game), game.id)


def _anchor_games(season: Season, team_id: UUID | None) -> list[Game]:
    query = Game.objects.filter(
        season=season,
        game_type=Game.Type.REGULAR,
        finality=Game.Finality.FINAL,
    )
    if team_id is not None:
        query = query.filter(Q(home_team_id=team_id) | Q(away_team_id=team_id))
    return list(query)


def _resolve_cutoff(
    request: Cutoff, season: Season, anchors: list[Game]
) -> tuple[Cutoff | None, Game | None]:
    known_dates = [game.official_date for game in anchors if game.official_date]
    has_unknown_date = any(game.official_date is None for game in anchors)
    if request.kind == CutoffKind.LATEST:
        if not anchors:
            raise SelectionError("NO_FINAL_REGULAR_GAME")
        if not known_dates:
            return None, None
        return Cutoff.on_date(max(known_dates)), None
    if request.kind == CutoffKind.DATE:
        if known_dates and not has_unknown_date:
            if request.official_date < min(known_dates):
                raise SelectionError("CUTOFF_BEFORE_SCOPE")
            if request.official_date > max(known_dates):
                raise SelectionError("CUTOFF_AFTER_SCOPE")
        elif not anchors:
            raise SelectionError("NO_FINAL_REGULAR_GAME")
        return request, None
    game = Game.objects.filter(pk=request.game_id).first()
    if game is None:
        raise SelectionError("CUTOFF_GAME_NOT_FOUND")
    if game.season_id != season.id:
        raise SelectionError("CUTOFF_WRONG_SEASON")
    if game.game_type != Game.Type.REGULAR or game.finality != Game.Finality.FINAL:
        raise SelectionError("CUTOFF_GAME_INELIGIBLE")
    if game.id not in {candidate.id for candidate in anchors}:
        raise SelectionError("CUTOFF_GAME_OUTSIDE_SCOPE")
    if game.official_date is None:
        raise SelectionError("CUTOFF_GAME_DATE_UNKNOWN")
    return request, game


def _through_cutoff(
    game: Game, resolved: Cutoff | None, cutoff_game: Game | None
) -> bool:
    if game.official_date is None or resolved is None:
        return False
    if resolved.kind == CutoffKind.DATE:
        return game.official_date <= resolved.official_date
    # Include the whole meaningful tie here. _finish reports cutoff ambiguity;
    # UUID is only a display tie-break, never evidence of baseball order.
    return _meaningful_order_key(game) <= _meaningful_order_key(cutoff_game)


def _cutoff_tie_ids(
    scoped_games: list[Game], resolved: Cutoff | None, cutoff_game: Game | None
) -> tuple[UUID, ...]:
    if resolved is None or resolved.kind != CutoffKind.GAME:
        return ()
    tied = [
        game.id
        for game in scoped_games
        if _meaningful_order_key(game) == _meaningful_order_key(cutoff_game)
    ]
    return tuple(sorted(tied)) if len(tied) > 1 else ()


def _unverified_groups(games: list[Game]) -> tuple[tuple[UUID, ...], ...]:
    groups: dict[tuple, list[UUID]] = defaultdict(list)
    for game in games:
        groups[_meaningful_order_key(game)].append(game.id)
    return tuple(tuple(sorted(ids)) for ids in groups.values() if len(ids) > 1)


def _lower_bound(requested_n: int | None, known_count: int) -> int:
    return known_count if requested_n is None else min(requested_n, known_count)


def _finish(
    *,
    subject_kind: str,
    subject_id: UUID,
    season: Season,
    window: str,
    requested_n: int | None,
    team_filter_id: UUID | None,
    home_away: str,
    cutoff_request: Cutoff,
    resolved_cutoff: Cutoff | None,
    qualified: list[tuple[Game, SelectionEntry]],
    uncertain: list[tuple[Game, MembershipState]],
    unknown_date_ids: tuple[UUID, ...],
    cutoff_tie_ids: tuple[UUID, ...],
    cutoff_game_id: UUID | None,
) -> SelectionResult:
    qualified.sort(key=lambda pair: _order_key(pair[0]))
    known_games = [game for game, _ in qualified]
    known_count = _lower_bound(requested_n, len(qualified))
    relevant_uncertain: list[tuple[Game, MembershipState]] = []
    if requested_n is None or len(qualified) < requested_n:
        relevant_uncertain = uncertain
    elif uncertain:
        boundary = _meaningful_order_key(qualified[-requested_n][0])
        relevant_uncertain = [
            (game, state)
            for game, state in uncertain
            if _meaningful_order_key(game) >= boundary
        ]
    uncertain_ids = tuple(
        sorted(set(unknown_date_ids) | {game.id for game, _ in relevant_uncertain})
    )
    if unknown_date_ids or relevant_uncertain or resolved_cutoff is None:
        known_order_groups = _unverified_groups(known_games)
        membership = (
            MembershipState.UNKNOWN
            if unknown_date_ids
            or any(state == MembershipState.UNKNOWN for _, state in relevant_uncertain)
            else MembershipState.INCOMPLETE
        )
        return SelectionResult(
            subject_kind,
            subject_id,
            season.id,
            season.year,
            window,
            requested_n,
            team_filter_id,
            home_away,
            cutoff_request,
            resolved_cutoff,
            membership,
            (
                OrderState.UNKNOWN
                if unknown_date_ids
                else OrderState.UNVERIFIED
                if known_order_groups
                else OrderState.VERIFIED
            ),
            (),
            (),
            known_count,
            None,
            (),
            uncertain_ids,
            known_order_groups,
        )

    cutoff_tie = set(cutoff_tie_ids)
    if cutoff_tie:
        relevant_tie = cutoff_tie & (
            {game.id for game, _ in qualified} | {game.id for game, _ in uncertain}
        )
        if relevant_tie - {cutoff_game_id}:
            # Only games strictly before the tie are certain to be through this
            # game cutoff. A rolling suffix has no guaranteed core here.
            before_tie = [
                entry for game, entry in qualified if game.id not in cutoff_tie
            ]
            core = tuple(before_tie) if requested_n is None else ()
            lower_bound = _lower_bound(
                requested_n,
                len(before_tie)
                + int(cutoff_game_id in {game.id for game in known_games}),
            )
            return SelectionResult(
                subject_kind,
                subject_id,
                season.id,
                season.year,
                window,
                requested_n,
                team_filter_id,
                home_away,
                cutoff_request,
                resolved_cutoff,
                MembershipState.ORDER_UNVERIFIED,
                OrderState.UNVERIFIED,
                (),
                core,
                lower_bound,
                None,
                cutoff_tie_ids,
                (),
                (cutoff_tie_ids,),
            )

    selected = qualified if requested_n is None else qualified[-requested_n:]
    selected_games = [game for game, _ in selected]
    selected_entries = tuple(entry for _, entry in selected)
    groups = _unverified_groups(selected_games)
    if requested_n is not None and len(qualified) > requested_n:
        first_selected = qualified[-requested_n][0]
        previous = qualified[-requested_n - 1][0]
        if _meaningful_order_key(first_selected) == _meaningful_order_key(previous):
            tie_key = _meaningful_order_key(first_selected)
            boundary_ids = tuple(
                game.id
                for game in known_games
                if _meaningful_order_key(game) == tie_key
            )
            core = tuple(
                entry
                for game, entry in selected
                if _meaningful_order_key(game) > tie_key
            )
            return SelectionResult(
                subject_kind,
                subject_id,
                season.id,
                season.year,
                window,
                requested_n,
                team_filter_id,
                home_away,
                cutoff_request,
                resolved_cutoff,
                MembershipState.ORDER_UNVERIFIED,
                OrderState.UNVERIFIED,
                (),
                core,
                known_count,
                None,
                boundary_ids,
                (),
                (boundary_ids,),
            )
    return SelectionResult(
        subject_kind,
        subject_id,
        season.id,
        season.year,
        window,
        requested_n,
        team_filter_id,
        home_away,
        cutoff_request,
        resolved_cutoff,
        MembershipState.RESOLVED,
        OrderState.UNVERIFIED if groups else OrderState.VERIFIED,
        selected_entries,
        selected_entries,
        len(selected_entries),
        len(selected_entries),
        (),
        (),
        groups,
    )


def select_team_window(
    *,
    season: Season | int,
    team: Team | UUID,
    window: str = "SEASON",
    cutoff: Cutoff | str | date | UUID = "LATEST",
    home_away: str = "ALL",
) -> SelectionResult:
    """Select final regular team games; PA/HR completeness never affects membership."""
    requested_n = _validate_scope(window, home_away)
    season = _resolve_season(season)
    team = _resolve_entity(Team, team, "TEAM_NOT_FOUND")
    cutoff_request = _parse_cutoff(cutoff)
    anchors = _anchor_games(season, team.id)
    resolved_cutoff, cutoff_game = _resolve_cutoff(cutoff_request, season, anchors)
    scoped = [
        game
        for game in anchors
        if home_away == "ALL"
        or (home_away == "HOME" and game.home_team_id == team.id)
        or (home_away == "AWAY" and game.away_team_id == team.id)
    ]
    if cutoff_game is not None and cutoff_game.id not in {game.id for game in scoped}:
        raise SelectionError("CUTOFF_GAME_OUTSIDE_SCOPE")
    unknown_date_ids = tuple(
        sorted(game.id for game in scoped if game.official_date is None)
    )
    known = [
        game for game in scoped if _through_cutoff(game, resolved_cutoff, cutoff_game)
    ]
    cutoff_tie_ids = _cutoff_tie_ids(scoped, resolved_cutoff, cutoff_game)
    return _finish(
        subject_kind="TEAM",
        subject_id=team.id,
        season=season,
        window=window,
        requested_n=requested_n,
        team_filter_id=None,
        home_away=home_away,
        cutoff_request=cutoff_request,
        resolved_cutoff=resolved_cutoff,
        qualified=[
            (game, SelectionEntry(game.id, game.official_date, (team.id,)))
            for game in known
        ],
        uncertain=[],
        unknown_date_ids=unknown_date_ids,
        cutoff_tie_ids=cutoff_tie_ids,
        cutoff_game_id=cutoff_game.id if cutoff_game else None,
    )


def _player_game_evidence(
    game: Game,
    team_ids: tuple[UUID, ...],
    participation_rows: dict[tuple[UUID, UUID], PlayerGameParticipation],
    pa_rows: dict[tuple[UUID, UUID], list[PlateAppearance]],
    participation_coverage: dict[UUID, str],
) -> tuple[SelectionEntry | None, MembershipState | None]:
    qualifying_rows: list[PlayerGameParticipation] = []
    qualifying_pas: list[PlateAppearance] = []
    uncertain_teams: list[UUID] = []
    possible_states: list[MembershipState] = []
    for team_id in team_ids:
        row = participation_rows.get((game.id, team_id))
        pas = pa_rows.get((game.id, team_id), [])
        if row is None:
            if pas:
                uncertain_teams.append(team_id)
                possible_states.append(MembershipState.INCOMPLETE)
            elif participation_coverage.get(game.id) == GameDataCoverage.State.COMPLETE:
                continue
            else:
                uncertain_teams.append(team_id)
                possible_states.append(
                    MembershipState.INCOMPLETE
                    if participation_coverage.get(game.id)
                    == GameDataCoverage.State.PARTIAL
                    else MembershipState.UNKNOWN
                )
        elif row.participation_state == PlayerGameParticipation.State.DID_NOT_APPEAR:
            continue
        elif row.participation_state == PlayerGameParticipation.State.UNKNOWN:
            uncertain_teams.append(team_id)
            possible_states.append(MembershipState.UNKNOWN)
        elif row.pa_coverage == PlayerGameParticipation.Coverage.PARTIAL:
            uncertain_teams.append(team_id)
            possible_states.append(MembershipState.INCOMPLETE)
        elif row.pa_coverage != PlayerGameParticipation.Coverage.COMPLETE:
            uncertain_teams.append(team_id)
            possible_states.append(MembershipState.UNKNOWN)
        elif pas:
            qualifying_rows.append(row)
            qualifying_pas.extend(pas)
        # APPEARED + complete PA coverage + no PA is a known non-opportunity.

    if qualifying_rows:
        qualifying_pas.sort(
            key=lambda pa: (pa.game_pa_ordinal is None, pa.game_pa_ordinal or 0, pa.id)
        )
        return (
            SelectionEntry(
                game.id,
                game.official_date,
                tuple(row.team_id for row in qualifying_rows),
                tuple(row.id for row in qualifying_rows),
                tuple(pa.id for pa in qualifying_pas),
                tuple(uncertain_teams),
            ),
            None,
        )
    if possible_states:
        state = (
            MembershipState.UNKNOWN
            if MembershipState.UNKNOWN in possible_states
            else MembershipState.INCOMPLETE
        )
        return None, state
    return None, None


def _affiliation_may_cover(affiliation: PlayerTeamAffiliation, game: Game) -> bool:
    """Only precise date bounds may exclude a game for this affiliation's team."""
    if game.official_date is None:
        return True
    if affiliation.boundary_precision != PlayerTeamAffiliation.BoundaryPrecision.DATE:
        return True
    return (
        affiliation.effective_from_date is None
        or affiliation.effective_from_date <= game.official_date
    ) and (
        affiliation.effective_to_date_exclusive is None
        or game.official_date < affiliation.effective_to_date_exclusive
    )


def select_player_window(
    *,
    season: Season | int,
    player: Player | UUID,
    window: str = "SEASON",
    cutoff: Cutoff | str | date | UUID = "LATEST",
    represented_team: Team | UUID | None = None,
    home_away: str = "ALL",
) -> SelectionResult:
    """Select distinct player batting games and their scoped PA identities."""
    requested_n = _validate_scope(window, home_away)
    season = _resolve_season(season)
    player = _resolve_entity(Player, player, "PLAYER_NOT_FOUND")
    team = (
        _resolve_entity(Team, represented_team, "TEAM_NOT_FOUND")
        if represented_team is not None
        else None
    )
    cutoff_request = _parse_cutoff(cutoff)
    anchors = _anchor_games(season, team.id if team else None)
    resolved_cutoff, cutoff_game = _resolve_cutoff(cutoff_request, season, anchors)
    scoped = [
        game
        for game in anchors
        if team is None or game.home_team_id == team.id or game.away_team_id == team.id
    ]
    if (
        cutoff_game is not None
        and team is not None
        and (
            (home_away == "HOME" and cutoff_game.home_team_id != team.id)
            or (home_away == "AWAY" and cutoff_game.away_team_id != team.id)
        )
    ):
        raise SelectionError("CUTOFF_GAME_OUTSIDE_SCOPE")
    selected_team_ids = {
        team_id
        for game in scoped
        for team_id in (game.home_team_id, game.away_team_id)
        if team is None or team_id == team.id
    }
    game_ids = [game.id for game in scoped]
    participation_rows = {
        (row.game_id, row.team_id): row
        for row in PlayerGameParticipation.objects.filter(
            game_id__in=game_ids, player=player, team_id__in=selected_team_ids
        )
    }
    pa_rows: dict[tuple[UUID, UUID], list[PlateAppearance]] = defaultdict(list)
    for pa in PlateAppearance.objects.filter(
        game_id__in=game_ids, batter=player, batting_team_id__in=selected_team_ids
    ):
        pa_rows[(pa.game_id, pa.batting_team_id)].append(pa)
    participation_coverage = {
        row.game_id: row.state
        for row in GameDataCoverage.objects.filter(
            game_id__in=game_ids, domain=GameDataCoverage.Domain.PARTICIPATION
        )
    }

    if team is None:
        affiliations = list(
            PlayerTeamAffiliation.objects.filter(player=player).filter(
                Q(season=season) | Q(season__isnull=True)
            )
        )
        observed_teams: dict[UUID, set[UUID]] = defaultdict(set)
        for game_id, team_id in participation_rows:
            observed_teams[game_id].add(team_id)
        for game_id, team_id in pa_rows:
            observed_teams[game_id].add(team_id)
        relevant_teams: dict[UUID, tuple[UUID, ...]] = {}
        for game in scoped:
            clubs = {game.home_team_id, game.away_team_id}
            teams = observed_teams[game.id] & clubs
            teams.update(
                affiliation.team_id
                for affiliation in affiliations
                if affiliation.team_id in clubs
                and _affiliation_may_cover(affiliation, game)
            )
            if teams:
                relevant_teams[game.id] = tuple(
                    team_id
                    for team_id in (game.home_team_id, game.away_team_id)
                    if team_id in teams
                )
        scoped = [game for game in scoped if game.id in relevant_teams]
    else:
        relevant_teams = {game.id: (team.id,) for game in scoped}

    known: list[tuple[Game, SelectionEntry]] = []
    uncertain: list[tuple[Game, MembershipState]] = []
    unknown_date_ids: list[UUID] = []
    cutoff_tie_ids = _cutoff_tie_ids(scoped, resolved_cutoff, cutoff_game)
    for game in scoped:
        if game.official_date is not None and not _through_cutoff(
            game, resolved_cutoff, cutoff_game
        ):
            continue
        eligible_teams = tuple(
            team_id
            for team_id in relevant_teams[game.id]
            if (
                home_away == "ALL"
                or (home_away == "HOME" and team_id == game.home_team_id)
                or (home_away == "AWAY" and team_id == game.away_team_id)
            )
        )
        if not eligible_teams:
            continue
        entry, state = _player_game_evidence(
            game,
            eligible_teams,
            participation_rows,
            pa_rows,
            participation_coverage,
        )
        if game.official_date is None:
            if entry is not None or state is not None:
                unknown_date_ids.append(game.id)
        elif entry is not None:
            known.append((game, entry))
        elif state is not None:
            uncertain.append((game, state))
    return _finish(
        subject_kind="PLAYER",
        subject_id=player.id,
        season=season,
        window=window,
        requested_n=requested_n,
        team_filter_id=team.id if team else None,
        home_away=home_away,
        cutoff_request=cutoff_request,
        resolved_cutoff=resolved_cutoff,
        qualified=known,
        uncertain=uncertain,
        unknown_date_ids=tuple(sorted(unknown_date_ids)),
        cutoff_tie_ids=cutoff_tie_ids,
        cutoff_game_id=cutoff_game.id if cutoff_game else None,
    )
