"""Exports preserve existing JSON evidence rather than computing new analytics."""

import csv
import io
import json
from copy import deepcopy
from datetime import date, datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from api.exports import render_csv, render_html, render_pdf
from domain.fixtures import (
    build_batting_sequence,
    complete_step,
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


class ExportContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = load_synthetic_fixtures()
        cls.revision = DatasetRevision.objects.create(
            committed_at_utc=datetime(2099, 5, 1, 12, tzinfo=timezone.utc)
        )
        cls.season = Season.objects.get(pk=cls.fixture.season_id)
        cls.team = Team.objects.get(pk=cls.fixture.team_ids["a"])
        cls.other = Team.objects.get(pk=cls.fixture.team_ids["b"])
        cls.player = Player.objects.get(pk=cls.fixture.player_ids["slugger"])
        cls.venue = Venue.objects.get(name="Synthetic Park")

    def setUp(self):
        self.client = APIClient()

    def families(self):
        return [
            "leaderboards/players/",
            f"teams/{self.team.id}/recurrence/",
            f"players/{self.player.id}/recurrence/",
            f"teams/{self.team.id}/home-runs/",
            f"players/{self.player.id}/home-runs/",
        ]

    def export(self, family, query="season=2099&cutoff=2099-04-10&format=csv"):
        return self.client.get(f"/api/v1/exports/{family}?{query}")

    def body(self, family, query="season=2099&cutoff=2099-04-10"):
        return self.client.get(f"/api/v1/{family}?{query}").json()

    @staticmethod
    def rows(response):
        return list(csv.DictReader(io.StringIO(response.content.decode("utf-8"))))

    def test_strict_format_filters_pagination_duplicates_and_get_only(self):
        for family in self.families():
            for query in (
                "season=2099",
                "season=2099&format=json",
                "season=2099&format=csv&format=pdf",
                "format=csv",
                "season=2099&format=csv&page=1",
                "season=2099&format=csv&page_size=100",
                "season=2099&format=csv&dataset_revision=1",
                f"season=2099&format=csv&cutoff={uuid4()}",
                "season=2099&format=csv&league=AL",
                "season=2099&format=csv&window=4G",
            ):
                with self.subTest(family=family, query=query):
                    response = self.export(family, query)
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("error", response.json())
                    self.assertEqual(
                        response.json()["meta"]["dataset_revision"],
                        str(self.revision.id),
                    )
            self.assertEqual(
                self.client.post(f"/api/v1/exports/{family}").status_code, 405
            )
        for kind in ("teams", "players"):
            self.assertEqual(self.export(f"{kind}/bad/recurrence/").status_code, 404)
            self.assertEqual(
                self.export(f"{kind}/{uuid4()}/home-runs/").status_code, 404
            )
        self.assertEqual(
            self.export(
                self.families()[1], "season=2099&format=csv&team=bad"
            ).status_code,
            400,
        )

    def test_revision_headers_and_empty_scope(self):
        for family in self.families():
            response = self.export(family, "season=2099&cutoff=2099-01-01&format=csv")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
            self.assertEqual(response["X-Dataset-Revision"], str(self.revision.id))
            self.assertEqual(response["X-Data-As-Of"], "2099-05-01T12:00:00Z")
            self.assertEqual(json.loads(response["X-Export-Scope"])["season"], 2099)
            self.assertIn('attachment; filename="mlb-', response["Content-Disposition"])
            self.assertIn("dataset_revision", response.content.decode())
        DatasetRevision.objects.all().delete()
        response = self.export(self.families()[0])
        self.assertEqual(response.status_code, 503)
        self.assertIsNone(response.json()["meta"]["dataset_revision"])

    def test_matrix_csv_is_one_cell_per_row_with_all_semantic_states(self):
        departed = Player.objects.create(display_name="Departed export player")
        PlayerTeamAffiliation.objects.create(
            player=departed,
            team=self.team,
            season=self.season,
            effective_from_date=date(2099, 4, 1),
            effective_to_date_exclusive=date(2099, 4, 3),
            boundary_precision="DATE",
        )
        PlayerTeamAffiliation.objects.create(
            player=departed,
            team=self.other,
            season=self.season,
            effective_from_date=date(2099, 4, 3),
            boundary_precision="DATE",
        )
        family = self.families()[1]
        payload = self.body(family)
        rows = self.rows(self.export(family))
        self.assertEqual(len(rows), len(payload["columns"]) * len(payload["rows"]))
        states = set()
        for record, (player, column, cell) in zip(
            rows,
            [
                (row, column, cell)
                for row in payload["rows"]
                for column, cell in zip(payload["columns"], row["cells"], strict=True)
            ],
            strict=True,
        ):
            self.assertEqual(record["game_id"], column["game_id"])
            self.assertEqual(record["player_id"], player["player"]["id"])
            self.assertEqual(record["cell_state"], cell["state"])
            self.assertEqual(
                record["hr_count"],
                "" if cell["hr_count"] is None else str(cell["hr_count"]),
            )
            self.assertEqual(record["reason"], cell["reason"] or "")
            self.assertEqual(json.loads(record["scope"]), payload["scope"])
            self.assertEqual(
                record["team.hr.state"], payload["metrics"]["team.hr"]["state"]
            )
            states.add(cell["state"])
        self.assertEqual(
            states,
            {
                "HR_COUNT",
                "KNOWN_ZERO",
                "DNP",
                "ZERO_PA_APPEARANCE",
                "NOT_WITH_TEAM",
                "UNKNOWN",
                "INCOMPLETE",
            },
        )
        doubleheader = [row for row in rows if row["official_date"] == "2099-04-09"]
        self.assertTrue(doubleheader)

    def test_player_recurrence_csv_preserves_summary_observations_and_gaps(self):
        ids = build_batting_sequence(
            key="export-gaps",
            season=self.season,
            player=self.player,
            batting_team=self.team,
            opponent=self.other,
            venue=self.venue,
            start_date=date(2099, 6, 1),
            steps=(
                complete_step(1),
                complete_step(1),
                complete_step(0),
                complete_step(1),
            ),
        )
        family = self.families()[2]
        query = "season=2099&window=7G&cutoff=2099-06-04"
        payload = self.body(family, query)
        rows = self.rows(self.export(family, query + "&format=csv"))
        observations = [row for row in rows if row["record_type"] == "OBSERVATION"]
        gaps = [row for row in rows if row["record_type"] == "GAP"]
        self.assertEqual(
            [row["game_id"] for row in observations],
            [item["game_id"] for item in payload["observations"]],
        )
        self.assertEqual(
            [row["non_hr_games.value"] for row in gaps],
            [str(item["non_hr_games"]["value"]) for item in payload["gaps"]],
        )
        self.assertIn("0", [row["non_hr_games.value"] for row in gaps])
        self.assertIn(str(ids[0]), [row["game_id"] for row in observations])
        for record, observation in zip(
            observations, payload["observations"], strict=True
        ):
            self.assertEqual(
                json.loads(record["represented_teams"]),
                observation["represented_teams"],
            )
            self.assertEqual(record["hr.state"], observation["hr"]["state"])
        self.assertEqual(
            len([row for row in rows if row["record_type"] == "SUMMARY"]),
            len(payload["metrics"]),
        )

    def test_unresolved_player_export_does_not_invent_observations(self):
        family = self.families()[2]
        rows = self.rows(self.export(family, "season=2099&format=csv"))
        self.assertTrue(rows)
        self.assertTrue(all(row["record_type"] == "SUMMARY" for row in rows))

    def test_hr_logs_partial_unknown_total_and_safe_events_agree_with_json(self):
        for state in (GameDataCoverage.State.PARTIAL, GameDataCoverage.State.UNKNOWN):
            GameDataCoverage.objects.filter(
                game_id=self.fixture.game_ids["multi_hr"], domain="HR_EVENTS"
            ).update(state=state)
            for family in self.families()[3:]:
                query = "season=2099&cutoff=2099-04-03&ordering=-official_date"
                payload = self.body(family, query)
                rows = self.rows(self.export(family, query + "&format=csv"))
                events = [row for row in rows if row["record_type"] == "EVENT"]
                self.assertEqual(
                    [row["event_id"] for row in events],
                    [event["id"] for event in payload["results"]],
                )
                self.assertEqual(len(events), 2)
                self.assertEqual(rows[0]["total_hr.value"], "")
                self.assertEqual(
                    rows[0]["total_hr.state"],
                    "INCOMPLETE" if state == "PARTIAL" else "UNKNOWN",
                )
                self.assertTrue(all(row["pitcher"] == "" for row in events))
                self.assertNotIn(
                    "storage_key",
                    self.export(family, query + "&format=csv").content.decode(),
                )
                self.assertTrue(events[0]["source_label"])

    def test_full_logs_not_json_page_and_complete_zero(self):
        for family in self.families()[3:]:
            query = "season=2099&cutoff=2099-04-03"
            page = self.body(family, query + "&page_size=1")
            events = [
                row
                for row in self.rows(self.export(family, query + "&format=csv"))
                if row["record_type"] == "EVENT"
            ]
            self.assertEqual(len(page["results"]), 1)
            self.assertEqual(len(events), 2)
            zero = self.rows(
                self.export(family, "season=2099&cutoff=2099-04-02&format=csv")
            )
            self.assertEqual(zero[0]["total_hr.state"], "VALUE")
            self.assertEqual(zero[0]["total_hr.value"], "0")
            self.assertEqual(len(zero), 1)

    def test_leaderboard_all_candidates_beyond_page_and_order_agreement(self):
        season = Season.objects.create(year=2100)
        for index in range(28):
            player = Player.objects.create(
                display_name=f"Export candidate {index:02}",
                primary_position="OF",
                bats="L",
            )
            build_batting_sequence(
                key=f"export-candidate-{index}",
                season=season,
                player=player,
                batting_team=self.team,
                opponent=self.other,
                venue=self.venue,
                start_date=date(2100, 6, 1),
                steps=(complete_step(index % 2),),
            )
        family = self.families()[0]
        for ordering in ("hr", "-hr", "name"):
            query = (
                f"season=2100&cutoff=2100-06-01&ordering={ordering}"
                f"&search=Export&position=OF&bats=L&team={self.team.id}"
            )
            payload = self.body(family, query + "&page_size=100")
            rows = self.rows(self.export(family, query + "&format=csv"))
            self.assertEqual(len(rows), 28)
            self.assertEqual(
                [row["player_id"] for row in rows],
                [row["player"]["id"] for row in payload["results"]],
            )
            self.assertTrue(any(row["player.hr.value"] == "0" for row in rows))
            self.assertTrue(
                all(row["represented_team_id"] == str(self.team.id) for row in rows)
            )

    def test_export_uses_same_payload_as_json_for_all_families(self):
        kinds = (
            "leaderboard",
            "team_recurrence",
            "player_recurrence",
            "team_home_runs",
            "player_home_runs",
        )
        for family, kind in zip(self.families(), kinds, strict=True):
            body = self.body(family)
            with patch(
                "api.exports.render_pdf", return_value=(b"%PDF-test", 1)
            ) as renderer:
                response = self.export(
                    family, "season=2099&cutoff=2099-04-10&format=pdf"
                )
            self.assertEqual(response.status_code, 200)
            args = renderer.call_args.args
            self.assertEqual(args[0], kind)
            # Export uses the same public fields, without JSON pagination.
            for key in (
                "scope",
                "coverage",
                "metrics",
                "columns",
                "rows",
                "observations",
                "gaps",
                "total_hr",
                "player",
                "team",
            ):
                if key in body:
                    self.assertEqual(
                        json.loads(json.dumps(args[1][key], default=str)), body[key]
                    )
            self.assertEqual(args[3], body["meta"])
            self.assertEqual(response["Content-Type"], "application/pdf")

    def test_pdf_engine_smoke_render_once_and_all_families(self):
        for family in self.families():
            response = self.export(family, "season=2099&cutoff=2099-04-03&format=pdf")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.content.startswith(b"%PDF-"))
            self.assertGreater(len(response.content), 1000)
        payload = self.body(self.families()[1], "season=2099&cutoff=2099-04-03")
        data, pages = render_pdf(
            "team_recurrence", payload, payload["scope"], payload["meta"]
        )
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertGreater(pages, 0)
        html = render_html(
            "team_recurrence", payload, payload["scope"], payload["meta"]
        )
        for text in (
            "A3 landscape",
            "Dataset revision",
            "data_as_of",
            "UNKNOWN",
            "INCOMPLETE",
            "Coverage",
            "Game",
            "Season HR",
        ):
            self.assertIn(text, html)

    def test_html_escaping_and_no_private_provenance(self):
        family = self.families()[3]
        payload = self.body(family, "season=2099&cutoff=2099-04-03")
        payload["team"]["display_name"] = '<img src="https://example.com/private">'
        html = render_html("team_home_runs", payload, payload["scope"], payload["meta"])
        self.assertNotIn("<img src=", html)
        self.assertIn("&lt;img", html)

    def test_player_gap_states_are_preserved_without_arithmetic(self):
        payload = self.body(self.families()[2], "season=2099&cutoff=2099-04-03")
        metric = payload["metrics"]["player.hr"]
        payload["gaps"] = [
            {
                "from_game_id": str(uuid4()),
                "to_game_id": str(uuid4()),
                "non_hr_games": {
                    **metric,
                    "value": None,
                    "state": "ORDER_UNVERIFIED",
                    "reason": "UNVERIFIED_GAME_ORDER",
                },
            }
        ]
        data, _ = render_csv(
            "player_recurrence", payload, payload["scope"], payload["meta"]
        )
        row = list(csv.DictReader(io.StringIO(data.decode())))[-1]
        self.assertEqual(row["non_hr_games.value"], "")
        self.assertEqual(row["non_hr_games.state"], "ORDER_UNVERIFIED")
        self.assertIn(
            "ORDER_UNVERIFIED",
            render_html(
                "player_recurrence", payload, payload["scope"], payload["meta"]
            ),
        )

    def test_season_representation_includes_every_horizontal_group_and_cell(self):
        # Small row population, but every column of a 162-game Season representation.
        payload = self.body(self.families()[1], "season=2099&cutoff=2099-04-03")
        column = payload["columns"][0]
        payload["columns"] = [
            {**column, "game_id": str(uuid4()), "official_date": f"Game-date-{i:03}"}
            for i in range(162)
        ]
        payload["rows"] = deepcopy(payload["rows"][:2])
        for row in payload["rows"]:
            row["cells"] = [deepcopy(row["cells"][0]) for _ in range(162)]
        data, count = render_csv(
            "team_recurrence", payload, payload["scope"], payload["meta"]
        )
        self.assertEqual(count, 162 * len(payload["rows"]))
        records = list(csv.DictReader(io.StringIO(data.decode())))
        self.assertEqual(
            {record["game_id"] for record in records},
            {item["game_id"] for item in payload["columns"]},
        )
        html = render_html(
            "team_recurrence", payload, payload["scope"], payload["meta"]
        )
        self.assertEqual(html.count("<section class='matrix-group'>"), 11)
        self.assertIn("Games 151-162 of 162", html)
        for column in payload["columns"]:
            self.assertEqual(html.count(column["official_date"]), 1)

    def test_current_drought_export_is_not_clamped_to_display_window(self):
        season = Season.objects.create(year=2101)
        build_batting_sequence(
            key="export-long-drought",
            season=season,
            player=self.player,
            batting_team=self.team,
            opponent=self.other,
            venue=self.venue,
            start_date=date(2101, 4, 1),
            steps=(complete_step(1), *(complete_step(0) for _ in range(41))),
        )
        query = "season=2101&window=30G&cutoff=2101-05-12"
        family = self.families()[2]
        payload = self.body(family, query)
        rows = self.rows(self.export(family, query + "&format=csv"))
        summaries = {
            row["metric_id"]: row for row in rows if row["record_type"] == "SUMMARY"
        }
        self.assertEqual(
            summaries["player.current_hr_drought_games"]["metric.value"], "41"
        )
        self.assertEqual(summaries["player.max_hr_drought_games"]["metric.value"], "30")
        self.assertEqual(payload["scope"]["actual_game_count"], 30)
        self.assertEqual(len(payload["observations"]), 30)

    def test_native_render_failure_is_safe_json_even_with_pdf_accept(self):
        with patch(
            "api.exports.render_pdf", side_effect=OSError("private/library/path")
        ):
            response = self.client.get(
                f"/api/v1/exports/{self.families()[1]}?season=2099&format=pdf",
                HTTP_ACCEPT="application/pdf",
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "EXPORT_UNAVAILABLE")
        self.assertNotIn("private/library", response.content.decode())

    def test_leaderboard_semantic_nulls_and_explicit_metric_fields(self):
        query = "season=2099&cutoff=2099-04-03&search=Slugger"
        for coverage, state in (("UNKNOWN", "UNKNOWN"), ("PARTIAL", "INCOMPLETE")):
            GameDataCoverage.objects.filter(
                game_id=self.fixture.game_ids["multi_hr"], domain="HR_EVENTS"
            ).update(state=coverage)
            body = self.body(self.families()[0], query)
            rows = self.rows(self.export(self.families()[0], query + "&format=csv"))
            self.assertTrue(rows)
            for record, source in zip(rows, body["results"], strict=True):
                self.assertEqual(record["player.hr.state"], state)
                self.assertEqual(record["player.hr.value"], "")
                for field in (
                    "state",
                    "value",
                    "reason",
                    "unit",
                    "numerator",
                    "denominator",
                ):
                    value = source["metrics"]["player.hr"][field]
                    self.assertEqual(
                        record[f"player.hr.{field}"],
                        "" if value is None else str(value),
                    )
                self.assertEqual(
                    record["dataset_revision"], body["meta"]["dataset_revision"]
                )
