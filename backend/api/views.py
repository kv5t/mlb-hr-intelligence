"""B11 read-only discovery, game and date-focused API endpoints."""

from datetime import date
from uuid import UUID

from django.db.models import F, Q
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from domain.models import (
    Game,
    PlateAppearance,
    Player,
    PlayerGameParticipation,
    PlayerTeamAffiliation,
    Season,
    Team,
)

from .base import ReadOnlyView
from .errors import ApiProblem
from .pagination import paginate
from .serializers import player_summary, season_summary, team_summary
from .services import (
    game_detail,
    public_game,
    schedule_date,
    today_coverage,
    today_games,
    today_leaders,
)


def _parameters(request, allowed):
    unknown = set(request.query_params) - set(allowed)
    if unknown:
        raise ApiProblem(
            "INVALID_FILTER",
            "Unsupported query parameter",
            details={name: "unsupported" for name in sorted(unknown)},
        )
    if any(
        len(request.query_params.getlist(name)) != 1 for name in request.query_params
    ):
        raise ApiProblem("INVALID_FILTER", "Duplicate query parameter", details={})


def _year(raw, *, required=False):
    if raw is None:
        if required:
            raise ApiProblem(
                "INVALID_FILTER", "season is required", details={"season": "required"}
            )
        return None
    if len(raw) != 4 or not raw.isdecimal():
        raise ApiProblem(
            "INVALID_FILTER", "Invalid season", details={"season": "use YYYY"}
        )
    season = Season.objects.filter(year=int(raw)).first()
    if season is None:
        raise ApiProblem(
            "INVALID_FILTER", "Unknown season", details={"season": "not found"}
        )
    return season


def _date(raw, name, *, required=False):
    if raw is None:
        if required:
            raise ApiProblem(
                "INVALID_FILTER", f"{name} is required", details={name: "required"}
            )
        return None
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        day = None
    if day is None or day.isoformat() != raw:
        raise ApiProblem(
            "INVALID_FILTER", f"Invalid {name}", details={name: "use YYYY-MM-DD"}
        )
    return day


def _uuid(raw, name, *, path=False):
    try:
        return UUID(raw)
    except (ValueError, TypeError):
        if path:
            raise NotFound() from None
        raise ApiProblem(
            "INVALID_FILTER",
            f"Invalid {name}",
            details={name: "canonical UUID required"},
        ) from None


def _ordering(raw, allowed, default):
    if raw is None:
        return default
    descending = raw.startswith("-")
    key = raw[1:] if descending else raw
    if key not in allowed:
        raise ApiProblem(
            "INVALID_FILTER",
            "Unsupported ordering",
            details={"ordering": "unsupported"},
        )
    return [
        F(allowed[key]).desc(nulls_last=True)
        if descending
        else F(allowed[key]).asc(nulls_last=True),
        "id",
    ]


class SeasonsView(ReadOnlyView):
    def get(self, request):
        _parameters(request, {"page", "page_size"})
        return Response(
            paginate(request, Season.objects.order_by("-year", "id"), season_summary)
        )


class TeamsView(ReadOnlyView):
    def get(self, request):
        _parameters(
            request,
            {"season", "league", "division", "search", "ordering", "page", "page_size"},
        )
        season = _year(request.query_params.get("season"))
        queryset = Team.objects.all()
        if season:
            ids = set(
                Game.objects.filter(season=season).values_list(
                    "home_team_id", flat=True
                )
            )
            ids.update(
                Game.objects.filter(season=season).values_list(
                    "away_team_id", flat=True
                )
            )
            ids.update(
                PlayerGameParticipation.objects.filter(game__season=season).values_list(
                    "team_id", flat=True
                )
            )
            ids.update(
                PlateAppearance.objects.filter(game__season=season).values_list(
                    "batting_team_id", flat=True
                )
            )
            ids.update(
                PlayerTeamAffiliation.objects.filter(season=season).values_list(
                    "team_id", flat=True
                )
            )
            queryset = queryset.filter(id__in=ids)
        for name in ("league", "division"):
            if request.query_params.get(name):
                queryset = queryset.filter(
                    **{f"{name}__iexact": request.query_params[name]}
                )
        if search := request.query_params.get("search"):
            queryset = queryset.filter(display_name__icontains=search)
        ordering = _ordering(
            request.query_params.get("ordering"),
            {"name": "display_name", "abbreviation": "abbreviation"},
            [F("display_name").asc(nulls_last=True), "id"],
        )
        return Response(paginate(request, queryset.order_by(*ordering), team_summary))


