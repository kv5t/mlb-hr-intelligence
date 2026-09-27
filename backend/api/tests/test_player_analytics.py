"""B14 player analytics, leaderboard and verified home-run log contracts."""

from datetime import date, datetime, timezone
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from domain.fixtures import fixture_uuid, load_synthetic_fixtures
from domain.models import (
    Game,
    GameDataCoverage,
    Player,
    PlayerGameParticipation,
    PlayerTeamAffiliation,
    Season,
    Team,
)
from ingestion.models import DatasetRevision


class PlayerAnalyticsApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = load_synthetic_fixtures()
        DatasetRevision.objects.create(
            committed_at_utc=datetime(2099, 5, 1, 12, tzinfo=timezone.utc)
        )
        cls.season = Season.objects.get(pk=cls.fixture.season_id)
        cls.slugger = Player.objects.get(pk=cls.fixture.player_ids["slugger"])
        cls.regular = Player.objects.get(pk=cls.fixture.player_ids["regular"])
        cls.a = Team.objects.get(pk=cls.fixture.team_ids["a"])
        cls.b = Team.objects.get(pk=cls.fixture.team_ids["b"])

    def setUp(self):
        self.client = APIClient()

    def detail(self, player=None, query="season=2099"):
        player = player or self.slugger
        return self.client.get(f"/api/v1/players/{player.id}/?{query}")

    def log(self, query="season=2099", player=None):
        player = player or self.slugger
        return self.client.get(f"/api/v1/players/{player.id}/home-runs/?{query}")

    def leaderboard(self, query="season=2099"):
        return self.client.get(f"/api/v1/leaderboards/players/?{query}")

    def save_valid(self, instance):
        instance.full_clean()
        instance.save()
        return instance

    def test_player_detail_requires_season_and_missing_player_is_404(self):
        self.assertEqual(self.detail(query="").status_code, 400)
        self.assertEqual(self.log(query="").status_code, 400)
        self.assertEqual(
            self.client.get(f"/api/v1/players/{uuid4()}/?season=2099").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/players/{uuid4()}/home-runs/?season=2099"
            ).status_code,
            404,
        )

    def test_known_player_without_latest_game_is_semantic_200(self):
        empty = Season(
            id=fixture_uuid("b14:empty-season"), year=2098, label="Synthetic empty"
        )
        empty.full_clean()
        empty.save()
        response = self.detail(query="season=2098")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["scope"]["selection_state"], "UNKNOWN")
        self.assertEqual(response.json()["metrics"]["player.hr"]["state"], "UNKNOWN")

    def test_player_detail_supports_every_window_and_semantic_200(self):
        expected_metrics = {
            "player.hr",
            "player.pa",
            "player.hr_per_pa",
            "player.pa_per_hr",
            "player.hr_per_game",
            "player.hr_games",
            "player.hr_game_pct",
            "player.multi_hr_games",
            "player.avg_hr_gap_games",
            "player.median_hr_gap_games",
            "player.current_hr_drought_games",
            "player.max_hr_drought_games",
            "player.current_hr_streak_games",
            "player.max_hr_streak_games",
            "player.current_hr_drought_pa",
            "player.max_hr_drought_pa",
        }
        for window in ("7G", "15G", "30G", "60G", "SEASON"):
            with self.subTest(window=window):
                response = self.detail(query=f"season=2099&window={window}")
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["scope"]["window"], window)
                self.assertEqual(set(body["metrics"]), expected_metrics)
                self.assertIn(
                    body["metrics"]["player.hr"]["state"],
                    {"VALUE", "UNKNOWN", "INCOMPLETE", "ORDER_UNVERIFIED"},
                )
                self.assertNotIn("current_team", body["player"])

    def test_player_scope_applies_team_home_away_cutoff_before_window(self):
        response = self.detail(
            query=(
                f"season=2099&window=7G&team={self.b.id}"
                "&home_away=HOME&cutoff=2099-04-19"
            )
        )
        self.assertEqual(response.status_code, 200)
        scope = response.json()["scope"]
        self.assertEqual(scope["team_filter_id"], str(self.b.id))
        self.assertEqual(scope["home_away"], "HOME")
        self.assertEqual(scope["cutoff_date"], "2099-04-19")
        self.assertLessEqual(scope["actual_game_count"], 7)

        home = self.detail(
            query=f"season=2099&team={self.a.id}&home_away=HOME&cutoff=2099-04-03"
        ).json()
        away = self.detail(
            query=f"season=2099&team={self.a.id}&home_away=AWAY&cutoff=2099-04-03"
        ).json()
        self.assertEqual(home["player"]["represented_team"]["id"], str(self.a.id))
        self.assertEqual(home["scope"]["actual_game_count"], 2)
        self.assertEqual(away["scope"]["actual_game_count"], 0)

    def test_player_detail_trade_scope_is_one_identity_and_fewer_than_n(self):
        response = self.detail(query="season=2099&window=30G&cutoff=2099-04-03")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["player"]["id"], str(self.slugger.id))
        self.assertLess(body["scope"]["actual_game_count"], 30)

    def test_common_parameters_are_strict_and_cutoff_is_date_only(self):
        paths = (
            f"/api/v1/players/{self.slugger.id}/?season=2099&bogus=1",
            "/api/v1/leaderboards/players/?season=2099&league=AL",
            "/api/v1/leaderboards/players/?season=2099&division=East",
            f"/api/v1/players/{self.slugger.id}/home-runs/?season=2099&cutoff={uuid4()}",
            "/api/v1/leaderboards/players/?season=2099&dataset_revision=1",
            "/api/v1/leaderboards/players/?season=2099&home_away=SIDE",
            "/api/v1/leaderboards/players/?season=2099&window=5G",
            "/api/v1/leaderboards/players/?season=2099&team=invalid",
            "/api/v1/leaderboards/players/?season=2099&cutoff=2099-02-30",
            "/api/v1/leaderboards/players/?season=2099&page=0",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 400)

    def test_player_reported_pa_mismatch_remains_incomplete(self):
        row = PlayerGameParticipation.objects.get(
            game_id=self.fixture.game_ids["multi_hr"],
            player=self.slugger,
            team=self.a,
        )
        row.reported_pa_count = 5
        row.save()
        body = self.detail(query="season=2099&cutoff=2099-04-03").json()
        for metric_id in ("player.pa", "player.hr_per_pa", "player.pa_per_hr"):
            with self.subTest(metric_id=metric_id):
                self.assertEqual(body["metrics"][metric_id]["state"], "INCOMPLETE")
                self.assertEqual(
                    body["metrics"][metric_id]["reason"], "BOX_SCORE_PA_MISMATCH"
                )

    def test_leaderboard_requires_season_filters_profiles_and_has_row_scopes(self):
        self.assertEqual(self.leaderboard(query="").status_code, 400)
        self.regular.primary_position = "1B"
        self.regular.bats = Player.Bats.RIGHT
        self.regular.full_clean()
        self.regular.save()
        response = self.leaderboard(
            query="season=2099&search=regular&position=1B&bats=R"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        row = body["results"][0]
        self.assertEqual(row["player"]["id"], str(self.regular.id))
        self.assertEqual(row["scope"]["subject_id"], str(self.regular.id))
        self.assertNotIn("score", row)
        self.assertNotIn("current_team", row["player"])

    def test_leaderboard_team_candidate_uses_historical_evidence(self):
        response = self.leaderboard(f"season=2099&team={self.b.id}&cutoff=2099-04-13")
        self.assertEqual(response.status_code, 200)
        rows = response.json()["results"]
        slugger = next(
            row for row in rows if row["player"]["id"] == str(self.slugger.id)
        )
        self.assertEqual(slugger["player"]["represented_team"]["id"], str(self.b.id))
        self.assertEqual(slugger["scope"]["team_filter_id"], str(self.b.id))

    def test_represented_team_requires_positive_selected_evidence(self):
        unrelated = Team.objects.get(pk=self.fixture.team_ids["c"])
        unrelated_body = self.detail(
            query=f"season=2099&team={unrelated.id}&cutoff=2099-04-03"
        ).json()
        self.assertIsNone(unrelated_body["player"]["represented_team"])

        before_join = self.detail(
            query=f"season=2099&team={self.b.id}&cutoff=2099-04-03"
        ).json()
        self.assertIsNone(before_join["player"]["represented_team"])

        evidenced = self.detail(
            query=f"season=2099&team={self.b.id}&cutoff=2099-04-13"
        ).json()
        self.assertEqual(evidenced["player"]["represented_team"]["id"], str(self.b.id))
        unfiltered = self.detail(query="season=2099&cutoff=2099-04-14").json()
        self.assertIsNone(unfiltered["player"]["represented_team"])

    def test_historical_cutoff_excludes_future_only_candidates(self):
        future = self.save_valid(
            Player(
                id=fixture_uuid("b15:future-player"),
                display_name="Fixture Future Player",
            )
        )
        self.save_valid(
            PlayerTeamAffiliation(
                id=fixture_uuid("b15:future-affiliation"),
                player=future,
                team=self.b,
                season=self.season,
                effective_from_date=date(2099, 6, 1),
                boundary_precision=PlayerTeamAffiliation.BoundaryPrecision.DATE,
            )
        )
        queries = (
            ("season=2099&cutoff=2099-04-03", True),
            (f"season=2099&team={self.b.id}&cutoff=2099-04-03", False),
        )
        for query, slugger_expected in queries:
            with self.subTest(query=query):
                ids = {
                    row["player"]["id"]
                    for row in self.leaderboard(query).json()["results"]
                }
                self.assertNotIn(str(future.id), ids)
                self.assertEqual(str(self.slugger.id) in ids, slugger_expected)

    def test_historical_cutoff_keeps_unknown_date_candidate_conservative(self):
        player = self.save_valid(
            Player(
                id=fixture_uuid("b15:unknown-date-player"),
                display_name="Fixture Unknown Date Player",
            )
        )
        game = self.save_valid(
            Game(
                id=fixture_uuid("b15:unknown-date-game"),
                season=self.season,
                home_team=self.a,
                away_team=self.b,
                game_type=Game.Type.REGULAR,
                status=Game.Status.COMPLETED,
                finality=Game.Finality.FINAL,
                official_date=None,
            )
        )
        self.save_valid(
            PlayerGameParticipation(
                id=fixture_uuid("b15:unknown-date-participation"),
                game=game,
                player=player,
                team=self.a,
                participation_state=PlayerGameParticipation.State.APPEARED,
                pa_coverage=PlayerGameParticipation.Coverage.COMPLETE,
                reported_pa_count=0,
            )
        )
        ids = {
            row["player"]["id"]
            for row in self.leaderboard("season=2099&cutoff=2099-04-03").json()[
                "results"
            ]
        }
        self.assertIn(str(player.id), ids)

    def test_leaderboard_default_metric_order_and_unavailable_last_both_ways(self):
        default = self.leaderboard("season=2099&cutoff=2099-04-03").json()
        self.assertEqual(default["results"][0]["player"]["id"], str(self.slugger.id))
        self.assertGreater(
            len({row["scope"]["actual_game_count"] for row in default["results"]}),
            1,
        )
        for ordering in ("hr", "-hr"):
            with self.subTest(ordering=ordering):
                rows = self.leaderboard(
                    f"season=2099&cutoff=2099-04-10&ordering={ordering}"
                ).json()["results"]
                states = [row["metrics"]["player.hr"]["state"] for row in rows]
                self.assertTrue(any(state != "VALUE" for state in states))
                first_unavailable = next(
                    index for index, state in enumerate(states) if state != "VALUE"
                )
                self.assertTrue(
                    all(state != "VALUE" for state in states[first_unavailable:])
                )
                values = [
                    row
                    for row in rows
                    if row["metrics"]["player.hr"]["state"] == "VALUE"
                ]
                zero_ids = [
                    row["player"]["id"]
                    for row in values
                    if row["metrics"]["player.hr"]["value"] == 0
                ]
                self.assertEqual(zero_ids, sorted(zero_ids))

        incomplete = self.leaderboard("season=2099&cutoff=2099-04-09").json()
        slugger = next(
            row
            for row in incomplete["results"]
            if row["player"]["id"] == str(self.slugger.id)
        )
        self.assertIn(
            slugger["metrics"]["player.hr"]["state"], {"UNKNOWN", "INCOMPLETE"}
        )

        coverage = GameDataCoverage.objects.get(
            game_id=self.fixture.game_ids["multi_hr"],
            domain=GameDataCoverage.Domain.HR_EVENTS,
        )
        coverage.state = GameDataCoverage.State.PARTIAL
        coverage.save()
        partial_rows = self.leaderboard("season=2099&cutoff=2099-04-03").json()[
            "results"
        ]
        partial_slugger = next(
            row for row in partial_rows if row["player"]["id"] == str(self.slugger.id)
        )
        self.assertEqual(partial_slugger["metrics"]["player.hr"]["state"], "INCOMPLETE")

    def test_every_documented_leaderboard_ordering_is_accepted(self):
        orderings = (
            "name",
            "hr",
            "pa",
            "hr_per_pa",
            "pa_per_hr",
            "hr_per_game",
            "hr_game_pct",
            "median_hr_gap_games",
            "current_hr_drought_games",
            "current_hr_streak_games",
        )
        for ordering in orderings:
            for prefix in ("", "-"):
                with self.subTest(ordering=f"{prefix}{ordering}"):
                    response = self.leaderboard(
                        f"season=2099&cutoff=2099-04-03&ordering={prefix}{ordering}"
                    )
                    self.assertEqual(response.status_code, 200)

    def test_leaderboard_team_filter_pagination_and_ordering_validation(self):
        response = self.leaderboard(
            f"season=2099&team={self.a.id}&home_away=HOME&page_size=1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertGreaterEqual(response.json()["count"], 1)
        self.assertEqual(
            response.json()["results"][0]["scope"]["team_filter_id"], str(self.a.id)
        )
        self.assertEqual(self.leaderboard("season=2099&page_size=101").status_code, 400)
        self.assertEqual(
            self.leaderboard("season=2099&ordering=power").status_code, 400
        )

    def test_hr_log_complete_zero_and_multi_hr_pagination(self):
        zero = self.log("season=2099&cutoff=2099-04-02")
        self.assertEqual(zero.status_code, 200)
        self.assertEqual(zero.json()["total_hr"]["state"], "VALUE")
        self.assertEqual(zero.json()["total_hr"]["value"], 0)
        self.assertEqual(zero.json()["results"], [])

        multi = self.log("season=2099&cutoff=2099-04-03&page_size=1")
        self.assertEqual(multi.status_code, 200)
        body = multi.json()
        self.assertEqual(body["count"], 2)
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["total_hr"]["value"], 2)
        self.assertIsNone(body["results"][0]["pitcher"])
        self.assertEqual(
            set(body["results"][0]["provenance"]), {"source_label", "retrieved_at"}
        )
        self.assertNotIn("storage_key", str(body))

    def test_hr_log_partial_or_unknown_total_keeps_known_events(self):
        game_id = self.fixture.game_ids["multi_hr"]
        coverage = GameDataCoverage.objects.get(
            game_id=game_id, domain=GameDataCoverage.Domain.HR_EVENTS
        )
        for state, expected in (
            (GameDataCoverage.State.PARTIAL, "INCOMPLETE"),
            (GameDataCoverage.State.UNKNOWN, "UNKNOWN"),
        ):
            with self.subTest(state=state):
                coverage.state = state
                coverage.save()
                body = self.log("season=2099&cutoff=2099-04-03").json()
                self.assertEqual(body["count"], 2)
                self.assertEqual(body["total_hr"]["state"], expected)
                self.assertIsNone(body["total_hr"]["value"])

    def test_hr_log_unresolved_membership_claims_no_selected_records(self):
        response = self.log("season=2099&cutoff=2099-04-09")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["results"], [])
        self.assertEqual(body["count"], 0)
        self.assertIn(body["scope"]["selection_state"], {"UNKNOWN", "INCOMPLETE"})
        self.assertIsNone(body["total_hr"]["value"])

    def test_hr_log_team_cutoff_ordering_and_trade_attribution(self):
        default = self.log(f"season=2099&window=7G&team={self.a.id}&cutoff=2099-04-19")
        ascending = self.log(
            f"season=2099&window=7G&team={self.a.id}"
            "&cutoff=2099-04-19&ordering=official_date"
        )
        descending = self.log(
            f"season=2099&window=7G&team={self.a.id}"
            "&cutoff=2099-04-19&ordering=-official_date"
        )
        self.assertEqual(ascending.status_code, 200)
        asc_rows = ascending.json()["results"]
        desc_rows = descending.json()["results"]
        self.assertEqual(
            [row["id"] for row in default.json()["results"]],
            [row["id"] for row in asc_rows],
        )
        self.assertGreaterEqual(len(asc_rows), 2)
        self.assertEqual(
            [row["official_date"] for row in desc_rows],
            sorted((row["official_date"] for row in asc_rows), reverse=True),
        )
        self.assertTrue(
            all(row["batting_team"]["id"] == str(self.a.id) for row in asc_rows)
        )

        home = self.log(
            f"season=2099&team={self.a.id}&home_away=HOME&cutoff=2099-04-03"
        ).json()
        away = self.log(
            f"season=2099&team={self.a.id}&home_away=AWAY&cutoff=2099-04-03"
        ).json()
        self.assertEqual(home["count"], 2)
        self.assertEqual(away["count"], 0)
