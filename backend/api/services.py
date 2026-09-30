"""B11 composition of canonical evidence and existing analytical services."""

from collections import defaultdict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db.models import Q

from analytics.coverage import (
    MatrixCellState,
    MatrixEvidenceIndex,
    assess_hr_integrity,
    assess_player_pa_integrity,
    evaluate_game_coverage,
)
from analytics.production import (
    compute_player_production_metrics,
    compute_team_production_metrics,
    player_observation_metrics,
)
from analytics.recurrence import compute_player_recurrence, compute_team_recurrence
from analytics.values import MetricState, MetricValue
from analytics.windows import MembershipState, select_player_window
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
from ingestion.models import FactSourceLink

from .serializers import (
    coverage_summary,
    game_summary,
    metric_value,
    player_summary,
    team_summary,
)


def game_hr_count(game):
    """One whole-game HR proof for list, detail and Today."""
    gate = evaluate_game_coverage(game, (GameDataCoverage.Domain.HR_EVENTS,))
    if gate.state != MetricState.VALUE:
        return MetricValue(gate.state, unit="HR", reason=gate.reason)
    pas = list(PlateAppearance.objects.filter(game=game))
    events = list(HomeRunEvent.objects.filter(plate_appearance__game=game))
    integrity = assess_hr_integrity(pas, events)
    if integrity.state != MetricState.VALUE:
        return MetricValue(integrity.state, unit="HR", reason=integrity.reason)
    count = len(events)
    return MetricValue(MetricState.VALUE, value=count, unit="HR", numerator=count)


def public_game(game):
    return game_summary(game, game_hr_count(game))


def _participant_metric(game, player, team, row, count):
    if row is None:
        return MetricValue(
            MetricState.UNKNOWN, unit="PA", reason="PARTICIPATION_POPULATION_UNVERIFIED"
        )
    if row.pa_coverage == PlayerGameParticipation.Coverage.PARTIAL:
        return MetricValue(MetricState.INCOMPLETE, unit="PA")
    if row.pa_coverage != PlayerGameParticipation.Coverage.COMPLETE:
        return MetricValue(MetricState.UNKNOWN, unit="PA")
    pas = list(
        PlateAppearance.objects.filter(game=game, batter=player, batting_team=team)
    )
    integrity = assess_player_pa_integrity([row], pas)
    if integrity.state != MetricState.VALUE:
        return MetricValue(integrity.state, unit="PA", reason=integrity.reason)
    return MetricValue(MetricState.VALUE, value=count, unit="PA", numerator=count)


def game_participants(game):
    """Positive APPEARED rows and PA batter/pitcher evidence only."""
    appearances = list(
        PlateAppearance.objects.filter(game=game).select_related(
            "batter", "pitcher", "batting_team", "fielding_team"
        )
    )
    rows = list(
        PlayerGameParticipation.objects.filter(
            game=game, participation_state=PlayerGameParticipation.State.APPEARED
        ).select_related("player", "team")
    )
    by_key = {}
    for row in rows:
        by_key[(row.player_id, row.team_id)] = {
            "player": row.player,
            "team": row.team,
            "row": row,
            "roles": set(),
            "pa_count": 0,
        }
    for pa in appearances:
        key = (pa.batter_id, pa.batting_team_id)
        entry = by_key.setdefault(
            key,
            {
                "player": pa.batter,
                "team": pa.batting_team,
                "row": None,
                "roles": set(),
                "pa_count": 0,
            },
        )
        entry["roles"].add("BATTER")
        entry["pa_count"] += 1
        if pa.pitcher_id is not None:
            key = (pa.pitcher_id, pa.fielding_team_id)
            entry = by_key.setdefault(
                key,
                {
                    "player": pa.pitcher,
                    "team": pa.fielding_team,
                    "row": None,
                    "roles": set(),
                    "pa_count": 0,
                },
            )
            entry["roles"].add("PITCHER")
    return [
        {
            "player": player_summary(item["player"], item["team"]),
            "team": team_summary(item["team"]),
            "participation_state": PlayerGameParticipation.State.APPEARED,
            "roles": sorted(item["roles"]),
            "pa_count": metric_value(
                _participant_metric(
                    game, item["player"], item["team"], item["row"], item["pa_count"]
                )
            ),
        }
        for _, item in sorted(by_key.items())
    ]


