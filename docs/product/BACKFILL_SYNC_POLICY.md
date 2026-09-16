# Backfill, incremental sync and orchestration — Phase 0.0-E

**Design only.** No command or job is implemented or scheduled. Every automated provider request requires `PROVIDER_ACCESS_APPROVED` for its operation, scope and date, externally recorded as defined in [INGESTION_ARCHITECTURE.md](INGESTION_ARCHITECTURE.md). `RESEARCH_ONLY`, `UNKNOWN`, expired approval or `BLOCKED` stop before fetch. Provider limits and SLA for MLB public endpoints remain unknown; no numeric quota is invented.

## Orchestration and backfill

MVP orchestration is Django management commands called by a single external scheduler, with one controlled SQLite writer and DB-backed target leases. Celery/Redis are deferred until measured throughput, parallelism, latency or recovery needs justify them. `backfill_season --season YYYY` is a resumable orchestration contract, not a single DB transaction:

1. Check access decision, provider disable switch, requested season and job lease; record run/config version.
2. Sync season metadata and team IDs/names as source observations.
3. Discover schedule in bounded date chunks under approved policy. Persist each raw response and checkpoint chunk; filter regular-season analytics later, without discarding other game types from identity/navigation.
4. Discover players from game/roster evidence as encountered; no full player catalog preload required.
5. Fetch eligible final game snapshots one target at a time, conditioned on approved access; preserve schedule status and lifecycle observations even before final game details.
6. Parse/normalize; resolve IDs; classify PA/NON_PA/UNRESOLVED; build HR and participation claims; compare boxscore; assess coverage.
7. Commit accepted game revisions atomically and enqueue revision-keyed invalidation. Record blocked/partial items without aborting entire season.
8. Revisit conflicts/corrections; report analytics readiness by domain and unresolved issues.

Checkpoint is `(run,stage,chunk/target)` with snapshot/revision ID. On restart, use the same run config or explicitly begin a new run; skip identical accepted target fingerprint, reprocess a changed snapshot or parser version, and never skip a known failed item as success. A half-finished season is `PARTIAL`, not complete. Limit date chunk size/configurable request spacing; do not launch concurrent backfills. Initial backfill does not imply rights/access approval merely because an operator invoked a command.

## Incremental schedule, lifecycle and cadence

Separate schedules for metadata, schedule discovery/refresh, pregame, in-progress, post-final reconciliation, and correction revisit. Since 0.1 has no second-by-second live requirement and provider limits/support are unknown, the **default is disabled** until approved; when approved, start with low concurrency (one active request and one writer) and configurable conservative intervals, adjusted only from documented access terms and observed load. In-progress refresh is optional and must not hold a game COMPLETE. A late correction revisit remains necessary even after a final game.

On every changed schedule/game snapshot, compare normalized status, scheduled time, official date, venue, teams, score and resume metadata. Append `GameLifecycleEvent` only for a meaningful change; `recorded_at_utc` is our snapshot processing time; `effective_at_utc` is populated only from an explicit source timestamp. Preserve prior scheduled starts and source references. Same `gamePk` after postponement or suspension stays one contest, subject to identity validation. Unknown provider status stays `UNKNOWN`, not FINAL. An official-date correction reorders affected windows and invalidates later cutoff metrics.

## Retry, access and rate safety

| Failure | Retry policy | Canonical effect |
| --- | --- | --- |
| Timeout/network error, temporary 5xx | Bounded attempts with exponential backoff and jitter, then failed item; resume later. | Prior state preserved; no false coverage upgrade. |
| 429 | Honor `Retry-After` when present; otherwise bounded conservative backoff; reduce concurrency and expose rate-limit metric. | No retry storm; provider disable switch can stop all requests. |
| Explicit inaccessible/unavailable resource | Stop or mark `UNAVAILABLE` only under a documented condition; recheck access basis. | Do not convert to empty data. |
| Parse error/schema drift | Preserve raw snapshot; visible issue and quarantine affected claims; no blind retry of same bytes/parser. | No canonical publication from malformed response. |
| Invariant failure/identity ambiguity/PA conflict | Quarantine candidate, await correction or operator resolution; repeated identical bytes are no-op issue updates. | Prior published state remains; affected coverage downgraded when new evidence undermines it. |
| Access decision absent/expired/blocked | No provider request; `BLOCKED` run/item with `ACCESS_NOT_APPROVED`. | No canonical change. |

Per-provider configuration includes enable/disable, approved operations, maximum concurrency, minimum request spacing, timeout, retry budget, backoff ceiling and retention limits. Log aggregate request/429/latency metrics, never credentials. A missing published rate limit means `UNKNOWN LIMIT` and continued conservative controls.

## Locks and conceptual command contracts

All commands are **specifications**, not CLI implementations. Exit classes: `0=all requested targets reconciled or idempotent no-op`, `2=partial/quality-blocked`, `3=access-blocked`, `4=invalid input/config`; transient fetch failure after bounded retries is partial/failed, never exit 0. `--dry-run` may parse existing snapshots and report proposed mutations without modifying canonical facts; it does not grant permission to fetch. Run and item logs record status. Target lease is `(provider,resource,target)`; season backfill also holds a season-wide lease. Two jobs for one game cannot commit concurrently; stale recovery and optimistic revision checks follow INGESTION_ARCHITECTURE.

| Contract | Purpose and inputs | Idempotency, effects, lock, resume |
| --- | --- | --- |
| `sync_seasons` | Refresh allowed season metadata. | Upsert by year; metadata-batch lease; unchanged no revision; resume per season; dry-run supported. |
| `sync_teams` | Refresh verified MLB team IDs/metadata. | Upsert by MLB ID; metadata-batch lease; preserve rename evidence; resume per team; dry-run. |
| `sync_schedule --season YYYY` | Discover/refresh bounded schedule chunks. | Game by gamePk; season/chunk lease; append meaningful lifecycle changes; resume chunk; dry-run. |
| `sync_games --date YYYY-MM-DD` | Refresh known games for one date. | Calls schedule then per-game only as access permits; date lease plus game leases; resume per game; dry-run. |
| `sync_game --game-pk X` | Fetch one game snapshot and propose normalized facts. | Game lease/transaction; identical snapshot no-op; resume from saved snapshot; dry-run. |
| `backfill_season --season YYYY` | Orchestrate staged bounded season processing. | Season lease, checkpoints, per-game atomic commits; resume failed items; dry-run plan from existing evidence only. |
| `reconcile_game --game-pk X` | Recompare retained source claims/canonical facts. | Game lease; deterministic versioned rules; revision only on accepted change; dry-run. |
| `assess_coverage --game-pk X` | Reassess four coverage domains from retained evidence. | Game lease; assessment history; revision if current state changes; dry-run. |
| `reprocess_snapshot --snapshot X` | Replay immutable bytes under chosen parser/config version. | No network; target lease; preserve prior evidence, publish only validated change; dry-run. |

No manual command may bypass the access gate for a fresh provider fetch. Reprocessing already retained snapshots still respects the recorded allowed-use scope for storage/derivatives; if that scope is revoked, publication remains blocked pending external review.
