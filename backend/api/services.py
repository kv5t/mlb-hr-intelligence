"""B11 composition of canonical evidence and existing analytical services."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from analytics.coverage import (
    assess_hr_integrity,
    assess_player_pa_integrity,
    evaluate_game_coverage,
)
from analytics.production import compute_player_production_metrics
from analytics.recurrence import compute_player_recurrence
from analytics.values import MetricState, MetricValue
from analytics.windows import MembershipState, select_player_window
from domain.models import (
    Game,
    GameDataCoverage,
    HomeRunEvent,
    PlateAppearance,
    Player,
    PlayerGameParticipation,
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
        pa = event.plate_appearance
        result.append(
            {
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
                "provenance": _safe_event_provenance(event),
            }
        )
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
