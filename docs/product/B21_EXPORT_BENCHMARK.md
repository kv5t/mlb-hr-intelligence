# B21 synchronous export benchmark

Measured 2026-09-30 on macOS 27.0 arm64, Python 3.12.14, SQLite, WeasyPrint 70.0 and Homebrew Pango 1.58.0. All data is deterministic synthetic canonical evidence, not MLB data.

## Method and reproducibility

`backend/api/benchmarks/matrix.py` creates an isolated temporary database per process: 60 players, 162 FINAL REGULAR games, complete participation/PA/HR coverage, one canonical PA per player/game and a linked HR every seventh observation. UUIDs are deterministic. Every case captures revision **"1"**, committed at `2098-10-01T00:00:00Z`.

Run from `backend/`:

```bash
../.venv/bin/python -m api.benchmarks.matrix 30G csv
../.venv/bin/python -m api.benchmarks.matrix 30G pdf
# Repeat with 60G and SEASON. Optional: --output /tmp/report.pdf
```

On the development Mac, prefix commands with `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`; `XDG_CACHE_HOME=/tmp/mlb-b21-cache` provides a writable font cache. Run cases sequentially, each in a fresh process. Migration/fixture setup is excluded from wall time. Selection, shared analytical composition, HTML/CSV generation, PDF render/write and transaction completion are included. Network/file-download time is excluded. Peak memory is whole-process `resource.getrusage(RUSAGE_SELF).ru_maxrss`, including setup and native PDF allocations, normalized from Darwin bytes to **MiB**; Linux KiB is also supported. This is not tracemalloc.

## Results

| Scope | CSV wall / budget (s) | PDF wall / budget (s) | CSV rows | PDF pages | CSV peak MiB | PDF peak MiB | CSV / PDF bytes |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 30G | **11.323 / 5 — miss** | 12.548 / 15 — pass | 1,800 | 7 | 121.72 | 172.73 | 3,061,776 / 75,959 |
| 60G | **11.973 / 8 — miss** | 13.724 / 25 — pass | 3,600 | 13 | 148.14 | 215.78 | 6,121,296 / 135,420 |
| SEASON (162) | 13.587 / 20 — pass | 18.519 / 60 — pass | 9,720 | 34 | 256.52 | 373.70 | 17,295,156 / 338,526 |

CSV row counts exclude the header and equal exactly `60 × selected games`. Every case retains all selected cells. Maximum peak RSS is 373.70 MiB (391.85 decimal MB), below the 500 MB contract limit. Measurements characterize this synthetic workload and development machine; production hardware and denser PA populations require remeasurement.

## Provisional B21/B27 issue: matrix composition exceeds short-window CSV budgets

**Status: open; B21 PASS CONDITIONAL on performance only.** No scope reduction, silent truncation, cache, async job or change to analytical semantics was used.

Composition alone takes 11.235s / 11.793s / 13.086s in the CSV cases; CSV encoding adds approximately 0.09s / 0.18s / 0.50s. A diagnostic `--profile /tmp/b21-profile.prof` run (profiling overhead excluded from results above) attributes 25.13 of its 27.85 composition seconds to 60 existing `compute_player_production_metrics` calls. Shared HR integrity evaluation repeatedly materializes season-wide game PA/event evidence for each player's season HR column; ORM conversion/model construction dominates. PDF rendering is not the principal source of this short-window miss.

B27 should address batched reuse of canonical season evidence in the existing analytical services and remeasure these identical cases before production acceptance. B21 deliberately preserves those services as the single source of truth. The known leaderboard's linear per-player composition cost also remains; exports do not introduce a second formula implementation.

## PDF visual smoke

A3 landscape matrices use 15-game horizontal sections, repeating Player, Season HR, Window HR and game headers, with repeated table headers on vertical pages. All 162 games produce 11 horizontal sections, including the final games 151–162. Representative 30G and Season pages were rendered with installed `pdftoppm` and inspected, including the final Season group. A four-game player recurrence report (2 pages, gap values 1 and 0) and a four-event team HR log (1 page) were also rendered and inspected. Scope/revision/coverage/legend, null pitcher, authoritative HR total and reliable textual state labels were visible without clipping or overlap. Generated PDFs/images remain outside Git.

Normal CI uses small synthetic fixtures and PDF smoke checks; this full workload is an explicit local benchmark, not a CI test.

## Frontend build

Production build after B21: entry 325.68 kB (94.67 kB gzip), shared MetricValue/API chunk 182.59 kB (55.47 kB gzip), runtime 0.58 kB (0.36 kB gzip), CSS 27.25 kB (5.76 kB gzip). Existing lazy analytical screen chunks remain approximately 1.83–16.30 kB. No frontend PDF library or new frontend dependency was added. Vite now extracts a shared chunk; combined entry/shared/runtime JavaScript is 508.85 kB versus the preceding 504.82 kB entry (about +0.8% raw). These files are build outputs, not committed artifacts.
