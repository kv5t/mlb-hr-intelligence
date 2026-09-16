# Ingestion architecture — Phase 0.0-E

**Specification only.** No implementation, scheduler or automated fetch is authorized. [SOURCE_SNAPSHOT_POLICY.md](SOURCE_SNAPSHOT_POLICY.md) defines immutable evidence; [COVERAGE_POLICY.md](COVERAGE_POLICY.md) defines publishability; [DATA_QUALITY_POLICY.md](DATA_QUALITY_POLICY.md) defines quarantine. The prerequisite `PROVIDER_ACCESS_APPROVED` is an externally recorded decision, not something a successful HTTP request or ingestion process can set.

## Deterministic pipeline and failure boundary

```mermaid
flowchart LR
  A[Externally approved provider] --> F[Fetch]
  F --> R[Immutable raw snapshot and retrieval metadata]
  R --> P[Parse and source-record references]
  P --> N[Normalize versioned source claims]
  N --> I[Resolve namespaced identities]
  I --> C[Reconcile old and new claims]
  C --> V[Validate canonical invariants]
  V --> G[Assess domain coverage]
  G --> T[Atomic commit per game]
  T --> D[Dataset revision and publication state]
  D --> X[Invalidate/recompute affected analytics]
```

Fetch failure creates an item error, not a raw success. Raw persistence must finish before parse/canonical mutation. Parse failure keeps raw evidence and opens an issue. Unresolved identity or invariants quarantine the candidate claim; old canonical state survives. Coverage is assessed from the exact snapshot/reconciliation candidate that is committed. Commit and revision/invalidation intent are one DB transaction; a later worker/cache task can execute the intent idempotently. A run is never marked successful when a required stage failed. A snapshot can be retained without publishing anything.

For MLB 0.1, the pipeline starts only after externally approved access. Research-only direct samples in PROVIDER_EVIDENCE are historical evidence, not a deployment configuration.

## Minimum operational records

| Record | Minimum fields / role | Uniqueness and lifecycle |
| --- | --- | --- |
| `ProviderAccessDecision` | provider, state `RESEARCH_ONLY/APPROVED_FOR_AUTOMATED_USE/BLOCKED/UNKNOWN`, externally supplied decision reference, scope of allowed operations, recorded time, expiry/review time | Approval cannot be self-declared by fetch code; default `UNKNOWN` and deny automation. `PROVIDER_ACCESS_APPROVED` means active externally recorded approval covers that operation. |
| `DataSyncRun` | provider, job kind, parameter fingerprint, code/config version, start/end, status, counts, error summary, access-decision reference | One run per invocation; status `PENDING/RUNNING/SUCCEEDED/PARTIAL/FAILED/BLOCKED`. |
| `DataSyncItem` | run, target kind/key, stage/checkpoint, attempt count, last error, snapshot ID, canonical revision, timestamps | Unique `(run,target)`; recover after interruption; identical target across runs is allowed under target lease. |
| `RawSourceSnapshot` | provider/resource/target, normalized request fingerprint, retrieved time, HTTP status/content type, SHA-256 digest, immutable payload pointer, optional provider timestamp, parse status | Metadata per retrieval; identical bytes share a content-addressed blob but distinct retrieval observations remain. No secret-bearing URL/header retained. |
| `SourceRecordReference` | snapshot, provider record path/key, retrieval time, optional provider-reported timestamp | Distinct source claim pointer, with stable key only where verified; aligns with DATA_MODEL. |
| `FactSourceLink` | source reference, typed canonical target/claim, relation `SUPPORTS/CONFLICTS/WITHDRAWN/UNRESOLVED` | Many-to-many claim ledger; never delete conflict evidence. |
| `DataQualityIssue` | stable code, severity, provider/target/domain, first/last seen, evidence refs, blocking scope, resolution | Fingerprint deduplicates recurring issue; resolution is auditable. |
| `QuarantineRecord` | candidate claim/source ref, reason, affected target/domain, first/last seen, review state | No canonical publication for quarantined claim. Can be reprocessed after mapping/config correction. |
| `CoverageAssessmentHistory` | game/domain and optional player/team scope, state, reason set, snapshot/revision, assessed time | Append immutable assessments; `GameDataCoverage` is current projection. |
| `DatasetRevision` | monotonic revision number, committed time, sync item/run, changed game/domain IDs, invalidation set | One successful canonical publication transaction advances revision. No revision for fetch-only/deduplicated no-op. |

Avoid separate tables for every error class. Issues, quarantine and source links represent exceptions without making raw JSON the query layer. Game lifecycle observations remain domain records sourced from successive snapshots.

