"""Run one isolated B21 benchmark: python -m api.benchmarks.matrix 30G csv.

Creates a temporary canonical SQLite database. Never touches development data.
Setup/migrations are excluded from wall time; source composition is included.
"""

import argparse
import cProfile
import json
import os
import resource
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5


def seed():
    from domain.models import (
        Game,
        GameDataCoverage,
        HomeRunEvent,
        PlateAppearance,
        Player,
        PlayerGameParticipation,
        Season,
        Team,
    )
    from ingestion.models import DatasetRevision

    def id(key):
        return uuid5(NAMESPACE_URL, f"mlb-b21-benchmark:{key}")

    season = Season.objects.create(id=id("season"), year=2098)
    team = Team.objects.create(id=id("team"), display_name="Benchmark Club")
    opponent = Team.objects.create(id=id("opponent"), display_name="Benchmark Opponent")
    instant = datetime(2098, 10, 1, tzinfo=timezone.utc)
    players = [
        Player(id=id(f"player:{i}"), display_name=f"Benchmark Player {i + 1:02}")
        for i in range(60)
    ]
    Player.objects.bulk_create(players)
    games = [
        Game(
            id=id(f"game:{i}"),
            season=season,
            home_team=team,
            away_team=opponent,
            official_date=date(2098, 4, 1) + timedelta(days=i),
            game_type="REGULAR",
            status="COMPLETED",
            finality="FINAL",
            scheduled_game_number=1,
        )
        for i in range(162)
    ]
    Game.objects.bulk_create(games)
    participations, pas, events = [], [], []
    for i, game in enumerate(games):
        for j, player in enumerate(players):
            participations.append(
                PlayerGameParticipation(
                    id=id(f"participation:{i}:{j}"),
                    game=game,
                    player=player,
                    team=team,
                    participation_state="APPEARED",
                    pa_coverage="COMPLETE",
                    reported_pa_count=1,
                )
            )
            hr = (i + j) % 7 == 0
            pa = PlateAppearance(
                id=id(f"pa:{i}:{j}"),
                game=game,
                batter=player,
                batting_team=team,
                fielding_team=opponent,
                game_pa_ordinal=j + 1,
                outcome_category="HOME_RUN" if hr else "NON_HR",
            )
            pas.append(pa)
            if hr:
                events.append(HomeRunEvent(id=id(f"hr:{i}:{j}"), plate_appearance=pa))
    PlayerGameParticipation.objects.bulk_create(participations)
    PlateAppearance.objects.bulk_create(pas)
    HomeRunEvent.objects.bulk_create(events)
    GameDataCoverage.objects.bulk_create(
        [
            GameDataCoverage(
                id=id(f"coverage:{i}:{domain}"),
                game=game,
                domain=domain,
                state="COMPLETE",
                assessed_at_utc=instant,
            )
            for i, game in enumerate(games)
            for domain in GameDataCoverage.Domain.values
        ]
    )
    revision = DatasetRevision.objects.create(committed_at_utc=instant)
    return team, revision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("window", choices=("30G", "60G", "SEASON"))
    parser.add_argument("format", choices=("csv", "pdf"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="mlb-b21-") as directory:
        os.environ["DJANGO_DB_PATH"] = str(Path(directory) / "benchmark.sqlite3")
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django

        django.setup()
        from django.core.management import call_command
        from django.db import transaction

        from analytics.windows import select_team_window
        from api.exports import render_csv, render_pdf
        from api.services import team_recurrence

        call_command("migrate", verbosity=0)
        team, revision = seed()
        profiler = cProfile.Profile() if args.profile else None
        if profiler:
            profiler.enable()
        start = perf_counter()
        with transaction.atomic():
            selection = select_team_window(
                season=2098, team=team, window=args.window, cutoff="LATEST"
            )
            payload = team_recurrence(team, selection)
            composed = perf_counter() - start
            meta = {
                "dataset_revision": str(revision.id),
                "data_as_of": revision.committed_at_utc.isoformat().replace(
                    "+00:00", "Z"
                ),
            }
            renderer = render_csv if args.format == "csv" else render_pdf
            data, count = renderer("team_recurrence", payload, payload["scope"], meta)
        elapsed = perf_counter() - start
        if profiler:
            profiler.disable()
            profiler.dump_stats(args.profile)
        # Darwin ru_maxrss is bytes; Linux reports KiB. Use binary MiB.
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
            1024**2 if sys.platform == "darwin" else 1024
        )
        if args.output:
            args.output.write_bytes(data)
        print(
            json.dumps(
                {
                    "window": args.window,
                    "format": args.format,
                    "composition_s": round(composed, 3),
                    "wall_s": round(elapsed, 3),
                    "peak_rss_mib": round(peak, 2),
                    "data_rows": count if args.format == "csv" else None,
                    "pages": count if args.format == "pdf" else None,
                    "bytes": len(data),
                    "dataset_revision": str(revision.id),
                    "players": len(payload["rows"]),
                    "games": len(payload["columns"]),
                }
            )
        )


if __name__ == "__main__":
    main()
