from django.urls import path

from .exports import ExportView
from .views import (
    GameDetailView,
    GamesView,
    PlayerDetailView,
    PlayerHomeRunsView,
    PlayerLeaderboardView,
    PlayerRecurrenceView,
    PlayersView,
    SeasonsView,
    TeamDetailView,
    TeamHomeRunsView,
    TeamRecurrenceView,
    TeamsView,
    TodayView,
)

urlpatterns = [
    path("exports/leaderboards/players/", ExportView.as_view(kind="leaderboard")),
    path(
        "exports/teams/<str:id>/recurrence/", ExportView.as_view(kind="team_recurrence")
    ),
    path(
        "exports/players/<str:id>/recurrence/",
        ExportView.as_view(kind="player_recurrence"),
    ),
    path(
        "exports/teams/<str:id>/home-runs/", ExportView.as_view(kind="team_home_runs")
    ),
    path(
        "exports/players/<str:id>/home-runs/",
        ExportView.as_view(kind="player_home_runs"),
    ),
    path("seasons/", SeasonsView.as_view()),
    path("teams/", TeamsView.as_view()),
    path("teams/<str:id>/recurrence/", TeamRecurrenceView.as_view()),
    path("teams/<str:id>/home-runs/", TeamHomeRunsView.as_view()),
    path("teams/<str:id>/", TeamDetailView.as_view()),
    path("players/", PlayersView.as_view()),
    path("players/<str:id>/recurrence/", PlayerRecurrenceView.as_view()),
    path("players/<str:id>/home-runs/", PlayerHomeRunsView.as_view()),
    path("players/<str:id>/", PlayerDetailView.as_view()),
    path("leaderboards/players/", PlayerLeaderboardView.as_view()),
    path("games/", GamesView.as_view()),
    path("games/<str:id>/", GameDetailView.as_view()),
    path("today/", TodayView.as_view()),
]