class PlayersView(ReadOnlyView):
    def get(self, request):
        _parameters(
            request,
            {
                "season",
                "team",
                "search",
                "position",
                "bats",
                "ordering",
                "page",
                "page_size",
            },
        )
        season = _year(request.query_params.get("season"))
        team = None
        if raw := request.query_params.get("team"):
            team = Team.objects.filter(pk=_uuid(raw, "team")).first()
            if team is None:
                raise ApiProblem(
                    "INVALID_FILTER", "Unknown team", details={"team": "not found"}
                )
        queryset = Player.objects.all()
        if season or team:
            participations = PlayerGameParticipation.objects.all()
            pas = PlateAppearance.objects.all()
            affiliations = PlayerTeamAffiliation.objects.all()
            if season:
                participations = participations.filter(game__season=season)
                pas = pas.filter(game__season=season)
                affiliations = (
                    affiliations.filter(
                        Q(season=season)
                        | Q(
                            season__isnull=True,
                        )
                        & (
                            Q(effective_from_date__isnull=True)
                            | Q(effective_from_date__lte=season.ends_on)
                        )
                        & (
                            Q(effective_to_date_exclusive__isnull=True)
                            | Q(effective_to_date_exclusive__gt=season.starts_on)
                        )
                    )
                    if season.starts_on and season.ends_on
                    else affiliations.filter(season=season)
                )
            if team:
                participations = participations.filter(team=team)
                pas = pas.filter(batting_team=team)
                affiliations = affiliations.filter(team=team)
            ids = set(participations.values_list("player_id", flat=True))
            ids.update(pas.values_list("batter_id", flat=True))
            ids.update(affiliations.values_list("player_id", flat=True))
            queryset = queryset.filter(id__in=ids)
        if search := request.query_params.get("search"):
            queryset = queryset.filter(display_name__icontains=search)
        if position := request.query_params.get("position"):
            queryset = queryset.filter(primary_position__iexact=position)
        if bats := request.query_params.get("bats"):
            if bats not in Player.Bats.values:
                raise ApiProblem(
                    "INVALID_FILTER", "Invalid bats", details={"bats": "unsupported"}
                )
            queryset = queryset.filter(bats=bats)
        ordering = _ordering(
            request.query_params.get("ordering"),
            {"name": "display_name", "position": "primary_position"},
            [F("display_name").asc(nulls_last=True), "id"],
        )
        # A team filter proves association, not a current team.
        return Response(
            paginate(
                request,
                queryset.order_by(*ordering),
                lambda player: player_summary(player, team),
            )
        )


def _games_order(raw):
    if raw is None:
        return [
            F("official_date").asc(nulls_last=True),
            F("scheduled_game_number").asc(nulls_last=True),
            F("scheduled_start_at_utc").asc(nulls_last=True),
            "id",
        ]
    return _ordering(
        raw,
        {
            "official_date": "official_date",
            "scheduled_start_at_utc": "scheduled_start_at_utc",
        },
        [],
    )


