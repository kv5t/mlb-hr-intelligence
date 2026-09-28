from django.urls import path

from .views import (
    GameDetailView,
    GamesView,
    PlayerDetailView,
    PlayerHomeRunsView,
    PlayerLeaderboardView,
    PlayersView,
    SeasonsView,
    TeamDetailView,
    TeamHomeRunsView,
    TeamsView,
    TodayView,
)

urlpatterns = [
    path("seasons/", SeasonsView.as_view()),
    path("teams/", TeamsView.as_view()),
    path("teams/<str:id>/home-runs/", TeamHomeRunsView.as_view()),
    path("teams/<str:id>/", TeamDetailView.as_view()),
    path("players/", PlayersView.as_view()),
    path("players/<str:id>/home-runs/", PlayerHomeRunsView.as_view()),
    path("players/<str:id>/", PlayerDetailView.as_view()),
    path("leaderboards/players/", PlayerLeaderboardView.as_view()),
    path("games/", GamesView.as_view()),
    path("games/<str:id>/", GameDetailView.as_view()),
    path("today/", TodayView.as_view()),
]