def _safe_event_provenance(event):
    link = (
        FactSourceLink.objects.filter(
            entity_kind="HOME_RUN_EVENT",
            canonical_entity_id=event.id,
            relation=FactSourceLink.Relation.SUPPORTS,
        )
        .select_related("source_record__provider")
        .order_by("source_record__retrieved_at_utc", "id")
        .first()
    )
    if link is None:
        return None
    return {
        "source_label": link.source_record.provider.display_name,
        "retrieved_at": link.source_record.retrieved_at_utc,
    }


_LOOK_UP_PROVENANCE = object()


def home_run_event_summary(event, provenance=_LOOK_UP_PROVENANCE):
    """Serialize one reconciled canonical event with public-safe evidence only."""
    pa = event.plate_appearance
    game = pa.game
    return {
        "id": str(event.id),
        "game_id": str(game.id),
        "plate_appearance_id": str(pa.id),
        "official_date": game.official_date,
        "batter": player_summary(pa.batter),
        "pitcher": player_summary(pa.pitcher) if pa.pitcher else None,
        "batting_team": team_summary(pa.batting_team),
        "inning": pa.inning,
        "half_inning": pa.half_inning or "UNKNOWN",
        "game_pa_ordinal": pa.game_pa_ordinal,
        "provenance": _safe_event_provenance(event)
        if provenance is _LOOK_UP_PROVENANCE
        else provenance,
    }


def game_home_runs(game):
    events = (
        HomeRunEvent.objects.filter(
            plate_appearance__game=game,
            plate_appearance__outcome_category=PlateAppearance.Outcome.HOME_RUN,
        )
        .select_related(
            "plate_appearance__batter",
            "plate_appearance__pitcher",
            "plate_appearance__batting_team",
        )
        .order_by("plate_appearance__game_pa_ordinal", "id")
    )
    result = []
    for event in events:
        result.append(home_run_event_summary(event))
    return result


def game_detail(game):
    return {
        "game": public_game(game),
        "participants": game_participants(game),
        "home_runs": game_home_runs(game),
        "coverage": coverage_summary(game),
    }


def schedule_date(game):
    """Use venue-local scheduled date when verifiable; otherwise official date.

    No UTC date is relabelled as local schedule date when venue timezone is
    absent/invalid. An unknown official date and unlocalizable start stay hidden.
    """
    if (
        game.scheduled_start_at_utc is not None
        and game.venue
        and game.venue.timezone_id
    ):
        try:
            return game.scheduled_start_at_utc.astimezone(
                ZoneInfo(game.venue.timezone_id)
            ).date()
        except ZoneInfoNotFoundError:
            pass
    return game.official_date


def today_games(season, day):
    games = Game.objects.filter(season=season).select_related(
        "season", "home_team", "away_team", "venue"
    )
    return [game for game in games if schedule_date(game) == day]


def _scope(selection):
    cutoff = selection.resolved_cutoff
    return {
        "season": selection.season_year,
        "subject": selection.subject_kind,
        "subject_id": str(selection.subject_id),
        "game_type": "REGULAR",
        "window": selection.window,
        "requested_n": selection.requested_n,
        "cutoff_date": cutoff.official_date
        if cutoff and cutoff.official_date
        else None,
        "cutoff_source": "EXPLICIT"
        if selection.cutoff_request.kind == "DATE"
        else "LATEST",
        "team_filter_id": str(selection.team_filter_id)
        if selection.team_filter_id
        else None,
        "home_away": selection.home_away,
        "selection_state": "VALUE"
        if selection.membership_state == MembershipState.RESOLVED
        else selection.membership_state.value,
        "actual_game_count": selection.actual_game_count,
        "known_eligible_game_count": selection.known_eligible_game_count,
    }