class GamesView(ReadOnlyView):
    def get(self, request):
        _parameters(
            request,
            {
                "season",
                "date_from",
                "date_to",
                "team",
                "status",
                "ordering",
                "page",
                "page_size",
            },
        )
        season = _year(request.query_params.get("season"))
        start = _date(request.query_params.get("date_from"), "date_from")
        end = _date(request.query_params.get("date_to"), "date_to")
        if start and end and start > end:
            raise ApiProblem(
                "INVALID_FILTER",
                "date_from exceeds date_to",
                details={"date_from": "after date_to"},
            )
        games = Game.objects.select_related("season", "home_team", "away_team", "venue")
        if season:
            games = games.filter(season=season)
        if raw := request.query_params.get("team"):
            team_id = _uuid(raw, "team")
            if not Team.objects.filter(pk=team_id).exists():
                raise ApiProblem(
                    "INVALID_FILTER", "Unknown team", details={"team": "not found"}
                )
            games = games.filter(Q(home_team_id=team_id) | Q(away_team_id=team_id))
        if status := request.query_params.get("status"):
            if status not in Game.Status.values:
                raise ApiProblem(
                    "INVALID_FILTER",
                    "Invalid status",
                    details={"status": "unsupported"},
                )
            games = games.filter(status=status)
        ordered = games.order_by(*_games_order(request.query_params.get("ordering")))
        # List date filters use the schedule calendar, not analytical cutoff.
        if start or end:
            ordered = [
                game
                for game in ordered
                if (scheduled := schedule_date(game)) is not None
                and (start is None or scheduled >= start)
                and (end is None or scheduled <= end)
            ]
        return Response(paginate(request, ordered, public_game))


class GameDetailView(ReadOnlyView):
    def get(self, request, id):
        _parameters(request, set())
        game = (
            Game.objects.filter(pk=_uuid(id, "id", path=True))
            .select_related("season", "home_team", "away_team", "venue")
            .first()
        )
        if game is None:
            raise NotFound()
        return Response(game_detail(game))


class TodayView(ReadOnlyView):
    def get(self, request):
        _parameters(request, {"season", "date", "window"})
        season = _year(request.query_params.get("season"), required=True)
        day = _date(request.query_params.get("date"), "date", required=True)
        window = request.query_params.get("window", "SEASON")
        if window not in ("7G", "15G", "30G", "60G", "SEASON"):
            raise ApiProblem(
                "INVALID_FILTER", "Invalid window", details={"window": "unsupported"}
            )
        if season.starts_on is None or season.ends_on is None:
            raise ApiProblem(
                "SEASON_CALENDAR_UNVERIFIED", "Season calendar is unavailable"
            )
        if not season.starts_on <= day <= season.ends_on:
            raise ApiProblem(
                "DATE_OUTSIDE_SEASON", "Date is outside the season calendar"
            )
        games = today_games(season, day)
        games.sort(
            key=lambda game: (
                game.scheduled_start_at_utc is None,
                game.scheduled_start_at_utc or date.max,
                game.scheduled_game_number is None,
                game.scheduled_game_number or 0,
                game.id,
            )
        )
        leaders = today_leaders(season, day, window)
        leader_states = [row["metrics"]["player.hr"]["state"] for row in leaders]
        availability = (
            "NOT_APPLICABLE"
            if not leader_states
            else "UNKNOWN"
            if "UNKNOWN" in leader_states
            else "INCOMPLETE"
            if "INCOMPLETE" in leader_states
            else "ORDER_UNVERIFIED"
            if "ORDER_UNVERIFIED" in leader_states
            else "VALUE"
        )
        return Response(
            {
                "date": day,
                "games": [public_game(game) for game in games],
                "recent_leaders": leaders,
                "recent_leaders_availability": {
                    "state": availability,
                    "reason": "NO_GAMES" if not leaders else None,
                },
                "scope": {
                    "season": season.year,
                    "subject": "PLAYER",
                    "game_type": "REGULAR",
                    "window": window,
                    "requested_n": None if window == "SEASON" else int(window[:-1]),
                    "cutoff_date": day,
                    "cutoff_source": "EXPLICIT",
                },
                "coverage": today_coverage(games),
            }
        )
