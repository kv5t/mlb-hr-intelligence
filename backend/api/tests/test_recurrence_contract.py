"""B18 team-matrix and player-sequence public recurrence contracts."""

from datetime import date, datetime, timezone
from uuid import uuid4

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from domain.fixtures import (
    build_batting_sequence,
    complete_step,
    fixture_uuid,
    load_synthetic_fixtures,
)
from domain.models import (
    GameDataCoverage,
    Player,
    PlayerTeamAffiliation,
    Season,
    Team,
    Venue,
)
from ingestion.models import DatasetRevision


class RecurrenceApiTests(TestCase):
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

    def team(self, query="season=2099&cutoff=2099-04-10", team=None):
        team = team or self.a
        return self.client.get(f"/api/v1/teams/{team.id}/recurrence/?{query}")

    def player(self, query="season=2099", player=None):
        player = player or self.slugger
        return self.client.get(f"/api/v1/players/{player.id}/recurrence/?{query}")

    @staticmethod
    def save_valid(instance):
        instance.full_clean()
        instance.save()
        return instance

    def test_identity_required_season_and_strict_parameters(self):
        for path in (
            "/api/v1/teams/not-a-uuid/recurrence/?season=2099",
            f"/api/v1/teams/{uuid4()}/recurrence/?season=2099",
            "/api/v1/players/not-a-uuid/recurrence/?season=2099",
            f"/api/v1/players/{uuid4()}/recurrence/?season=2099",
        ):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.team(query="").status_code, 400)
        self.assertEqual(self.player(query="").status_code, 400)
        rejected = (
            "page=1",
            "page_size=10",
            "ordering=official_date",
            "dataset_revision=1",
            "search=x",
            "window=5G",
            "home_away=SIDE",
            f"cutoff={uuid4()}",
            "season=2099&season=2099",
        )
        for query in rejected:
            full = query if query.startswith("season=") else f"season=2099&{query}"
            with self.subTest(query=full):
                self.assertEqual(self.team(query=full).status_code, 400)
                self.assertEqual(self.player(query=full).status_code, 400)
        self.assertEqual(self.team(query="season=2099&team=x").status_code, 400)

    def test_team_matrix_has_shared_ordered_columns_and_all_fixture_states(self):
        response = self.team()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["scope"]["subject"], "TEAM")
        self.assertEqual(body["meta"]["dataset_revision"], str(self.revision.id))
        self.assertEqual(len(body["columns"]), 10)
        self.assertTrue(body["rows"])
        self.assertTrue(
            all(len(row["cells"]) == len(body["columns"]) for row in body["rows"])
        )
        self.assertEqual(
            [column["official_date"] for column in body["columns"]],
            sorted(column["official_date"] for column in body["columns"]),
        )
        states = {cell["state"] for row in body["rows"] for cell in row["cells"]}
        self.assertTrue(
            {
                "HR_COUNT",
                "KNOWN_ZERO",
                "DNP",
                "ZERO_PA_APPEARANCE",
                "UNKNOWN",
                "INCOMPLETE",
            }.issubset(states)
        )
        for row in body["rows"]:
            for cell in row["cells"]:
                if cell["state"] == "HR_COUNT":
                    self.assertGreaterEqual(cell["hr_count"], 1)
                    self.assertEqual(len(cell["home_run_event_ids"]), cell["hr_count"])
                elif cell["state"] == "KNOWN_ZERO":
                    self.assertEqual(cell["hr_count"], 0)
                    self.assertEqual(cell["home_run_event_ids"], [])
                else:
                    self.assertIsNone(cell["hr_count"])
                    self.assertEqual(cell["home_run_event_ids"], [])

    def test_not_with_team_requires_precise_temporal_evidence(self):
        departed = self.save_valid(
            Player(id=fixture_uuid("b18:departed"), display_name="Departed Player")
        )
        self.save_valid(
            PlayerTeamAffiliation(
                id=fixture_uuid("b18:departed:a"),
                player=departed,
                team=self.a,
                season=self.season,
                effective_from_date=date(2099, 4, 1),
                effective_to_date_exclusive=date(2099, 4, 3),
                boundary_precision=PlayerTeamAffiliation.BoundaryPrecision.DATE,
            )
        )
        self.save_valid(
            PlayerTeamAffiliation(
                id=fixture_uuid("b18:departed:b"),
                player=departed,
                team=self.b,
                season=self.season,
                effective_from_date=date(2099, 4, 3),
                boundary_precision=PlayerTeamAffiliation.BoundaryPrecision.DATE,
            )
        )
        body = self.team(query="season=2099&cutoff=2099-04-03").json()
        row = next(
            item for item in body["rows"] if item["player"]["id"] == str(departed.id)
        )
        states = [cell["state"] for cell in row["cells"]]
        self.assertIn("NOT_WITH_TEAM", states)
        self.assertIn("UNKNOWN", states)

        imprecise = self.save_valid(
            Player(id=fixture_uuid("b18:imprecise"), display_name="Imprecise Player")
        )
        self.save_valid(
            PlayerTeamAffiliation(
                id=fixture_uuid("b18:imprecise:a"),
                player=imprecise,
                team=self.a,
                season=self.season,
                effective_to_date_exclusive=date(2099, 4, 3),
                boundary_precision=PlayerTeamAffiliation.BoundaryPrecision.UNKNOWN,
            )
        )
        body = self.team(query="season=2099&cutoff=2099-04-03").json()
        row = next(
            item for item in body["rows"] if item["player"]["id"] == str(imprecise.id)
        )
        self.assertNotIn("NOT_WITH_TEAM", {cell["state"] for cell in row["cells"]})

    def test_matrix_positive_multi_hr_and_distinct_window_and_season_totals(self):
        body = self.team(query="season=2099&cutoff=2099-04-03").json()
        row = next(
            item
            for item in body["rows"]
            if item["player"]["id"] == str(self.slugger.id)
        )
        positive = next(cell for cell in row["cells"] if cell["state"] == "HR_COUNT")
        self.assertEqual(positive["hr_count"], 2)
        self.assertEqual(len(positive["home_run_event_ids"]), 2)
        self.assertEqual(row["window_hr"]["state"], "UNKNOWN")
        self.assertIsNone(row["window_hr"]["value"])
        self.assertEqual(row["player_season_hr"]["value"], 2)
        self.assertNotIn("represented_team", body["team"])

    def test_player_representing_both_teams_has_one_team_scoped_matrix_row(self):
        game_id = str(self.fixture.scenarios["both_teams"][0])

        def row_and_cell(team):
            body = self.team(
                team=team,
                query="season=2099&window=SEASON&cutoff=2099-04-19",
            ).json()
            player_rows = [
                row
                for row in body["rows"]
                if row["player"]["id"] == str(self.slugger.id)
            ]
            self.assertEqual(len(player_rows), 1)
            column_index = next(
                index
                for index, column in enumerate(body["columns"])
                if column["game_id"] == game_id
            )
            return player_rows[0], player_rows[0]["cells"][column_index]

        team_a_row, team_a_cell = row_and_cell(self.a)
        team_b_row, team_b_cell = row_and_cell(self.b)
        self.assertEqual(team_a_cell["state"], "HR_COUNT")
        self.assertEqual(team_a_cell["hr_count"], 1)
        self.assertEqual(len(team_a_cell["home_run_event_ids"]), 1)
        self.assertEqual(team_b_cell["state"], "KNOWN_ZERO")
        self.assertEqual(team_b_cell["hr_count"], 0)
        self.assertEqual(team_b_cell["home_run_event_ids"], [])
        self.assertEqual(team_a_row["player_season_hr"], team_b_row["player_season_hr"])

    def test_team_filters_windows_and_unavailable_resource_semantics(self):
        for window in ("7G", "15G", "30G", "60G", "SEASON"):
            self.assertEqual(
                self.team(
                    query=f"season=2099&window={window}&cutoff=2099-04-03"
                ).status_code,
                200,
            )
        home = self.team(
            query="season=2099&window=7G&home_away=HOME&cutoff=2099-04-03"
        ).json()
        away = self.team(
            query="season=2099&window=7G&home_away=AWAY&cutoff=2099-04-03"
        ).json()
        self.assertEqual(len(home["columns"]), 3)
        self.assertEqual(away["columns"], [])
        empty_team = self.save_valid(
            Team(id=fixture_uuid("b18:empty-team"), display_name="Empty Team")
        )
        empty = self.team(team=empty_team, query="season=2099")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json()["columns"], [])
        self.assertEqual(empty.json()["rows"], [])
        self.assertIsNone(empty.json()["scope"]["actual_game_count"])

    def test_matrix_queries_are_batched_across_cells(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.team()
        self.assertEqual(response.status_code, 200)
        self.assertLess(len(queries), 90)
        self.assertEqual(len(response.json()["columns"]), 10)
        self.assertEqual(len(response.json()["rows"]), 4)

    def test_doubleheader_columns_and_unresolved_last_n_boundary(self):
        body = self.team(query="season=2099&cutoff=2099-04-15").json()
        doubleheader = [
            column
            for column in body["columns"]
            if column["official_date"] == "2099-04-15"
        ]
        self.assertEqual(
            [column["scheduled_game_number"] for column in doubleheader], [1, 2]
        )
        build_batting_sequence(
            key="b18-boundary-tail",
            season=self.season,
            player=self.regular,
            batting_team=self.a,
            opponent=self.b,
            venue=self.venue,
            start_date=date(2099, 4, 26),
            steps=(complete_step(0),),
        )
        unresolved = self.team(query="season=2099&window=7G&cutoff=2099-04-26").json()
        self.assertEqual(unresolved["scope"]["selection_state"], "ORDER_UNVERIFIED")
        self.assertIsNone(unresolved["scope"]["actual_game_count"])
        self.assertEqual(unresolved["columns"], [])
        self.assertEqual(unresolved["rows"], [])

    def test_player_observations_and_gap_endpoint_records(self):
        game_ids = build_batting_sequence(
            key="b18-gaps",
            season=self.season,
            player=self.regular,
            batting_team=self.a,
            opponent=self.b,
            venue=self.venue,
            start_date=date(2099, 7, 1),
            steps=(
                complete_step(1),
                complete_step(0),
                complete_step(0),
                complete_step(1),
            ),
        )
        body = self.player(
            player=self.regular,
            query="season=2099&window=7G&cutoff=2099-07-04",
        ).json()
        observation_ids = [row["game_id"] for row in body["observations"]]
        expected_ids = [str(game_id) for game_id in game_ids]
        self.assertEqual(observation_ids[-4:], expected_ids)
        gap = body["gaps"][-1]
        self.assertEqual(gap["from_game_id"], expected_ids[0])
        self.assertEqual(gap["to_game_id"], expected_ids[3])
        self.assertEqual(gap["non_hr_games"]["value"], 2)
        self.assertEqual(body["metrics"]["player.avg_hr_gap_games"]["value"], 2)
        for observation in body["observations"][-4:]:
            self.assertEqual(observation["represented_teams"][0]["id"], str(self.a.id))
            self.assertEqual(observation["pa"]["state"], "VALUE")
            self.assertEqual(observation["hr"]["state"], "VALUE")

    def test_consecutive_and_multi_hr_gap_endpoints_count_games_not_events(self):
        game_ids = build_batting_sequence(
            key="b18-consecutive",
            season=self.season,
            player=self.regular,
            batting_team=self.a,
            opponent=self.b,
            venue=self.venue,
            start_date=date(2099, 8, 1),
            steps=(complete_step(2, 2), complete_step(1, 1)),
        )
        body = self.player(
            player=self.regular,
            query="season=2099&window=7G&cutoff=2099-08-02",
        ).json()
        gap = body["gaps"][-1]
        self.assertEqual(gap["from_game_id"], str(game_ids[0]))
        self.assertEqual(gap["to_game_id"], str(game_ids[1]))
        self.assertEqual(gap["non_hr_games"]["value"], 0)
        self.assertEqual(body["observations"][-2]["hr"]["value"], 2)

    def test_gap_does_not_bridge_an_incomplete_observation(self):
        game_ids = build_batting_sequence(
            key="b18-barrier",
            season=self.season,
            player=self.regular,
            batting_team=self.a,
            opponent=self.b,
            venue=self.venue,
            start_date=date(2099, 9, 1),
            steps=(complete_step(1), complete_step(0), complete_step(1)),
        )
        coverage = GameDataCoverage.objects.get(
            game_id=game_ids[1], domain=GameDataCoverage.Domain.HR_EVENTS
        )
        coverage.state = GameDataCoverage.State.PARTIAL
        coverage.reason_code = "SOURCE_TRUNCATED"
        coverage.save()
        body = self.player(
            player=self.regular,
            query="season=2099&window=7G&cutoff=2099-09-03",
        ).json()
        self.assertEqual(body["gaps"], [])
        self.assertEqual(
            body["metrics"]["player.avg_hr_gap_games"]["state"], "INCOMPLETE"
        )

    def test_public_gap_patterns_use_batting_games_and_real_endpoints(self):
        for index, (pattern, expected) in enumerate(
            (((1, 0, 1), 1), ((2, 0, 1), 1)), start=1
        ):
            with self.subTest(pattern=pattern):
                game_ids = build_batting_sequence(
                    key=f"b18-gap-pattern-{index}",
                    season=self.season,
                    player=self.regular,
                    batting_team=self.a,
                    opponent=self.b,
                    venue=self.venue,
                    start_date=date(2099, 9, 10 + index * 4),
                    steps=tuple(
                        complete_step(value, max(1, value)) for value in pattern
                    ),
                )
                cutoff = date(2099, 9, 12 + index * 4).isoformat()
                body = self.player(
                    player=self.regular,
                    query=f"season=2099&window=7G&cutoff={cutoff}",
                ).json()
                gap = next(
                    row
                    for row in body["gaps"]
                    if row["from_game_id"] == str(game_ids[0])
                    and row["to_game_id"] == str(game_ids[-1])
                )
                self.assertEqual(gap["non_hr_games"]["value"], expected)

    def test_player_current_drought_can_exceed_displayed_window(self):
        build_batting_sequence(
            key="b18-current-drought",
            season=self.season,
            player=self.regular,
            batting_team=self.a,
            opponent=self.b,
            venue=self.venue,
            start_date=date(2099, 10, 1),
            steps=(complete_step(1),) + (complete_step(0),) * 8,
        )
        body = self.player(player=self.regular, query="season=2099&window=7G").json()
        self.assertEqual(body["scope"]["actual_game_count"], 7)
        self.assertEqual(body["metrics"]["player.current_hr_drought_games"]["value"], 8)
        self.assertEqual(body["metrics"]["player.max_hr_drought_games"]["value"], 7)

    def test_unresolved_player_membership_never_fabricates_sequence_or_gaps(self):
        body = self.player(query="season=2099&cutoff=2099-04-10").json()
        self.assertIn(body["scope"]["selection_state"], {"UNKNOWN", "INCOMPLETE"})
        self.assertEqual(body["observations"], [])
        self.assertEqual(body["gaps"], [])

    def test_public_gap_contract_omits_materially_unordered_same_day_endpoints(self):
        unordered_ids = {
            str(game_id) for game_id in self.fixture.scenarios["same_day_unordered"]
        }
        body = self.player(query="season=2099&window=7G&cutoff=2099-04-25").json()
        self.assertEqual(body["scope"]["selection_state"], "VALUE")
        self.assertEqual(
            body["metrics"]["player.avg_hr_gap_games"]["state"],
            "ORDER_UNVERIFIED",
        )
        self.assertEqual(
            body["metrics"]["player.median_hr_gap_games"]["state"],
            "ORDER_UNVERIFIED",
        )
        for gap in body["gaps"]:
            self.assertTrue(
                {gap["from_game_id"], gap["to_game_id"]}.isdisjoint(unordered_ids)
            )

    def test_player_filters_and_current_metric_are_not_clamped_to_window(self):
        body = self.player(
            query=f"season=2099&window=7G&team={self.a.id}&home_away=HOME&cutoff=2099-04-03"
        ).json()
        self.assertEqual(body["scope"]["team_filter_id"], str(self.a.id))
        self.assertEqual(body["scope"]["home_away"], "HOME")
        self.assertEqual(len(body["observations"]), body["scope"]["actual_game_count"])
        self.assertNotIn("current_team", body["player"])