## Idempotency and identity

| Canonical object | Stable upsert key | Collision policy |
| --- | --- | --- |
| Season | MLB season namespace + year | Different claimed year for same source ID quarantined. |
| Team, Player, Venue | verified namespaced MLB ID | Name/metadata change updates sourced attributes and preserves internal UUID/history. Duplicate key-to-two-UUID quarantined. |
| Game | MLB namespace + `gamePk` | Date, score, status and venue changes are revisions of the same contest, not a new game. Two incompatible teams for same `gamePk` quarantine pending correction review. |
| PlayerGameParticipation | canonical `(game,player,team)` | Both teams allowed in one resumed contest; state changes require source-backed reconciliation. |
| PlateAppearance | `(game, source namespace, about.atBatIndex)` source identity, only after confirmed PA classification | Raw index can point to a non-PA play. Canonical UUID stable across replays; `game_pa_ordinal` is dense **among verified PAs**, not necessarily equal to raw index. Duplicate raw index with conflicting play evidence quarantined. |
| HomeRunEvent | unique canonical PA | Event removal/change follows correction policy; never create HR without reconciled PA. |
| ExternalIdentifier | `(provider,entity_kind,external_value)` active mapping | Internal UUID remains canonical PK; aliases cannot identify two active canonical entities. |

Every normalized candidate is compared with the prior claim set. Same snapshot, same parser/config version and same canonical fingerprint is a no-op. A parser version change may intentionally reprocess identical bytes; it creates a new revision only if accepted canonical facts or coverage change. Deterministic conflict ordering uses source authority and recorded observations, never import iteration order.

## Atomic game transaction and SQLite policy

The raw blob/metadata is durable before game transaction. Inside a short single-writer transaction: acquire target lease; re-read current revision; upsert identities; append changed lifecycle/source claims; reconcile and validate all candidate PAs, HRs, participation and affected coverage; atomically switch current canonical projection/coverage; append revision and invalidation intent; commit. If validation fails, roll back canonical changes and revision while leaving raw snapshot and issue/quarantine metadata durable in a separate bounded transaction. Never make a partially replaced game visible as COMPLETE.

SQLite WAL permits readers with one writer. One ingestion writer, bounded transactions per game/small metadata batch, no concurrent season backfills, and a database-backed lease plus single scheduler invariant are sufficient for MVP. Lease key is `(provider,resource kind,external target)`; include owner/run, expiry and renewal. Stale lease can be reclaimed only after expiry plus verification that no live owner is active; reclaim is logged. Unique keys and optimistic revision check remain the correctness defense if a lease fails. PostgreSQL later can preserve the same transaction semantics; introduce Celery/Redis only after measured throughput, latency or availability requires parallel workers.

## Analytics revision and invalidation

`data_as_of` is the committed `DatasetRevision` and timestamp, never the provider game time. Web/CSV/PDF must pin one revision for an entire response/export. A request reading multiple queries uses a consistent read snapshot or the same revision-filtered projection; if revision changes midway, retry or return a clear stale result rather than mix revisions. A no-op fetch does not increment revision. The revision history keeps changed target and source references so results can be explained without full database snapshots.

Any change to HR, PA, finality, official date, order, team attribution or coverage invalidates the game, its teams, involved players, season leaderboards, affected rolling windows and current cutoff-state drought/streaks through later cutoffs in that season/filter scope. For MVP, prefer on-demand recalculation with revision-keyed cache invalidation; do not attempt fine-grained incremental arithmetic before measured need. Invalidations are durable intents in the commit and retried idempotently. An unresolved issue can change a prior numeric KPI to `UNKNOWN/INCOMPLETE`; never preserve a stale known zero.

## 0.0-E quality gate — specification audit

`PASS` evaluates whether the architecture documents the rule. It does not assert that integration code, provider rights approval, or broad coverage validation exists. G06 remains OPEN_ENGINEERING and G12 OPEN_EXTERNAL before deployment.

