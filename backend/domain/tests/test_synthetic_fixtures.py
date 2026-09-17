"""B06 fixtures represent states, not KPI results or provider completeness."""

from datetime import date
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from domain.fixtures import (
    SequenceStep,
    build_batting_sequence,
    complete_step,
    fixture_uuid,
    load_synthetic_fixtures,
)
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
from ingestion.models import (
    FactSourceLink,
    Provider,
    ProviderAccessDecision,
    RawSourceSnapshot,
    SourceRecordReference,
)


class SyntheticFixtureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with patch("socket.socket.connect", side_effect=AssertionError("network used")):
            cls.manifest = load_synthetic_fixtures()

    def game(self, name):
        return Game.objects.get(pk=self.manifest.game_ids[name])

    def coverage(self, name, domain):
        return GameDataCoverage.objects.get(game=self.game(name), domain=domain)

    def test_first_and_repeated_load_preserve_uuid_and_counts(self):
        models = (
            Season,
            Team,
            Player,
            Venue,
            PlayerTeamAffiliation,
            Game,
            GameLifecycleEvent,
            PlayerGameParticipation,
            PlateAppearance,
            HomeRunEvent,
            GameDataCoverage,
            Provider,
            RawSourceSnapshot,
            SourceRecordReference,
            FactSourceLink,
        )
        before = {model: model.objects.count() for model in models}
        second = load_synthetic_fixtures()
        self.assertEqual(before, {model: model.objects.count() for model in models})
        self.assertEqual(self.manifest.season_id, second.season_id)
        self.assertEqual(dict(self.manifest.team_ids), dict(second.team_ids))
        self.assertEqual(dict(self.manifest.player_ids), dict(second.player_ids))
        self.assertEqual(dict(self.manifest.game_ids), dict(second.game_ids))
        self.assertEqual(dict(self.manifest.pa_ids), dict(second.pa_ids))
        self.assertEqual(dict(self.manifest.hr_event_ids), dict(second.hr_event_ids))
        self.assertEqual(Game.objects.count(), 25)
        self.assertEqual(PlateAppearance.objects.count(), 28)
        self.assertEqual(HomeRunEvent.objects.count(), 13)
        self.assertEqual(
            self.manifest.game_ids["multi_hr"], fixture_uuid("game:multi_hr")
        )

    def test_synthetic_identity_and_provenance_never_approve_provider(self):
        season = Season.objects.get(pk=self.manifest.season_id)
        provider = Provider.objects.get(code="SYNTHETIC")
        snapshot = RawSourceSnapshot.objects.get(provider=provider)
        self.assertEqual(season.year, 2099)
        self.assertIn("SYNTHETIC", season.label)
        self.assertFalse(provider.enabled)
        self.assertEqual(ProviderAccessDecision.objects.count(), 0)
        self.assertIsNone(snapshot.http_status)
        self.assertEqual(snapshot.resource_kind, "synthetic_fixture_manifest")
        self.assertIn("synthetic", snapshot.content_type)
        self.assertTrue(
            SourceRecordReference.objects.filter(provider=provider).exists()
        )
        self.assertTrue(
            FactSourceLink.objects.filter(source_record__provider=provider).exists()
        )
        self.assertFalse(Game.objects.exclude(mlb_game_pk__isnull=True).exists())
        self.assertFalse(Player.objects.exclude(mlb_id__isnull=True).exists())

    def test_ordinary_and_known_zero_require_explicit_coverage(self):
        for name in ("ordinary", "known_zero"):
            game = self.game(name)
            self.assertEqual(game.finality, Game.Finality.FINAL)
            self.assertEqual(game.game_type, Game.Type.REGULAR)
            self.assertEqual(
                self.coverage(name, GameDataCoverage.Domain.PLATE_APPEARANCES).state,
                GameDataCoverage.State.COMPLETE,
            )
            self.assertEqual(
                self.coverage(name, GameDataCoverage.Domain.HR_EVENTS).state,
                GameDataCoverage.State.COMPLETE,
            )
            self.assertTrue(PlateAppearance.objects.filter(game=game).exists())
            self.assertFalse(
                HomeRunEvent.objects.filter(plate_appearance__game=game).exists()
            )

    def test_partial_unknown_and_unassessed_do_not_become_known_zero(self):
        partial = self.game("partial_pa")
        unknown_hr = self.game("unknown_hr")
        unassessed = self.game("unassessed")
        for game in (partial, unknown_hr, unassessed):
            self.assertEqual(game.finality, Game.Finality.FINAL)
            self.assertNotEqual(
                GameDataCoverage.objects.get(
                    game=game, domain=GameDataCoverage.Domain.HR_EVENTS
                ).state,
                GameDataCoverage.State.COMPLETE,
            )
        self.assertEqual(
            self.coverage(
                "partial_pa", GameDataCoverage.Domain.PLATE_APPEARANCES
            ).state,
            GameDataCoverage.State.PARTIAL,
        )
        self.assertEqual(
            self.coverage("partial_pa", GameDataCoverage.Domain.HR_EVENTS).reason_code,
            "SOURCE_TRUNCATED",
        )
        self.assertEqual(
            self.coverage(
                "unknown_hr", GameDataCoverage.Domain.PLATE_APPEARANCES
            ).state,
            GameDataCoverage.State.COMPLETE,
        )
        self.assertFalse(
            PlayerGameParticipation.objects.filter(
                game=unassessed, player_id=self.manifest.player_ids["slugger"]
            ).exists()
        )
        unknown = PlayerGameParticipation.objects.get(
            game=self.game("unknown_participation"),
            player_id=self.manifest.player_ids["slugger"],
        )
        self.assertEqual(unknown.participation_state, "UNKNOWN")

    def test_multi_hr_has_two_distinct_pa_and_event_ids(self):
        game = self.game("multi_hr")
        pas = PlateAppearance.objects.filter(game=game, outcome_category="HOME_RUN")
        events = HomeRunEvent.objects.filter(plate_appearance__game=game)
        self.assertEqual(pas.count(), 2)
        self.assertEqual(events.count(), 2)
        self.assertEqual(len(set(pas.values_list("id", flat=True))), 2)
        self.assertEqual(
            len(set(events.values_list("plate_appearance_id", flat=True))), 2
        )
        self.assertEqual(PlateAppearance.objects.filter(game=game).count(), 4)
        self.assertEqual(
            FactSourceLink.objects.filter(
                entity_kind="HOME_RUN_EVENT",
                canonical_entity_id__in=events.values_list("id", flat=True),
            ).count(),
            2,
        )

    def test_walk_zero_pa_and_affirmative_dnp_remain_distinct(self):
        walk = PlayerGameParticipation.objects.get(
            game=self.game("walk_only"), player_id=self.manifest.player_ids["walker"]
        )
        runner = PlayerGameParticipation.objects.get(
            game=self.game("zero_pa"), player_id=self.manifest.player_ids["runner"]
        )
        dnp = PlayerGameParticipation.objects.get(
            game=self.game("dnp"), player_id=self.manifest.player_ids["slugger"]
        )
        self.assertEqual(walk.participation_state, "APPEARED")
        self.assertEqual(walk.pa_coverage, "COMPLETE")
        self.assertEqual(
            PlateAppearance.objects.filter(game=walk.game, batter=walk.player).count(),
            1,
        )
        self.assertEqual(runner.participation_state, "APPEARED")
        self.assertEqual(runner.pa_coverage, "COMPLETE")
        self.assertFalse(
            PlateAppearance.objects.filter(
                game=runner.game, batter=runner.player
            ).exists()
        )
        self.assertEqual(dnp.participation_state, "DID_NOT_APPEAR")
        self.assertFalse(
            PlateAppearance.objects.filter(game=dnp.game, batter=dnp.player).exists()
        )
        self.assertTrue(
            FactSourceLink.objects.filter(
                entity_kind="PLAYER_GAME_PARTICIPATION", canonical_entity_id=dnp.id
            ).exists()
        )

    def test_trade_return_and_both_team_representation_keep_one_player(self):
        slugger = Player.objects.get(pk=self.manifest.player_ids["slugger"])
        affiliations = list(
            PlayerTeamAffiliation.objects.filter(player=slugger)
            .order_by("effective_from_date")
            .values_list("team_id", flat=True)
        )
        self.assertEqual(
            affiliations,
            [
                self.manifest.team_ids["a"],
                self.manifest.team_ids["b"],
                self.manifest.team_ids["a"],
            ],
        )
        trade_games = self.manifest.scenarios["trade"]
        self.assertEqual(PlayerTeamAffiliation.objects.count(), 3)
        self.assertEqual(
            list(
                PlayerGameParticipation.objects.filter(
                    game_id__in=trade_games, player=slugger
                )
                .order_by("game__official_date")
                .values_list("team_id", flat=True)
            ),
            [
                self.manifest.team_ids["a"],
                self.manifest.team_ids["b"],
                self.manifest.team_ids["b"],
            ],
        )
        both = self.game("both_teams")
        self.assertEqual(
            set(
                PlayerGameParticipation.objects.filter(
                    game=both, player=slugger
                ).values_list("team_id", flat=True)
            ),
            {self.manifest.team_ids["a"], self.manifest.team_ids["b"]},
        )
        self.assertEqual(
            set(
                PlateAppearance.objects.filter(game=both, batter=slugger).values_list(
                    "batting_team_id", flat=True
                )
            ),
            {self.manifest.team_ids["a"], self.manifest.team_ids["b"]},
        )

    def test_doubleheader_suspension_and_unresolved_same_day_order(self):
        first, second = (
            Game.objects.get(pk=pk) for pk in self.manifest.scenarios["doubleheader"]
        )
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.official_date, second.official_date)
        self.assertEqual(
            (first.scheduled_game_number, second.scheduled_game_number), (1, 2)
        )
        suspended = self.game("suspended")
        kinds = set(
            GameLifecycleEvent.objects.filter(game=suspended).values_list(
                "event_kind", flat=True
            )
        )
        self.assertEqual(
            kinds, {"SCHEDULED", "STARTED", "SUSPENDED", "RESUMED", "COMPLETED"}
        )
        self.assertNotEqual(suspended.official_date, suspended.completed_at_utc.date())
        unordered = [
            Game.objects.get(pk=pk)
            for pk in self.manifest.scenarios["same_day_unordered"]
        ]
        self.assertEqual(unordered[0].official_date, unordered[1].official_date)
        self.assertTrue(all(game.scheduled_game_number is None for game in unordered))
        self.assertTrue(all(game.scheduled_start_at_utc is None for game in unordered))
        self.assertTrue(all(game.actual_start_at_utc is None for game in unordered))

    def test_known_sequence_and_generated_30_game_sequence(self):
        known = [
            Game.objects.get(pk=pk) for pk in self.manifest.scenarios["known_sequence"]
        ]
        self.assertEqual(len(known), 5)
        self.assertEqual(len({game.official_date for game in known}), 5)
        self.assertTrue(
            any(game.home_team_id == self.manifest.team_ids["a"] for game in known)
        )
        self.assertTrue(
            any(game.away_team_id == self.manifest.team_ids["a"] for game in known)
        )
        season = Season.objects.get(pk=self.manifest.season_id)
        player = Player.objects.get(pk=self.manifest.player_ids["slugger"])
        a = Team.objects.get(pk=self.manifest.team_ids["a"])
        b = Team.objects.get(pk=self.manifest.team_ids["b"])
        venue = Venue.objects.get(pk=fixture_uuid("venue:synthetic"))
        steps = tuple(
            complete_step(1 if index % 3 == 0 else 0, home=index % 2 == 0)
            for index in range(30)
        )
        ids = build_batting_sequence(
            key="30g_test",
            season=season,
            player=player,
            batting_team=a,
            opponent=b,
            venue=venue,
            start_date=date(2099, 6, 1),
            steps=steps,
        )
        self.assertEqual(len(ids), 30)
        self.assertEqual(len(set(ids)), 30)
        self.assertEqual(
            ids,
            build_batting_sequence(
                key="30g_test",
                season=season,
                player=player,
                batting_team=a,
                opponent=b,
                venue=venue,
                start_date=date(2099, 6, 1),
                steps=steps,
            ),
        )
        self.assertEqual(Game.objects.filter(pk__in=ids).count(), 30)

    def test_validation_failure_rolls_back_new_generated_game(self):
        season = Season.objects.get(pk=self.manifest.season_id)
        player = Player.objects.get(pk=self.manifest.player_ids["slugger"])
        a = Team.objects.get(pk=self.manifest.team_ids["a"])
        b = Team.objects.get(pk=self.manifest.team_ids["b"])
        venue = Venue.objects.get(pk=fixture_uuid("venue:synthetic"))
        key = "sequence:validation_probe:1"
        with patch.object(
            PlayerGameParticipation,
            "full_clean",
            side_effect=ValidationError("stopped"),
        ):
            with self.assertRaises(ValidationError):
                build_batting_sequence(
                    key="validation_probe",
                    season=season,
                    player=player,
                    batting_team=a,
                    opponent=b,
                    venue=venue,
                    start_date=date(2099, 7, 1),
                    steps=(complete_step(0),),
                )
        self.assertFalse(Game.objects.filter(pk=fixture_uuid(f"game:{key}")).exists())

    def test_builder_can_represent_dnp_partial_unknown_and_unordered_pas(self):
        step = SequenceStep(
            participation=PlayerGameParticipation.State.APPEARED,
            player_pa_coverage=PlayerGameParticipation.Coverage.PARTIAL,
            participation_coverage=GameDataCoverage.State.PARTIAL,
            game_pa_coverage=GameDataCoverage.State.PARTIAL,
            game_hr_coverage=GameDataCoverage.State.UNKNOWN,
            pa_count=2,
            hr_count=0,
            ordinal_known=False,
        )
        season = Season.objects.get(pk=self.manifest.season_id)
        player = Player.objects.get(pk=self.manifest.player_ids["slugger"])
        a = Team.objects.get(pk=self.manifest.team_ids["a"])
        b = Team.objects.get(pk=self.manifest.team_ids["b"])
        venue = Venue.objects.get(pk=fixture_uuid("venue:synthetic"))
        (game_id,) = build_batting_sequence(
            key="partial_unordered",
            season=season,
            player=player,
            batting_team=a,
            opponent=b,
            venue=venue,
            start_date=date(2099, 7, 2),
            steps=(step,),
        )
        self.assertEqual(
            list(
                PlateAppearance.objects.filter(game_id=game_id).values_list(
                    "game_pa_ordinal", flat=True
                )
            ),
            [None, None],
        )
        self.assertEqual(
            GameDataCoverage.objects.get(game_id=game_id, domain="HR_EVENTS").state,
            "UNKNOWN",
        )
