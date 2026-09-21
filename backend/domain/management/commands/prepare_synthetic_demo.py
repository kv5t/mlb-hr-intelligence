"""Prepare an explicit, offline publication for local UI demonstration."""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from domain.fixtures import fixture_uuid, load_synthetic_fixtures
from domain.models import Season
from ingestion.models import DatasetRevision, Provider, ProviderAccessDecision


class Command(BaseCommand):
    help = "Load and publish the deterministic synthetic UI demo (offline)."

    @transaction.atomic
    def handle(self, *args, **options):
        starts_on = date(2099, 4, 1)
        ends_on = date(2099, 4, 30)
        synthetic_season_id = fixture_uuid("season:synthetic")
        existing = Season.objects.filter(pk=synthetic_season_id).first()
        if existing is not None:
            if (
                existing.year != 2099
                or existing.label != "SYNTHETIC FIXTURE SEASON"
                or existing.starts_on not in (None, starts_on)
                or existing.ends_on not in (None, ends_on)
            ):
                raise CommandError(
                    "Refusing to modify a season that does not match the "
                    "synthetic fixture identity."
                )
            if existing.starts_on is None or existing.ends_on is None:
                existing.starts_on = existing.starts_on or starts_on
                existing.ends_on = existing.ends_on or ends_on
                existing.full_clean()
                existing.save(update_fields=["starts_on", "ends_on"])
        manifest = load_synthetic_fixtures(
            starts_on=starts_on,
            ends_on=ends_on,
        )
        season = Season.objects.get(pk=manifest.season_id)
        provider = Provider.objects.get(code="SYNTHETIC")
        if (
            season.id != synthetic_season_id
            or season.year != 2099
            or season.label != "SYNTHETIC FIXTURE SEASON"
            or provider.enabled
        ):
            raise CommandError(
                "Refusing to publish data that is not the synthetic fixture pack."
            )
        if ProviderAccessDecision.objects.filter(provider=provider).exists():
            raise CommandError(
                "Synthetic demo must not create provider access decisions."
            )

        revision = DatasetRevision(
            changed_game_ids=sorted(
                str(game_id) for game_id in manifest.game_ids.values()
            ),
            invalidation_scopes=["SYNTHETIC_DEMO"],
        )
        revision.save()
        self.stdout.write(
            self.style.SUCCESS(
                "Synthetic demo ready (not real MLB data): "
                f"season=2099 games={len(manifest.game_ids)} "
                f"dataset_revision={revision.id}"
            )
        )