| # | Criterion | Result | Evidence |
| --- | --- | --- | --- |
| 1 | 0.0-D field-mapping metadata errors are corrected. | PASS | PROVIDER_FIELD_MAPPING |
| 2 | canonical requiredness matches DATA_MODEL. | PASS | PROVIDER_FIELD_MAPPING |
| 3 | non-game entities no longer incorrectly use gamePk as external ID. | PASS | PROVIDER_FIELD_MAPPING |
| 4 | internal timestamps are correctly distinguished from provider times. | PASS | PROVIDER_FIELD_MAPPING / SOURCE_SNAPSHOT_POLICY |
| 5 | game evidence cannot fabricate temporal affiliation intervals. | PASS | DATA_MODEL / DATA_INVARIANTS |
| 6 | G03/G05 distinguish degraded matrix fidelity from core analytics. | PASS | PROVIDER_GAPS |
| 7 | G06 remains a correctness gate until coverage validation succeeds. | PASS | COVERAGE_POLICY / PROVIDER_GAPS |
| 8 | G12 remains an external access gate. | PASS | INGESTION_ARCHITECTURE / PROVIDER_GAPS |
| 9 | Open-Meteo historical/commercial limitation is corrected. | PASS | PROVIDER_EVIDENCE E19 |
| 10 | Roadmap and glossary status are updated. | PASS | ROADMAP / GLOSSARY |
| 11 | game status/finality mapping is conservative. | PASS | COVERAGE_POLICY |
| 12 | abstractGameState alone never establishes FINAL. | PASS | COVERAGE_POLICY |
| 13 | ingestion pipeline stages are explicit. | PASS | INGESTION_ARCHITECTURE |
| 14 | raw snapshot is preserved before canonical mutation. | PASS | SOURCE_SNAPSHOT_POLICY |
| 15 | source snapshots are immutable and checksum-addressable or equivalently auditable. | PASS | SOURCE_SNAPSHOT_POLICY |
| 16 | canonical upserts are idempotent. | PASS | INGESTION_ARCHITECTURE |
| 17 | Game uses gamePk lookup without making it canonical PK. | PASS | INGESTION_ARCHITECTURE |
| 18 | participation uniqueness is `(game, player, team)`. | PASS | INGESTION_ARCHITECTURE |
| 19 | PA reconciliation has deterministic rules. | PASS | COVERAGE_POLICY |
| 20 | the 76/75 discrepancy is explained or remains an explicit blocking coverage fixture. | PASS | PROVIDER_EVIDENCE E18 / COVERAGE_POLICY |
| 21 | HR coverage cannot become COMPLETE if PA/HR reconciliation is unresolved. | PASS | COVERAGE_POLICY |
| 22 | verified zero HR requires explicit completeness evidence. | PASS | COVERAGE_POLICY |
| 23 | APPEARED requires positive evidence. | PASS | COVERAGE_POLICY |
| 24 | DNP requires affirmative evidence. | PASS | COVERAGE_POLICY |
| 25 | zero-PA appearance requires positive participation plus complete PA evidence. | PASS | COVERAGE_POLICY |
| 26 | NOT_WITH_TEAM requires verified affiliation/non-affiliation evidence. | PASS | DATA_MODEL / DATA_QUALITY_POLICY |
| 27 | incomplete data is never silently replaced by older complete data. | PASS | BACKFILL_SYNC_POLICY |
| 28 | retry classes are explicit. | PASS | BACKFILL_SYNC_POLICY |
| 29 | unknown rate limits produce conservative configurable behavior. | PASS | BACKFILL_SYNC_POLICY |
| 30 | SQLite writer concurrency is explicitly controlled. | PASS | INGESTION_ARCHITECTURE |
| 31 | overlapping backfills/syncs are prevented. | PASS | BACKFILL_SYNC_POLICY |
| 32 | correction/tombstone policy retains history. | PASS | SOURCE_SNAPSHOT_POLICY |
| 33 | quarantine is defined. | PASS | DATA_QUALITY_POLICY |
| 34 | schema drift is observable. | PASS | DATA_QUALITY_POLICY |
| 35 | data-quality severity and publication impact are explicit. | PASS | DATA_QUALITY_POLICY |
| 36 | analytics-ready is distinct from game finality. | PASS | COVERAGE_POLICY |
| 37 | data_as_of/dataset revision has a reproducible definition. | PASS | INGESTION_ARCHITECTURE |
| 38 | analytics invalidation/recomputation scope is defined. | PASS | INGESTION_ARCHITECTURE |
| 39 | management command contracts are specified. | PASS | BACKFILL_SYNC_POLICY |
| 40 | sync observability is specified. | PASS | DATA_QUALITY_POLICY |
| 41 | provider access approval is external and cannot be self-declared by ingestion code. | PASS | INGESTION_ARCHITECTURE |
| 42 | all required scenarios have expected outcomes. | PASS | INGESTION_TEST_CASES |
| 43 | no Django/application/provider integration code was implemented. | PASS | repository diff |

**Phase 0.0-E specification result: PASS. Production/backfill deployment: BLOCKED** until the external access decision is recorded and the G06 completeness rules pass real implementation validation. Phase 0.0-F may define API contracts without treating those gates as resolved.
