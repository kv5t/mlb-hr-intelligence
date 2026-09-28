"""B16 team detail and verified team home-run log contracts."""

from datetime import date, datetime, timezone
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from domain.fixtures import (
    build_batting_sequence,
    complete_step,
    fixture_uuid,
    load_synthetic_fixtures,
)
from domain.models import (
    Game,
    GameDataCoverage,
    HomeRunEvent,
    PlateAppearance,
    Player,
    Season,
    Team,
    Venue,
)
from ingestion.models import DatasetRevision


class TeamAnalyticsApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = load_synthetic_fixtures()
        cls.revision = DatasetRevision.objects.create(
            committed_at_utc=datetime(2099, 5, 1, 12, tzinfo=timezone.utc)
        )
        cls.season = Season.objects.get(pk=cls.fixture.season_id)
        cls.a = Team.objects.get(pk=cls.fixture.team_ids["a"])
        cls.b = Team.objects.get(pk=cls.fixture.team_ids["b"])
        cls.c = Team.objects.get(pk=cls.fixture.team_ids["c"])
        cls.slugger = Player.objects.get(pk=cls.fixture.player_ids["slugger"])
        cls.regular = Player.objects.get(pk=cls.fixture.player_ids["regular"])
        cls.venue = Venue.objects.get(name="Synthetic Park")

    def setUp(self):
        self.client = APIClient()

    def detail(self, team=None, query="season=2099"):
        team = team or self.a
        return self.client.get(f"/api/v1/teams/{team.id}/?{query}")

    def log(self, team=None, query="season=2099"):
        team = team or self.a
        return self.client.get(f"/api/v1/teams/{team.id}/home-runs/?{query}")

    @staticmethod
    def save_valid(instance):
        instance.full_clean()
        instance.save()
        return instance

    def test_team_identity_errors_and_required_season(self):
        for path in (
            "/api/v1/teams/not-a-uuid/?season=2099",
            f"/api/v1/teams/{uuid4()}/?season=2099",
            "/api/v1/teams/not-a-uuid/home-runs/?season=2099",
            f"/api/v1/teams/{uuid4()}/home-runs/?season=2099",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.detail(query="").status_code, 400)
        self.assertEqual(self.log(query="").status_code, 400)

    def test_team_detail_windows_scope_filters_cutoff_and_metrics(self):
        expected = {
            "team.hr",
            "team.pa",
            "team.hr_per_pa",
            "team.pa_per_hr",
            "team.hr_per_game",
            "team.hr_games",
            "team.hr_game_pct",
            "team.multi_hr_games",
            "team.avg_hr_gap_games",
            "team.median_hr_gap_games",
            "team.current_hr_drought_games",
            "team.max_hr_drought_games",
            "team.current_hr_streak_games",
            "team.max_hr_streak_games",
        }
        for window in ("7G", "15G", "30G", "60G", "SEASON"):
            with self.subTest(window=window):
                response = self.detail(query=f"season=2099&window={window}")
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["scope"]["subject"], "TEAM")
                self.assertEqual(body["scope"]["subject_id"], str(self.a.id))
                self.assertIsNone(body["scope"]["team_filter_id"])
                self.assertEqual(set(body["metrics"]), expected)

        home = self.detail(
            query="season=2099&window=7G&home_away=HOME&cutoff=2099-04-03"
        ).json()["scope"]
        away = self.detail(
            query="season=2099&window=7G&home_away=AWAY&cutoff=2099-04-03"
        ).json()["scope"]
        self.assertEqual(home["actual_game_count"], 3)
        self.assertEqual(away["actual_game_count"], 0)
        self.assertEqual(home["cutoff_date"], "2099-04-03")
        self.assertLess(home["actual_game_count"], 7)

    def test_known_team_without_latest_games_is_semantic_200(self):
        empty = self.save_valid(
            Team(id=fixture_uuid("b16:empty-team"), display_name="Synthetic Empty")
        )
        response = self.detail(empty)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["scope"]["selection_state"], "UNKNOWN")
        self.assertIsNone(body["scope"]["actual_game_count"])
        self.assertEqual(body["metrics"]["team.hr"]["state"], "UNKNOWN")

    def test_team_metrics_preserve_coverage_integrity_zero_and_multi_hr(self):
        body = self.detail(query="season=2099&cutoff=2099-04-03").json()
        self.assertEqual(body["metrics"]["team.hr"]["value"], 2)
        self.assertEqual(body["metrics"]["team.hr_games"]["value"], 1)
        self.assertEqual(body["metrics"]["team.multi_hr_games"]["value"], 1)

        zero = self.detail(self.c, "season=2099&cutoff=2099-04-11").json()
        self.assertEqual(zero["metrics"]["team.hr"]["state"], "VALUE")
        self.assertEqual(zero["metrics"]["team.hr"]["value"], 0)

        pa_coverage = GameDataCoverage.objects.get(
            game_id=self.fixture.game_ids["multi_hr"],
            domain=GameDataCoverage.Domain.PLATE_APPEARANCES,
        )
        pa_coverage.state = GameDataCoverage.State.PARTIAL
        pa_coverage.reason_code = "PA_COUNT_MISMATCH"
        pa_coverage.save()
        partial = self.detail(query="season=2099&cutoff=2099-04-03").json()
        for metric in ("team.pa", "team.hr_per_pa", "team.pa_per_hr"):
            self.assertEqual(partial["metrics"][metric]["state"], "INCOMPLETE")

    def test_canonical_hr_mismatch_overrides_complete_coverage(self):
        self.save_valid(
            PlateAppearance(
                id=fixture_uuid("b16:unmatched-hr-pa"),
                game_id=self.fixture.game_ids["multi_hr"],
                batter=self.regular,
                batting_team=self.a,
                fielding_team=self.b,
                game_pa_ordinal=6,
                outcome_category=PlateAppearance.Outcome.HOME_RUN,
            )
        )
        body = self.detail(query="season=2099&cutoff=2099-04-03").json()
        self.assertEqual(body["metrics"]["team.hr"]["state"], "INCOMPLETE")
        self.assertEqual(body["metrics"]["team.hr"]["reason"], "BOX_SCORE_HR_MISMATCH")

    def test_current_recurrence_can_extend_before_displayed_window(self):
        build_batting_sequence(
            key="b16-current-drought",
            season=self.season,
            player=self.regular,
            batting_team=self.a,
            opponent=self.b,
            venue=self.venue,
            start_date=date(2099, 6, 1),
            steps=(
                complete_step(1),
                complete_step(0),
                complete_step(0),
                complete_step(0),
                complete_step(0),
                complete_step(0),
                complete_step(0),
                complete_step(0),
                complete_step(0),
            ),
        )
        body = self.detail(query="season=2099&window=7G").json()
        self.assertEqual(body["scope"]["actual_game_count"], 7)
        self.assertEqual(body["metrics"]["team.current_hr_drought_games"]["value"], 8)
        self.assertEqual(body["metrics"]["team.max_hr_drought_games"]["value"], 7)

    def test_revision_and_coverage_are_public(self):
        body = self.detail(query="season=2099&cutoff=2099-04-03").json()
        self.assertEqual(body["meta"]["dataset_revision"], str(self.revision.id))
        self.assertEqual(body["meta"]["data_as_of"], "2099-05-01T12:00:00Z")
        self.assertEqual(
            {row["domain"] for row in body["coverage"]},
            set(GameDataCoverage.Domain.values),
        )

    def test_team_hr_log_complete_zero_multi_hr_and_opponent_exclusion(self):
        zero = self.log(self.c, "season=2099&cutoff=2099-04-11").json()
        self.assertEqual(zero["results"], [])
        self.assertEqual(zero["count"], 0)
        self.assertEqual(zero["total_hr"]["value"], 0)

        game = Game.objects.get(pk=self.fixture.game_ids["multi_hr"])
        opponent_pa = self.save_valid(
            PlateAppearance(
                id=fixture_uuid("b16:opponent-hr-pa"),
                game=game,
                batter=self.regular,
                batting_team=self.b,
                fielding_team=self.a,
                game_pa_ordinal=5,
                outcome_category=PlateAppearance.Outcome.HOME_RUN,
            )
        )
        opponent_hr = self.save_valid(
            HomeRunEvent(
                id=fixture_uuid("b16:opponent-hr"), plate_appearance=opponent_pa
            )
        )
        body = self.log(query="season=2099&cutoff=2099-04-03").json()
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["total_hr"]["value"], 2)
        self.assertNotIn(str(opponent_hr.id), {row["id"] for row in body["results"]})

    def test_team_hr_log_partial_and_unknown_totals_keep_known_events(self):
        coverage = GameDataCoverage.objects.get(
            game_id=self.fixture.game_ids["multi_hr"],
            domain=GameDataCoverage.Domain.HR_EVENTS,
        )
        for state, expected in (
            (GameDataCoverage.State.PARTIAL, "INCOMPLETE"),
            (GameDataCoverage.State.UNKNOWN, "UNKNOWN"),
        ):
            with self.subTest(state=state):
                coverage.state = state
                coverage.save()
                body = self.log(query="season=2099&cutoff=2099-04-03").json()
                self.assertEqual(body["count"], 2)
                self.assertEqual(len(body["results"]), 2)
                self.assertEqual(body["total_hr"]["state"], expected)
                self.assertIsNone(body["total_hr"]["value"])

    def test_team_hr_log_filters_ordering_pagination_and_safe_events(self):
        default = self.log(
            query="season=2099&window=7G&home_away=HOME&cutoff=2099-04-19"
        ).json()
        descending = self.log(
            query=(
                "season=2099&window=7G&home_away=HOME&cutoff=2099-04-19"
                "&ordering=-official_date"
            )
        ).json()
        self.assertEqual(
            [row["official_date"] for row in default["results"]],
            sorted(row["official_date"] for row in default["results"]),
        )
        self.assertEqual(
            [row["official_date"] for row in descending["results"]],
            sorted(
                (row["official_date"] for row in descending["results"]), reverse=True
            ),
        )
        self.assertTrue(
            all(
                row["batting_team"]["id"] == str(self.a.id)
                for row in default["results"]
            )
        )
        self.assertTrue(any(row["pitcher"] is None for row in default["results"]))
        for row in default["results"]:
            if row["provenance"]:
                self.assertEqual(
                    set(row["provenance"]), {"source_label", "retrieved_at"}
                )

        paged = self.log(
            query="season=2099&cutoff=2099-04-19&page_size=1&page=2"
        ).json()
        self.assertEqual(len(paged["results"]), 1)
        self.assertGreater(paged["count"], len(paged["results"]))
        self.assertEqual(paged["scope"]["home_away"], "ALL")

        away = self.log(query="season=2099&home_away=AWAY&cutoff=2099-04-03").json()
        self.assertEqual(away["scope"]["actual_game_count"], 0)
        self.assertEqual(away["results"], [])

    def test_unresolved_team_membership_never_claims_event_results(self):
        game = Game.objects.get(pk=self.fixture.game_ids["multi_hr"])
        game.official_date = None
        game.save()
        body = self.log(query="season=2099&window=7G&cutoff=2099-04-03").json()
        self.assertEqual(body["scope"]["selection_state"], "UNKNOWN")
        self.assertEqual(body["results"], [])
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["total_hr"]["state"], "UNKNOWN")

    def test_team_hr_log_same_day_game_order_is_stable(self):
        game_two = Game.objects.get(pk=self.fixture.game_ids["doubleheader_2"])
        pa = PlateAppearance.objects.get(game=game_two, batter=self.slugger)
        pa.outcome_category = PlateAppearance.Outcome.HOME_RUN
        pa.save()
        second_event = self.save_valid(
            HomeRunEvent(
                id=fixture_uuid("b16:doubleheader-second-hr"), plate_appearance=pa
            )
        )
        first_event_id = str(self.fixture.hr_event_ids["doubleheader_1:1"])
        ascending = self.log(query="season=2099&cutoff=2099-04-15").json()["results"]
        descending = self.log(
            query="season=2099&cutoff=2099-04-15&ordering=-official_date"
        ).json()["results"]
        same_day_asc = [
            row["id"] for row in ascending if row["official_date"] == "2099-04-15"
        ]
        same_day_desc = [
            row["id"] for row in descending if row["official_date"] == "2099-04-15"
        ]
        self.assertEqual(same_day_asc, [first_event_id, str(second_event.id)])
        self.assertEqual(same_day_desc, [str(second_event.id), first_event_id])

    def test_team_endpoints_reject_unsupported_and_invalid_queries(self):
        paths = (
            f"/api/v1/teams/{self.a.id}/?season=2099&team={self.a.id}",
            f"/api/v1/teams/{self.a.id}/?season=2099&dataset_revision=1",
            f"/api/v1/teams/{self.a.id}/?season=2099&window=5G",
            f"/api/v1/teams/{self.a.id}/?season=2099&home_away=SIDE",
            f"/api/v1/teams/{self.a.id}/?season=2099&cutoff={uuid4()}",
            f"/api/v1/teams/{self.a.id}/?season=2099&season=2098",
            f"/api/v1/teams/{self.a.id}/home-runs/?season=2099&ordering=hr",
            f"/api/v1/teams/{self.a.id}/home-runs/?season=2099&page=0",
            f"/api/v1/teams/{self.a.id}/home-runs/?season=2099&page_size=101",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 400)
