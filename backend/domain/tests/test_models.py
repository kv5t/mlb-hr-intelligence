"""Structural B03/B04 invariants, independent of providers."""

from datetime import date, datetime, timezone
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from domain.models import (
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


class CanonicalModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.season = Season.objects.create(year=2025)
        cls.home = Team.objects.create(display_name="Home", mlb_id=101)
        cls.away = Team.objects.create(display_name="Away", mlb_id=102)
        cls.other = Team.objects.create(display_name="Other")
        cls.player = Player.objects.create(
            display_name="Batter", mlb_id=201, bats=Player.Bats.SWITCH
        )
        cls.venue = Venue.objects.create(name="Park", mlb_id=301)
        cls.game = Game.objects.create(
            season=cls.season,
            home_team=cls.home,
            away_team=cls.away,
            official_date=date(2025, 4, 12),
            game_type=Game.Type.REGULAR,
            finality=Game.Finality.FINAL,
        )

    def test_uuid_identity_nullable_external_ids_and_duplicate_lookup(self):
        self.assertNotEqual(self.player.id, self.player.mlb_id)
        self.assertIsNone(Player.objects.create().mlb_id)
        self.assertIsNone(Team.objects.create().mlb_id)
        with self.assertRaises(ValidationError):
            Player.objects.create(mlb_id=self.player.mlb_id)
        with self.assertRaises(ValidationError):
            Season.objects.create(year=2025)
        Game.objects.create(
            season=self.season,
            home_team=self.home,
            away_team=self.away,
            mlb_game_pk=900,
        )
        with self.assertRaises(ValidationError):
            Game.objects.create(
                season=self.season,
                home_team=self.home,
                away_team=self.away,
                mlb_game_pk=900,
            )
        original_id = self.player.id
        self.player.id = uuid4()
        with self.assertRaises(ValidationError):
            self.player.save()
        self.player.id = original_id

    def test_trade_return_and_interval_bounds(self):
        for team, start, end in [
            (self.home, date(2025, 1, 1), date(2025, 5, 1)),
            (self.away, date(2025, 5, 1), date(2025, 7, 1)),
            (self.home, date(2025, 7, 1), None),
        ]:
            PlayerTeamAffiliation.objects.create(
                player=self.player,
                team=team,
                effective_from_date=start,
                effective_to_date_exclusive=end,
                boundary_precision=PlayerTeamAffiliation.BoundaryPrecision.DATE,
            )
        self.assertEqual(
            list(
                PlayerTeamAffiliation.objects.filter(player=self.player).values_list(
                    "team_id", flat=True
                )
            ),
            [self.home.id, self.away.id, self.home.id],
        )
        PlayerTeamAffiliation.objects.create(player=self.player, team=self.away)
        with self.assertRaises(ValidationError):
            PlayerTeamAffiliation.objects.create(
                player=self.player,
                team=self.home,
                effective_from_date=date(2025, 5, 1),
                effective_to_date_exclusive=date(2025, 5, 1),
                boundary_precision=PlayerTeamAffiliation.BoundaryPrecision.DATE,
            )
        with self.assertRaises(ValidationError):
            PlayerTeamAffiliation.objects.create(
                player=self.player, team=self.home, effective_from_date=date(2025, 5, 1)
            )

    def test_doubleheader_and_game_teams(self):
        second = Game.objects.create(
            season=self.season,
            home_team=self.home,
            away_team=self.away,
            official_date=self.game.official_date,
            scheduled_game_number=2,
        )
        self.assertNotEqual(self.game.id, second.id)
        with self.assertRaises(ValidationError):
            Game.objects.create(
                season=self.season, home_team=self.home, away_team=self.home
            )
        self.assertEqual(
            Game.objects.filter(official_date=self.game.official_date).count(), 2
        )

    def test_lifecycle_and_utc_validation(self):
        instant = datetime(2025, 4, 12, 20, tzinfo=timezone.utc)
        GameLifecycleEvent.objects.create(
            game=self.game,
            event_kind=GameLifecycleEvent.Kind.SUSPENDED,
            recorded_at_utc=instant,
        )
        GameLifecycleEvent.objects.create(
            game=self.game,
            event_kind=GameLifecycleEvent.Kind.RESUMED,
            recorded_at_utc=instant,
        )
        self.assertEqual(GameLifecycleEvent.objects.filter(game=self.game).count(), 2)
        with self.assertRaises(ValidationError):
            GameLifecycleEvent.objects.create(
                game=self.game,
                event_kind=GameLifecycleEvent.Kind.COMPLETED,
                recorded_at_utc=datetime(2025, 4, 12, 20),
            )

    def test_participation_allows_two_teams_but_not_duplicate_triplet(self):
        for team in (self.home, self.away):
            PlayerGameParticipation.objects.create(
                game=self.game,
                player=self.player,
                team=team,
                participation_state=PlayerGameParticipation.State.APPEARED,
            )
        self.assertEqual(
            PlayerGameParticipation.objects.filter(player=self.player).count(), 2
        )
        with self.assertRaises(ValidationError):
            PlayerGameParticipation.objects.create(
                game=self.game, player=self.player, team=self.home
            )
        with self.assertRaises(ValidationError):
            PlayerGameParticipation.objects.create(
                game=self.game, player=self.player, team=self.other
            )
        with self.assertRaises(ValidationError):
            PlayerGameParticipation.objects.create(
                game=self.game,
                player=self.player,
                team=self.other,
                reported_pa_count=-1,
            )

    def test_pa_hr_and_dnp_conflicts(self):
        pa = PlateAppearance.objects.create(
            game=self.game,
            batter=self.player,
            batting_team=self.home,
            fielding_team=self.away,
            game_pa_ordinal=1,
            outcome_category=PlateAppearance.Outcome.HOME_RUN,
            batter_side_used="R",
        )
        HomeRunEvent.objects.create(plate_appearance=pa)
        self.assertEqual(self.player.bats, Player.Bats.SWITCH)
        pa.outcome_category = PlateAppearance.Outcome.NON_HR
        with self.assertRaises(ValidationError):
            pa.save()
        pa.outcome_category = PlateAppearance.Outcome.HOME_RUN
        with self.assertRaises(ValidationError):
            HomeRunEvent.objects.create(plate_appearance=pa)
        with self.assertRaises(ValidationError):
            PlayerGameParticipation.objects.create(
                game=self.game,
                player=self.player,
                team=self.home,
                participation_state=PlayerGameParticipation.State.DID_NOT_APPEAR,
            )
        with self.assertRaises(ValidationError):
            PlateAppearance.objects.create(
                game=self.game,
                batter=self.player,
                batting_team=self.home,
                fielding_team=self.away,
                game_pa_ordinal=1,
            )
        with self.assertRaises(ValidationError):
            PlateAppearance.objects.create(
                game=self.game,
                batter=self.player,
                batting_team=self.other,
                fielding_team=self.away,
            )
        non_hr = PlateAppearance.objects.create(
            game=self.game,
            batter=self.player,
            batting_team=self.home,
            fielding_team=self.away,
            outcome_category=PlateAppearance.Outcome.NON_HR,
        )
        with self.assertRaises(ValidationError):
            HomeRunEvent.objects.create(plate_appearance=non_hr)

    def test_finality_does_not_create_coverage_and_current_assessment_is_unique(self):
        self.assertEqual(self.game.finality, Game.Finality.FINAL)
        self.assertFalse(GameDataCoverage.objects.filter(game=self.game).exists())
        instant = datetime(2025, 4, 12, 20, tzinfo=timezone.utc)
        GameDataCoverage.objects.create(
            game=self.game,
            domain=GameDataCoverage.Domain.HR_EVENTS,
            state=GameDataCoverage.State.PARTIAL,
            assessed_at_utc=instant,
        )
        with self.assertRaises(ValidationError):
            GameDataCoverage.objects.create(
                game=self.game,
                domain=GameDataCoverage.Domain.HR_EVENTS,
                state=GameDataCoverage.State.COMPLETE,
                assessed_at_utc=instant,
            )
        self.assertEqual(GameDataCoverage.objects.get(game=self.game).state, "PARTIAL")

    def test_database_constraints_survive_bulk_insert(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Game.objects.bulk_create(
                [Game(season=self.season, home_team=self.home, away_team=self.home)]
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlayerTeamAffiliation.objects.bulk_create(
                [
                    PlayerTeamAffiliation(
                        player=self.player,
                        team=self.home,
                        effective_from_date=date(2025, 5, 2),
                        effective_to_date_exclusive=date(2025, 5, 1),
                    )
                ]
            )
        participation = PlayerGameParticipation(
            game=self.game, player=self.player, team=self.home
        )
        PlayerGameParticipation.objects.bulk_create([participation])
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlayerGameParticipation.objects.bulk_create(
                [
                    PlayerGameParticipation(
                        game=self.game, player=self.player, team=self.home
                    )
                ]
            )
