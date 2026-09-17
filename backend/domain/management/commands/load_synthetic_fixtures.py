from django.core.management.base import BaseCommand

from domain.fixtures import load_synthetic_fixtures


class Command(BaseCommand):
    help = "Load deterministic synthetic B06 canonical fixtures (offline)."

    def handle(self, *args, **options):
        manifest = load_synthetic_fixtures()
        self.stdout.write(
            self.style.SUCCESS(
                "Synthetic fixtures ready: "
                f"season={manifest.season_id} "
                f"games={len(manifest.game_ids)} "
                f"PAs={len(manifest.pa_ids)} "
                f"HRs={len(manifest.hr_event_ids)}"
            )
        )