def player_metrics(selection):
    """All scalar B09/B10 player metrics for an already selected scope."""
    metrics = compute_player_production_metrics(selection)
    metrics.update(compute_player_recurrence(selection).metrics)
    return {name: metric_value(value) for name, value in metrics.items()}


def team_metrics(selection):
    """All scalar B09/B10 team metrics for an already selected scope."""
    metrics = compute_team_production_metrics(selection)
    metrics.update(compute_team_recurrence(selection).metrics)
    return {name: metric_value(value) for name, value in metrics.items()}


def team_hr_total(selection):
    """Authoritative team HR total without computing unrelated recurrence KPIs."""
    metric = compute_team_production_metrics(selection)["team.hr"]
    return metric_value(metric)


def selection_coverage(selection):
    """Conservative current coverage projection across selected games."""
    game_ids = {entry.game_id for entry in selection.entries}
    if not game_ids:
        return []
    rows = defaultdict(dict)
    for row in GameDataCoverage.objects.filter(game_id__in=game_ids):
        rows[row.domain][row.game_id] = row
    result = []
    for domain in GameDataCoverage.Domain.values:
        domain_rows = rows[domain]
        states = [domain_rows.get(game_id) for game_id in game_ids]
        if any(
            row is None
            or row.state
            in (GameDataCoverage.State.UNKNOWN, GameDataCoverage.State.UNAVAILABLE)
            for row in states
        ):
            state = GameDataCoverage.State.UNKNOWN
        elif any(row.state == GameDataCoverage.State.PARTIAL for row in states):
            state = GameDataCoverage.State.PARTIAL
        else:
            state = GameDataCoverage.State.COMPLETE
        result.append(
            {
                "domain": domain,
                "state": state,
                "reason_codes": sorted(
                    {row.reason_code for row in states if row and row.reason_code}
                ),
            }
        )
    return result


def represented_team_for_selection(selection, requested_team):
    """Return a requested team only when positive selected evidence supports it."""
    if requested_team is None:
        return None
    entries = (
        *selection.entries,
        *selection.known_core_entries,
        *(item.entry for item in selection.full_scope_observations if item.entry),
    )
    if any(requested_team.id in entry.represented_team_ids for entry in entries):
        return requested_team
    return None


def player_analytics_row(player, selection, requested_team=None):
    return {
        "player": player_summary(
            player, represented_team_for_selection(selection, requested_team)
        ),
        "metrics": player_metrics(selection),
        "scope": _scope(selection),
        "coverage": selection_coverage(selection),
    }


def team_analytics(team, selection):
    return {
        "team": team_summary(team),
        "metrics": team_metrics(selection),
        "scope": _scope(selection),
        "coverage": selection_coverage(selection),
    }


def _coverage_by_game(games):
    games = list(games)
    rows = defaultdict(dict)
    for row in GameDataCoverage.objects.filter(game_id__in=[game.id for game in games]):
        rows[row.game_id][row.domain] = row
    return {
        game.id: [
            {
                "domain": domain,
                "state": rows[game.id][domain].state
                if domain in rows[game.id]
                else GameDataCoverage.State.UNKNOWN,
                "reason_codes": [rows[game.id][domain].reason_code]
                if domain in rows[game.id] and rows[game.id][domain].reason_code
                else [],
            }
            for domain in GameDataCoverage.Domain.values
        ]
        for game in games
    }


def _matrix_players(selection, team, games):
    game_ids = [game.id for game in games]
    player_ids = set(
        PlayerGameParticipation.objects.filter(
            game_id__in=game_ids, team=team
        ).values_list("player_id", flat=True)
    )
    player_ids.update(
        PlateAppearance.objects.filter(
            game_id__in=game_ids, batting_team=team
        ).values_list("batter_id", flat=True)
    )
    if games:
        first_day = min(game.official_date for game in games)
        last_day = max(game.official_date for game in games)
        affiliations = PlayerTeamAffiliation.objects.filter(team=team).filter(
            Q(season_id=selection.season_id) | Q(season__isnull=True)
        )
        affiliations = affiliations.filter(
            ~Q(boundary_precision=PlayerTeamAffiliation.BoundaryPrecision.DATE)
            | (
                (
                    Q(effective_from_date__isnull=True)
                    | Q(effective_from_date__lte=last_day)
                )
                & (
                    Q(effective_to_date_exclusive__isnull=True)
                    | Q(effective_to_date_exclusive__gt=first_day)
                )
            )
        )
        player_ids.update(affiliations.values_list("player_id", flat=True))
    return list(Player.objects.filter(id__in=player_ids).order_by("id"))


