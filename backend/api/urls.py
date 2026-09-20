from django.urls import path

from .views import (
    GameDetailView,
    GamesView,
    PlayersView,
    SeasonsView,
    TeamsView,
    TodayView,
)

urlpatterns = [
    path("seasons/", SeasonsView.as_view()),
    path("teams/", TeamsView.as_view()),
    path("players/", PlayersView.as_view()),
    path("games/", GamesView.as_view()),
    path("games/<str:id>/", GameDetailView.as_view()),
    path("today/", TodayView.as_view()),
]
