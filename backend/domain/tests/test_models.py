"""Structural B03/B04 invariants, independent of providers."""

from datetime import date, datetime, timezone
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from domain.models import (
    CoverageReason,
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
        with self.assertRaises(IntegrityError), transaction.atomic():
            Player.objects.create(mlb_id=self.player.mlb_id)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Season.objects.create(year=2025)
        Game.objects.create(
            season=self.season,
            home_team=self.home,
            away_team=self.away,
            mlb_game_pk=900,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
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
        invalid = PlayerTeamAffiliation(
            player=self.player,
            team=self.home,
            effective_from_date=date(2025, 5, 1),
            effective_to_date_exclusive=date(2025, 5, 1),
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()
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
        invalid = Game(season=self.season, home_team=self.home, away_team=self.home)
        with self.assertRaises(ValidationError):
            invalid.full_clean()
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
        invalid = GameLifecycleEvent(
            game=self.game,
            event_kind=GameLifecycleEvent.Kind.COMPLETED,
            recorded_at_utc=datetime(2025, 4, 12, 20),
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

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
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlayerGameParticipation.objects.create(
                game=self.game, player=self.player, team=self.home
            )
        invalid = PlayerGameParticipation(
            game=self.game, player=self.player, team=self.other
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()
        with self.assertRaises(ValidationError):
            PlayerGameParticipation(
                game=self.game,
                player=self.player,
                team=self.home,
                reported_pa_count=-1,
            ).full_clean()

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
            pa.full_clean()
        pa.outcome_category = PlateAppearance.Outcome.HOME_RUN
        with self.assertRaises(IntegrityError), transaction.atomic():
            HomeRunEvent.objects.create(plate_appearance=pa)
        with self.assertRaises(ValidationError):
            PlayerGameParticipation(
                game=self.game,
                player=self.player,
                team=self.home,
                participation_state=PlayerGameParticipation.State.DID_NOT_APPEAR,
            ).full_clean()
        with self.assertRaises(ValidationError):
            PlateAppearance(
                game=self.game,
                batter=self.player,
                batting_team=self.home,
                fielding_team=self.away,
                game_pa_ordinal=1,
            ).full_clean()
        with self.assertRaises(ValidationError):
            PlateAppearance(
                game=self.game,
                batter=self.player,
                batting_team=self.other,
                fielding_team=self.away,
            ).full_clean()
        non_hr = PlateAppearance.objects.create(
            game=self.game,
            batter=self.player,
            batting_team=self.home,
            fielding_team=self.away,
            outcome_category=PlateAppearance.Outcome.NON_HR,
        )
        with self.assertRaises(ValidationError):
            HomeRunEvent(plate_appearance=non_hr).full_clean()

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
        with self.assertRaises(IntegrityError), transaction.atomic():
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

    def test_save_does_not_implicitly_run_cross_row_validation(self):
        invalid = PlayerGameParticipation.objects.create(
            game=self.game, player=self.player, team=self.other
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()
        original_id = invalid.id
        invalid.id = uuid4()
        with self.assertRaises(ValidationError):
            invalid.save()
        invalid.id = original_id

    def test_unknown_affiliation_precision_with_known_bound(self):
        interval = PlayerTeamAffiliation.objects.create(
            player=self.player,
            team=self.home,
            effective_from_date=date(2025, 4, 1),
        )
        interval.full_clean()
        self.assertEqual(interval.boundary_precision, "UNKNOWN")
        self.assertIsNone(interval.effective_to_date_exclusive)

    def test_coverage_reason_and_domains_are_independent(self):
        instant = datetime(2025, 4, 12, 20, tzinfo=timezone.utc)
        hr = GameDataCoverage.objects.create(
            game=self.game,
            domain=GameDataCoverage.Domain.HR_EVENTS,
            state=GameDataCoverage.State.PARTIAL,
            reason_code=CoverageReason.HR_WITHOUT_PA,
            assessed_at_utc=instant,
        )
        pa = GameDataCoverage.objects.create(
            game=self.game,
            domain=GameDataCoverage.Domain.PLATE_APPEARANCES,
            state=GameDataCoverage.State.UNKNOWN,
            assessed_at_utc=instant,
        )
        hr.full_clean()
        pa.full_clean()
        self.assertEqual(hr.reason_code, "HR_WITHOUT_PA")
        self.assertIsNone(pa.reason_code)
        self.assertEqual(GameDataCoverage.objects.filter(game=self.game).count(), 2)

    def test_multiple_unordered_pas_and_two_hr_events(self):
        pas = [
            PlateAppearance.objects.create(
                game=self.game,
                batter=self.player,
                batting_team=self.home,
                fielding_team=self.away,
                outcome_category=PlateAppearance.Outcome.HOME_RUN,
            )
            for _ in range(2)
        ]
        events = [HomeRunEvent.objects.create(plate_appearance=pa) for pa in pas]
        self.assertEqual(len({event.id for event in events}), 2)
        self.assertTrue(all(pa.game_pa_ordinal is None for pa in pas))
