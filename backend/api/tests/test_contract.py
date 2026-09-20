"""B11 public JSON, revision, discovery, game and Today contracts."""

from datetime import date, datetime, timezone
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from analytics.values import MetricState, MetricValue
from api.serializers import metric_value
from domain.fixtures import fixture_uuid, load_synthetic_fixtures
from domain.models import (
    Game,
    GameDataCoverage,
    PlateAppearance,
    Player,
    Season,
    Team,
)
from ingestion.models import DatasetRevision


class NoRevisionTests(TestCase):
    def test_missing_revision_is_503_without_fabricated_zero(self):
        response = APIClient().get("/api/v1/seasons/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "REVISION_UNAVAILABLE")
        self.assertEqual(
            response.json()["meta"], {"dataset_revision": None, "data_as_of": None}
        )


class ApiContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = load_synthetic_fixtures()
        cls.revision = DatasetRevision.objects.create(
            committed_at_utc=datetime(2099, 5, 1, 12, tzinfo=timezone.utc)
        )
        cls.season = Season.objects.get(pk=cls.fixture.season_id)
        cls.a = Team.objects.get(pk=cls.fixture.team_ids["a"])
        cls.b = Team.objects.get(pk=cls.fixture.team_ids["b"])
        cls.slugger = Player.objects.get(pk=cls.fixture.player_ids["slugger"])

    def setUp(self):
        self.client = APIClient()

    def game(self, key):
        return Game.objects.get(pk=self.fixture.game_ids[key])

    def assert_meta(self, response):
        self.assertEqual(
            response.json()["meta"],
            {
                "dataset_revision": str(self.revision.id),
                "data_as_of": "2099-05-01T12:00:00Z",
            },
        )

    def test_metricvalue_zero_and_decimal_render_as_json_numbers(self):
        from rest_framework.renderers import JSONRenderer

        zero = JSONRenderer().render(
            metric_value(MetricValue(MetricState.VALUE, 0, "HR", numerator=0))
        )
        ratio = JSONRenderer().render(
            metric_value(
                MetricValue(
                    MetricState.VALUE,
                    Decimal("0.5"),
                    "HR/PA",
                    numerator=1,
                    denominator=2,
                )
            )
        )
        self.assertIn(b'"value":0', zero)
        self.assertIn(b'"value":0.5', ratio)
        self.assertNotIn(b'"value":"0.5"', ratio)
        unavailable = JSONRenderer().render(
            metric_value(MetricValue(MetricState.UNKNOWN, unit="HR"))
        )
        self.assertIn(b'"value":null', unavailable)

    def test_meta_one_revision_and_no_private_revision_fields(self):
        response = self.client.get("/api/v1/games/")
        self.assertEqual(response.status_code, 200)
        self.assert_meta(response)
        self.assertEqual(
            set(response.json()["meta"]), {"dataset_revision", "data_as_of"}
        )
        self.assertNotIn("changed_game_ids", response.content.decode())
        self.assertEqual(response.json()["results"][0]["hr_count"]["unit"], "HR")

    def test_unknown_and_historical_revision_queries_rejected(self):
        for path in ("/api/v1/seasons/?dataset_revision=1", "/api/v1/games/?bogus=1"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], "INVALID_FILTER")
                self.assert_meta(response)

    def test_get_only_errors_have_envelope(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)("/api/v1/games/")
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response.json()["error"]["code"], "METHOD_NOT_ALLOWED")
                self.assert_meta(response)

    def test_seasons_pagination_order_and_validation(self):
        other = Season(
            id=fixture_uuid("b11:season"), year=2098, label="Synthetic earlier"
        )
        other.full_clean()
        other.save()
        response = self.client.get("/api/v1/seasons/?page_size=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual(response.json()["results"][0]["year"], 2099)
        self.assertIn("page_size=1", response.json()["next"])
        for suffix in ("page=0", "page_size=101", "page_size=abc", "page=999"):
            self.assertEqual(
                self.client.get(f"/api/v1/seasons/?{suffix}").status_code, 400
            )

    def test_teams_search_league_division_order_and_season(self):
        self.a.display_name = "Synthetic Alpha"
        self.a.abbreviation = "SA"
        self.a.league = "Fixture League"
        self.a.division = "Fixture East"
        self.a.full_clean()
        self.a.save()
        response = self.client.get(
            "/api/v1/teams/?search=alpha&league=Fixture%20League&division=Fixture%20East&ordering=-name"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in response.json()["results"]], [str(self.a.id)]
        )
        self.assertEqual(self.client.get("/api/v1/teams/?ordering=hr").status_code, 400)
        self.assertGreater(
            self.client.get("/api/v1/teams/?season=2099").json()["count"], 0
        )

    def test_players_are_discovery_only_with_known_team_association(self):
        self.slugger.primary_position = "1B"
        self.slugger.full_clean()
        self.slugger.save()
        response = self.client.get(
            f"/api/v1/players/?season=2099&team={self.b.id}&search=Slugger&position=1B&bats=UNKNOWN"
        )
        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        self.assertEqual(row["id"], str(self.slugger.id))
        self.assertEqual(row["represented_team"]["id"], str(self.b.id))
        self.assertNotIn("current_team", row)
        self.assertNotIn("metrics", row)
        unfiltered = self.client.get("/api/v1/players/?search=Slugger").json()[
            "results"
        ][0]
        self.assertIsNone(unfiltered["represented_team"])
        self.assertEqual(self.client.get("/api/v1/players/?bats=X").status_code, 400)
        self.assertEqual(
            self.client.get("/api/v1/players/?ordering=hr").status_code, 400
        )

    def test_games_filter_doubleheader_nonfinal_and_stable_count(self):
        nonfinal_game = Game(
            id=fixture_uuid("b11:nonfinal"),
            season=self.season,
            home_team=self.a,
            away_team=self.b,
            venue=self.game("known_zero").venue,
            official_date=date(2099, 4, 20),
            game_type=Game.Type.OTHER,
            status=Game.Status.POSTPONED,
            finality=Game.Finality.NOT_FINAL,
        )
        nonfinal_game.full_clean()
        nonfinal_game.save()
        response = self.client.get(
            f"/api/v1/games/?season=2099&date_from=2099-04-15&date_to=2099-04-15&team={self.a.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        ids = [row["id"] for row in response.json()["results"]]
        self.assertEqual(
            ids,
            [
                str(self.fixture.game_ids["doubleheader_1"]),
                str(self.fixture.game_ids["doubleheader_2"]),
            ],
        )
        nonfinal = self.client.get("/api/v1/games/?status=POSTPONED")
        self.assertEqual(nonfinal.status_code, 200)
        self.assertEqual(nonfinal.json()["count"], 1)
        self.assertTrue(
            all(
                row["hr_count"]["state"] != "VALUE"
                for row in nonfinal.json()["results"]
            )
        )
        self.assertIn("hr_count", nonfinal.json()["results"][0])
        self.assertEqual(
            self.client.get("/api/v1/games/?ordering=score").status_code, 400
        )

    def test_game_hr_count_proof_zero_positive_partial_unknown_and_mismatch(self):
        for key, state, value in (
            ("known_zero", "VALUE", 0),
            ("multi_hr", "VALUE", 2),
            ("partial_pa", "UNKNOWN", None),
            ("unknown_hr", "UNKNOWN", None),
        ):
            with self.subTest(key=key):
                game = self.game(key)
                result = self.client.get(f"/api/v1/games/{game.id}/")
                self.assertEqual(result.status_code, 200)
                self.assertEqual(
                    (
                        result.json()["game"]["hr_count"]["state"],
                        result.json()["game"]["hr_count"]["value"],
                    ),
                    (state, value),
                )
        game = self.game("known_zero")
        coverage = GameDataCoverage.objects.get(
            game=game, domain=GameDataCoverage.Domain.HR_EVENTS
        )
        coverage.state = GameDataCoverage.State.PARTIAL
        coverage.full_clean()
        coverage.save()
        self.assertEqual(
            self.client.get(f"/api/v1/games/{game.id}/").json()["game"]["hr_count"][
                "state"
            ],
            "INCOMPLETE",
        )
        coverage.state = GameDataCoverage.State.COMPLETE
        coverage.full_clean()
        coverage.save()
        pa = PlateAppearance.objects.get(game=game, batter=self.slugger)
        pa.outcome_category = PlateAppearance.Outcome.HOME_RUN
        pa.full_clean()
        pa.save()
        mismatch = self.client.get(f"/api/v1/games/{game.id}/").json()["game"][
            "hr_count"
        ]
        self.assertEqual(
            (mismatch["state"], mismatch["reason"]),
            ("INCOMPLETE", "BOX_SCORE_HR_MISMATCH"),
        )

        multi = self.game("multi_hr")
        coverage = GameDataCoverage.objects.get(
            game=multi, domain=GameDataCoverage.Domain.HR_EVENTS
        )
        coverage.state = GameDataCoverage.State.PARTIAL
        coverage.full_clean()
        coverage.save()
        detail = self.client.get(f"/api/v1/games/{multi.id}/").json()
        self.assertEqual(detail["game"]["hr_count"]["state"], "INCOMPLETE")
        self.assertEqual(len(detail["home_runs"]), 2)

    def test_game_detail_participants_and_safe_provenance(self):
        game = self.game("multi_hr")
        response = self.client.get(f"/api/v1/games/{game.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assert_meta(response)
        self.assertEqual(len(data["home_runs"]), 2)
        self.assertEqual(
            {item["player"]["id"] for item in data["participants"]},
            {str(self.slugger.id)},
        )
        self.assertEqual(data["participants"][0]["roles"], ["BATTER"])
        self.assertIsNone(data["home_runs"][0]["pitcher"])
        self.assertNotIn("storage_key", response.content.decode())
        self.assertNotIn("record_path", response.content.decode())
        self.assertNotIn("provider_access", response.content.decode())
        self.assertEqual(
            {item["domain"] for item in data["coverage"]},
            set(GameDataCoverage.Domain.values),
        )
        zero_pa = self.client.get(
            f"/api/v1/games/{self.fixture.game_ids['zero_pa']}/"
        ).json()
        self.assertIn(
            str(self.fixture.player_ids["runner"]),
            {item["player"]["id"] for item in zero_pa["participants"]},
        )
        runner = next(
            item
            for item in zero_pa["participants"]
            if item["player"]["id"] == str(self.fixture.player_ids["runner"])
        )
        self.assertEqual(
            (runner["pa_count"]["state"], runner["pa_count"]["value"]),
            ("VALUE", 0),
        )
        dnp = self.client.get(f"/api/v1/games/{self.fixture.game_ids['dnp']}/").json()
        self.assertNotIn(
            str(self.fixture.player_ids["runner"]),
            {item["player"]["id"] for item in dnp["participants"]},
        )
        unknown = self.client.get(
            f"/api/v1/games/{self.fixture.game_ids['unknown_participation']}/"
        ).json()
        self.assertNotIn(
            str(self.slugger.id),
            {item["player"]["id"] for item in unknown["participants"]},
        )
        provenance = data["home_runs"][0]["provenance"]
        self.assertEqual(set(provenance), {"source_label", "retrieved_at"})

    def test_game_path_uuid_missing_and_filter_errors(self):
        for path in (
            "/api/v1/games/not-a-uuid/",
            f"/api/v1/games/{fixture_uuid('b11:missing')}/",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")
            self.assert_meta(response)
        self.assertEqual(
            self.client.get("/api/v1/games/?date_from=2099-99-99").status_code, 400
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/games/?date_from=2099-04-04&date_to=2099-04-01"
            ).status_code,
            400,
        )

    def test_today_calendar_validation_games_leaders_and_historical_cutoff(self):
        self.assertEqual(self.client.get("/api/v1/today/").status_code, 400)
        unverified = self.client.get("/api/v1/today/?season=2099&date=2099-04-03")
        self.assertEqual(
            unverified.json()["error"]["code"], "SEASON_CALENDAR_UNVERIFIED"
        )
        self.season.starts_on = date(2099, 4, 1)
        self.season.ends_on = date(2099, 10, 31)
        self.season.full_clean()
        self.season.save()
        nonfinal = Game(
            id=fixture_uuid("b11:today-nonfinal"),
            season=self.season,
            home_team=self.a,
            away_team=self.b,
            venue=self.game("known_zero").venue,
            official_date=date(2099, 4, 20),
            game_type=Game.Type.REGULAR,
            status=Game.Status.SCHEDULED,
            finality=Game.Finality.NOT_FINAL,
        )
        nonfinal.full_clean()
        nonfinal.save()
        outside = self.client.get("/api/v1/today/?season=2099&date=2099-11-01")
        self.assertEqual(outside.json()["error"]["code"], "DATE_OUTSIDE_SEASON")
        self.assertEqual(
            self.client.get("/api/v1/today/?season=2099&date=bad").status_code, 400
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/today/?season=2099&date=2099-04-03&cutoff={self.fixture.game_ids['multi_hr']}"
            ).status_code,
            400,
        )
        historical = self.client.get(
            "/api/v1/today/?season=2099&date=2099-04-02&window=SEASON"
        ).json()
        slugger = next(
            row
            for row in historical["recent_leaders"]
            if row["player"]["id"] == str(self.slugger.id)
        )
        self.assertEqual(slugger["metrics"]["player.hr"]["value"], 0)
        response = self.client.get(
            "/api/v1/today/?season=2099&date=2099-04-03&window=7G"
        )
        self.assertEqual(response.status_code, 200)
        self.assert_meta(response)
        data = response.json()
        self.assertEqual(data["date"], "2099-04-03")
        self.assertIn(
            str(self.fixture.game_ids["multi_hr"]),
            [item["id"] for item in data["games"]],
        )
        self.assertEqual(data["scope"]["cutoff_date"], "2099-04-03")
        self.assertNotIn("weather", data)
        self.assertNotIn("prediction", data)
        for leader in data["recent_leaders"]:
            self.assertLessEqual(leader["metrics"]["player.hr"]["value"] or 0, 2)
        partial = self.client.get("/api/v1/today/?season=2099&date=2099-04-09")
        self.assertEqual(partial.status_code, 200)
        self.assertTrue(partial.json()["games"])
        self.assertIn(
            partial.json()["recent_leaders_availability"]["state"],
            {"UNKNOWN", "INCOMPLETE"},
        )
        scheduled = self.client.get("/api/v1/today/?season=2099&date=2099-04-20").json()
        row = next(
            game for game in scheduled["games"] if game["id"] == str(nonfinal.id)
        )
        self.assertEqual(row["hr_count"]["state"], "UNKNOWN")