def _matrix_cell(cell):
    positive = cell.state == MatrixCellState.HR_COUNT
    return {
        "state": cell.state.value,
        "hr_count": cell.hr_count,
        "home_run_event_ids": [str(value) for value in cell.hr_event_ids]
        if positive
        else [],
        "reason": cell.reason,
    }


def _matrix_window_hr(cells):
    unknown = next(
        (cell for cell in cells if cell.state == MatrixCellState.UNKNOWN), None
    )
    if unknown:
        return MetricValue(MetricState.UNKNOWN, unit="HR", reason=unknown.reason)
    incomplete = next(
        (cell for cell in cells if cell.state == MatrixCellState.INCOMPLETE), None
    )
    if incomplete:
        return MetricValue(MetricState.INCOMPLETE, unit="HR", reason=incomplete.reason)
    total = sum(cell.hr_count or 0 for cell in cells)
    return MetricValue(MetricState.VALUE, value=total, unit="HR", numerator=total)


def team_recurrence(team, selection):
    """Compose a shared-column team matrix from batched B08 evidence."""
    base = team_analytics(team, selection)
    if selection.membership_state != MembershipState.RESOLVED:
        return {**base, "columns": [], "rows": []}
    ordered_ids = [entry.game_id for entry in selection.entries]
    game_map = {
        game.id: game
        for game in Game.objects.filter(id__in=ordered_ids).select_related(
            "home_team", "away_team"
        )
    }
    games = [game_map[game_id] for game_id in ordered_ids]
    coverage = _coverage_by_game(games)
    columns = []
    for game in games:
        home = game.home_team_id == team.id
        columns.append(
            {
                "game_id": str(game.id),
                "official_date": game.official_date,
                "scheduled_game_number": game.scheduled_game_number,
                "opponent": team_summary(game.away_team if home else game.home_team),
                "home_away": "HOME" if home else "AWAY",
                "game_status": game.status,
                "coverage": coverage[game.id],
            }
        )
    players = _matrix_players(selection, team, games)
    evidence = MatrixEvidenceIndex(games, [player.id for player in players], team)
    cutoff = selection.resolved_cutoff.official_date
    rows = []
    for player in players:
        cells = [evidence.resolve(game.id, player.id) for game in games]
        season_selection = select_player_window(
            season=selection.season_year,
            player=player,
            window="SEASON",
            cutoff=cutoff,
        )
        season_hr = compute_player_production_metrics(season_selection)["player.hr"]
        rows.append(
            {
                "player": player_summary(player),
                "player_season_hr": metric_value(season_hr),
                "window_hr": metric_value(_matrix_window_hr(cells)),
                "cells": [_matrix_cell(cell) for cell in cells],
            }
        )
    return {**base, "columns": columns, "rows": rows}


def player_recurrence(player, selection, requested_team=None):
    """Compose canonical batting-game observations and endpoint-aware gaps."""
    recurrence = compute_player_recurrence(selection)
    production = compute_player_production_metrics(selection)
    production.update(recurrence.metrics)
    base = {
        "player": player_summary(
            player, represented_team_for_selection(selection, requested_team)
        ),
        "metrics": {name: metric_value(value) for name, value in production.items()},
        "scope": _scope(selection),
        "coverage": selection_coverage(selection),
    }
    if selection.membership_state != MembershipState.RESOLVED:
        return {**base, "observations": [], "gaps": []}
    games = {
        game.id: game
        for game in Game.objects.filter(
            id__in=[entry.game_id for entry in selection.entries]
        )
    }
    team_ids = {
        team_id for entry in selection.entries for team_id in entry.represented_team_ids
    }
    teams = {team.id: team for team in Team.objects.filter(id__in=team_ids)}
    observations = {
        item.game_id: item for item in player_observation_metrics(selection)
    }
    result = []
    for entry in selection.entries:
        item = observations[entry.game_id]
        result.append(
            {
                "game_id": str(entry.game_id),
                "official_date": games[entry.game_id].official_date,
                "represented_teams": [
                    team_summary(teams[team_id])
                    for team_id in entry.represented_team_ids
                ],
                "pa": metric_value(item.pa),
                "hr": metric_value(item.hr),
            }
        )
    gaps = [
        {
            "from_game_id": str(record.from_game_id),
            "to_game_id": str(record.to_game_id),
            "non_hr_games": metric_value(record.non_hr_games),
        }
        for record in recurrence.gap_series.records
    ]
    return {**base, "observations": result, "gaps": gaps}


