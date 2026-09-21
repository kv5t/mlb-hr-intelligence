"""B13 local demo preparation stays deterministic, explicit, and offline."""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from domain.fixtures import fixture_uuid, load_synthetic_fixtures
from domain.models import Game, HomeRunEvent, PlateAppearance, Season
from ingestion.models import DatasetRevision, Provider, ProviderAccessDecision


class PrepareSyntheticDemoTests(TestCase):
    def run_command(self):
        output = StringIO()
        with patch("socket.socket.connect", side_effect=AssertionError("network used")):
            call_command("prepare_synthetic_demo", stdout=output)
        return output.getvalue()

    def test_command_prepares_explicit_synthetic_publication(self):
        output = self.run_command()
        season = Season.objects.get(pk=fixture_uuid("season:synthetic"))
        provider = Provider.objects.get(code="SYNTHETIC")

        self.assertEqual(
            (season.starts_on.isoformat(), season.ends_on.isoformat()),
            ("2099-04-01", "2099-04-30"),
        )
        self.assertIn("not real MLB data", output)
        self.assertFalse(provider.enabled)
        self.assertFalse(
            ProviderAccessDecision.objects.filter(provider=provider).exists()
        )
        self.assertEqual(DatasetRevision.objects.count(), 1)

        response = APIClient().get("/api/v1/today/?season=2099&date=2099-04-03")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["games"])

    def test_repeated_command_preserves_canonical_rows_and_publishes_new_revision(self):
        self.run_command()
        before = (
            Game.objects.count(),
            PlateAppearance.objects.count(),
            HomeRunEvent.objects.count(),
        )
        self.run_command()

        self.assertEqual(
            before,
            (
                Game.objects.count(),
                PlateAppearance.objects.count(),
                HomeRunEvent.objects.count(),
            ),
        )
        self.assertEqual(DatasetRevision.objects.count(), 2)

    def test_command_safely_upgrades_an_already_loaded_fixture_calendar(self):
        manifest = load_synthetic_fixtures()
        season = Season.objects.get(pk=manifest.season_id)
        self.assertIsNone(season.starts_on)

        self.run_command()

        season.refresh_from_db()
        self.assertEqual(season.starts_on.isoformat(), "2099-04-01")
        self.assertEqual(season.ends_on.isoformat(), "2099-04-30")
