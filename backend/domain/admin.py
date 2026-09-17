"""Read-only staff inspection of canonical sports facts."""

from django.contrib import admin

from .models import (
    Game,
    GameDataCoverage,
    GameLifecycleEvent,
    HomeRunEvent,
    PlateAppearance,
    Player,
    PlayerGameParticipation,
    PlayerTeamAffiliation,
    Season,
    Team,
    Venue,
)


class CanonicalInspectAdmin(admin.ModelAdmin):
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


ADMIN_VIEWS = (
    (Season, ("year", "label", "status"), ("year", "label"), ("status",)),
    (
        Team,
        ("display_name", "mlb_id", "league", "division"),
        ("display_name", "mlb_id"),
        ("league",),
    ),
    (
        Player,
        ("display_name", "mlb_id", "bats", "throws"),
        ("display_name", "mlb_id"),
        ("bats",),
    ),
    (Venue, ("name", "mlb_id", "timezone_id"), ("name", "mlb_id"), ()),
    (
        PlayerTeamAffiliation,
        ("player", "team", "effective_from_date", "effective_to_date_exclusive"),
        ("player__display_name", "team__display_name"),
        ("boundary_precision",),
    ),
    (
        Game,
        ("id", "official_date", "home_team", "away_team", "status", "finality"),
        ("mlb_game_pk",),
        ("game_type", "status", "finality"),
    ),
    (
        GameLifecycleEvent,
        ("game", "event_kind", "recorded_at_utc"),
        ("game__mlb_game_pk",),
        ("event_kind",),
    ),
    (
        PlayerGameParticipation,
        ("game", "player", "team", "participation_state", "pa_coverage"),
        ("player__display_name",),
        ("participation_state", "pa_coverage"),
    ),
    (
        PlateAppearance,
        ("game", "batter", "batting_team", "game_pa_ordinal", "outcome_category"),
        ("batter__display_name",),
        ("outcome_category",),
    ),
    (HomeRunEvent, ("id", "plate_appearance"), (), ()),
    (
        GameDataCoverage,
        ("game", "domain", "state", "reason_code", "assessed_at_utc"),
        ("game__mlb_game_pk",),
        ("domain", "state"),
    ),
)

for model, display, search, filters in ADMIN_VIEWS:
    admin.site.register(
        model,
        type(
            f"{model.__name__}InspectAdmin",
            (CanonicalInspectAdmin,),
            {"list_display": display, "search_fields": search, "list_filter": filters},
        ),
    )