def _order_home_run_events(events, selection, *, descending=False):
    ranks = {entry.game_id: index for index, entry in enumerate(selection.entries)}
    events.sort(
        key=lambda event: (
            -ranks[event.plate_appearance.game_id]
            if descending
            else ranks[event.plate_appearance.game_id],
            event.plate_appearance.game_pa_ordinal is None,
            event.plate_appearance.game_pa_ordinal or 0,
            event.id,
        )
    )
    return events


def player_home_run_events(selection):
    """Known event observations; membership uncertainty cannot define a list."""
    if selection.membership_state != MembershipState.RESOLVED:
        return []
    pa_ids = {
        pa_id for entry in selection.entries for pa_id in entry.plate_appearance_ids
    }
    if not pa_ids:
        return []
    events = list(
        HomeRunEvent.objects.filter(
            plate_appearance_id__in=pa_ids,
            plate_appearance__outcome_category=PlateAppearance.Outcome.HOME_RUN,
        ).select_related(
            "plate_appearance__game",
            "plate_appearance__batter",
            "plate_appearance__pitcher",
            "plate_appearance__batting_team",
        )
    )
    return _order_home_run_events(events, selection)


def team_home_run_events(selection):
    """Verified team-batting events from a definitive team-game window."""
    if selection.membership_state != MembershipState.RESOLVED:
        return []
    game_ids = [entry.game_id for entry in selection.entries]
    events = list(
        HomeRunEvent.objects.filter(
            plate_appearance__game_id__in=game_ids,
            plate_appearance__batting_team_id=selection.subject_id,
            plate_appearance__outcome_category=PlateAppearance.Outcome.HOME_RUN,
        ).select_related(
            "plate_appearance__game",
            "plate_appearance__batter",
            "plate_appearance__pitcher",
            "plate_appearance__batting_team",
        )
    )
    return _order_home_run_events(events, selection)


def order_home_run_events(events, selection, *, descending=False):
    """Apply canonical window/game/PA/event ordering to an event list."""
    return _order_home_run_events(events, selection, descending=descending)


def public_home_run_events(events):
    """Serialize a page of events with one bounded provenance query."""
    events = list(events)
    event_ids = [event.id for event in events]
    provenance = {}
    links = (
        FactSourceLink.objects.filter(
            entity_kind="HOME_RUN_EVENT",
            canonical_entity_id__in=event_ids,
            relation=FactSourceLink.Relation.SUPPORTS,
        )
        .select_related("source_record__provider")
        .order_by("source_record__retrieved_at_utc", "id")
    )
    for link in links:
        provenance.setdefault(
            link.canonical_entity_id,
            {
                "source_label": link.source_record.provider.display_name,
                "retrieved_at": link.source_record.retrieved_at_utc,
            },
        )
    return [home_run_event_summary(event, provenance.get(event.id)) for event in events]


