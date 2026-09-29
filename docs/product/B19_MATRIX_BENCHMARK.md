# B19 Team Recurrence Matrix Benchmark

## Purpose

This benchmark checks the B19 Team Recurrence Matrix at the required upper-bound synthetic shape: 60 player rows by 162 team-game columns. It measures the production frontend bundle and does not call a provider or change canonical data.

## Environment

- Date: 2026-09-29
- Hardware: Apple M1 Max MacBook Pro, 10 CPU cores, 32 GB memory
- Operating system: macOS 27.0, arm64
- Browser: Codex in-app browser, Chromium 154 (`Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36`)
- Viewports: 1440 × 900 desktop and 390 × 844 mobile
- Build: Vite production preview with `VITE_MATRIX_BENCHMARK=1`
- Payload: deterministic 60 × 162 response, 908,416 JSON bytes

The benchmark-only fetch fixture is activated only by the explicit build variable. Normal development and production builds use `/api/v1/`.

## Method

1. Build with `VITE_MATRIX_BENCHMARK=1 npm run build`.
2. Serve `frontend/dist/` with Vite preview.
3. Load the Team Recurrence route five times at the desktop viewport.
4. Measure from deterministic response availability through two animation frames after React commits the matrix.
5. Change the window across `7G`, `15G`, `30G`, `60G`, and `SEASON` and record the same measure.
6. Exercise keyboard navigation from the first game cell to the final game column.
7. Switch to the mobile viewport and verify the player selector and complete game sequence.

## Results

| Measurement | Result |
| --- | ---: |
| Initial render runs | 377.4, 494.6, 469.6, 466.0, 487.2 ms |
| Initial render median | 469.6 ms |
| Initial render worst | 494.6 ms |
| Scope transition runs | 448.4, 436.8, 404.0, 428.6, 95.1 ms |
| Rendered matrix cells | 9,720 |
| Game columns | 162 |
| Player rows | 60 |
| Total DOM elements | 22,140 |
| Observed heap growth | 14.0–31.6 MB |
| Longest observed main-thread task | 309 ms |
| Sampled keyboard/scroll interaction long task | 0 ms (no task over the 50 ms API threshold) |

The browser exposed `performance.memory`, so heap growth is included. Long-task values come from the browser Long Tasks API. The 309 ms task occurred during full matrix rendering; after resetting the interaction sample, keyboard movement to the final column and horizontal scrolling produced no reported long task. These are diagnostic observations rather than CI thresholds.

## Interaction and responsive checks

- Roving keyboard focus reached column 162 using `End`; arrow, Home/End, Enter/Space, and Escape behavior is covered by component tests.
- The full desktop table remains horizontally reachable and keeps player and HR summary columns sticky.
- At 390 × 844, the desktop table is hidden and the mobile view exposes 60 selectable players plus the selected player's complete 162-game sequence.
- Multi-HR cells expose every canonical event as an independent Game Detail anchor.

## Virtualization decision

Virtualization is deferred for 0.1. The measured upper-bound matrix stays below 30,000 DOM elements and completes the five production-build initial renders below 500 ms on the documented machine. The mobile layout renders one player's game sequence at a time, which avoids duplicating all 9,720 data cells in the visible mobile presentation.

The 309 ms long task and approximately 22,000-element DOM remain performance debt. Reconsider row and column virtualization if production rosters exceed this envelope, lower-powered mobile hardware shows input latency, or future matrix content materially increases per-cell DOM cost.