def today_leaders(season, day, window):
    # Candidate identity comes from positive canonical batting evidence, never
    # a current-team profile. Rank with the B09 service, not a view formula.
    players = (
        Player.objects.filter(
            batting_pas__game__season=season,
            batting_pas__game__game_type=Game.Type.REGULAR,
            batting_pas__game__finality=Game.Finality.FINAL,
            batting_pas__game__official_date__lte=day,
        )
        .distinct()
        .order_by("id")
    )
    rows = []
    for player in players:
        selection = select_player_window(
            season=season, player=player, window=window, cutoff=day
        )
        metrics = compute_player_production_metrics(selection)
        metrics.update(compute_player_recurrence(selection).metrics)
        rows.append(
            {
                "player": player_summary(player),
                "metrics": {
                    name: metric_value(value) for name, value in metrics.items()
                },
                "scope": _scope(selection),
                "coverage": [],
            }
        )
    rows.sort(
        key=lambda row: (
            row["metrics"]["player.hr"]["state"] != "VALUE",
            -(row["metrics"]["player.hr"]["value"] or 0),
            row["player"]["id"],
        )
    )
    return rows[:5]


def today_leader_population_availability(season, day):
    """Assess whether every possible batting/HR contributor is represented.

    Observed player rows can still be useful when this gate is unavailable;
    this result describes the completeness of the ranking population itself.
    """
    candidates = Game.objects.filter(
        season=season,
        game_type=Game.Type.REGULAR,
        finality=Game.Finality.FINAL,
    )
    if candidates.filter(official_date__isnull=True).exists():
        return {"state": "UNKNOWN", "reason": "OFFICIAL_DATE_UNKNOWN"}

    game_ids = list(
        candidates.filter(official_date__lte=day).values_list("id", flat=True)
    )
    if not game_ids:
        return {"state": "NOT_APPLICABLE", "reason": "NO_GAMES"}

    rows = {
        (row.game_id, row.domain): row
        for row in GameDataCoverage.objects.filter(
            game_id__in=game_ids,
            domain__in=(
                GameDataCoverage.Domain.PLATE_APPEARANCES,
                GameDataCoverage.Domain.HR_EVENTS,
            ),
        )
    }
    saw_partial = False
    for game_id in game_ids:
        for domain in (
            GameDataCoverage.Domain.PLATE_APPEARANCES,
            GameDataCoverage.Domain.HR_EVENTS,
        ):
            row = rows.get((game_id, domain))
            if row is None or row.state in (
                GameDataCoverage.State.UNKNOWN,
                GameDataCoverage.State.UNAVAILABLE,
            ):
                return {
                    "state": "UNKNOWN",
                    "reason": row.reason_code
                    if row and row.reason_code
                    else "LEADER_POPULATION_UNVERIFIED",
                }
            if row.state == GameDataCoverage.State.PARTIAL:
                saw_partial = True
    if saw_partial:
        return {"state": "INCOMPLETE", "reason": "LEADER_POPULATION_INCOMPLETE"}
    return {"state": "VALUE", "reason": None}


def today_coverage(games):
    """Conservative current projection across listed schedule games."""
    if not games:
        return []
    summaries = [coverage_summary(game) for game in games]
    result = []
    for domain in GameDataCoverage.Domain.values:
        rows = [
            next(item for item in summary if item["domain"] == domain)
            for summary in summaries
        ]
        states = {row["state"] for row in rows}
        state = (
            GameDataCoverage.State.UNKNOWN
            if GameDataCoverage.State.UNKNOWN in states
            or GameDataCoverage.State.UNAVAILABLE in states
            else GameDataCoverage.State.PARTIAL
            if GameDataCoverage.State.PARTIAL in states
            else GameDataCoverage.State.COMPLETE
        )
        result.append(
            {
                "domain": domain,
                "state": state,
                "reason_codes": sorted(
                    {reason for row in rows for reason in row["reason_codes"]}
                ),
            }
        )
    return result


def home_run_scope(subject, selection, requested_team=None):
    """Authoritative metadata for both JSON HR logs and their full exports."""
    if selection.subject_kind == "TEAM":
        identity = {"team": team_summary(subject)}
        total = team_hr_total(selection)
    else:
        identity = {
            "player": player_summary(
                subject, represented_team_for_selection(selection, requested_team)
            )
        }
        total = player_metrics(selection)["player.hr"]
    return {
        **identity,
        "total_hr": total,
        "scope": _scope(selection),
        "coverage": selection_coverage(selection),
    }
