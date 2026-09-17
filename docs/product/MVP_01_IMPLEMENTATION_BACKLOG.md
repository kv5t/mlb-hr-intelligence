# MLB HR Intelligence — MVP 0.1 implementation backlog (0.0-H)

**Status:** 0.0 specification complete. This is the ordered work plan for **0.1 — HR Recurrence implementation**, not implementation authorization for live provider access. [ROADMAP.md](ROADMAP.md), [API_CONTRACT.md](API_CONTRACT.md), and [FRONTEND_ARCHITECTURE.md](FRONTEND_ARCHITECTURE.md) remain the contracts; this document assigns build order and checks without redefining them.

## 1. Implementation principles and critical path

Build with deterministic **synthetic canonical fixtures → domain/database → analytics → API → frontend vertical slices → exports → ingestion integration**. Work B01–B21 requires no automated MLB HTTP. Live fetch, backfill, or operational sync remain deny-by-default until an externally recorded G12 `PROVIDER_ACCESS_APPROVED` decision covers the operation; G06 PA/HR completeness is a separate hard analytics launch gate. G03/G05 can yield honest UNKNOWN matrix cells without inventing DNP or NOT_WITH_TEAM. No CI test makes a live provider request. Public 0.1 API is GET-only; internal ingestion commands are not public routes. Do not introduce Matchup, Explore, Statcast, weather, prediction, Redis/Celery, or an asynchronous export system.

The critical path is **B01 → B03–B06 → B07–B10 → B11 → B13**, followed by parallelizable screen slices B14–B20, exports B21, and fixture-driven ingestion B22–B25. G12 external approval enables B26; B26 establishes G06 against approved real samples. B27 reviews the integrated 0.1 release. Unapproved access does not stall the synthetic application build, but it prevents live-provider automation and production claims.

**Dependency key:** `Bxx` below is a direct predecessor, not a new phase. Each item is intended for one focused Codex run; a narrow item may be paired only with a tightly coupled neighbor. “Read” names the task's relevant specification files; follow linked sections only to resolve a concrete contradiction. “Checks” are required before the item is accepted.

## 2. Ordered backlog

### B01 — Backend foundation and deterministic CI
- **Goal:** Start the deployable server/test base. **Depends:** none. **Read:** ROADMAP, API_CONTRACT, INGESTION_ARCHITECTURE.
- **Build:** Django 5.2, DRF, django-filter, SQLite WAL startup policy, Ruff, Django test framework, migration check, and GitHub CI for offline backend tests/lint. **Exclude:** domain models, provider HTTP, Celery/Redis.
- **Accept:** server starts; WAL is verifiable; CI passes from a clean checkout with no secrets or network-dependent tests. **Checks:** startup, WAL pragma, lint/test/migration dry run. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B02 — Frontend toolchain and CI
- **Goal:** Start the typed client base. **Depends:** none. **Read:** FRONTEND_ARCHITECTURE, API_CONTRACT.
- **Build:** React/TypeScript/Vite, Tailwind, shadcn/ui, React Router, TanStack Query/Table, ECharts, Zod, TypeScript typecheck, ESLint, Vitest/React Testing Library, and offline CI jobs; add TanStack Virtual only when B19 measurement calls for it. **Exclude:** screens, API client behavior, extra state/chart/table libraries.
- **Accept:** production build, typecheck, lint and one local component smoke test pass in CI. **Checks:** clean install/build and deterministic CI; no live provider HTTP. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B03 — Canonical identity and temporal models
- **Goal:** Persist stable identities and associations. **Depends:** B01. **Read:** DATA_MODEL, DATA_INVARIANTS.
- **Build:** migrations/models for Season, Team, Player, Venue and PlayerTeamAffiliation; UUID keys, nullable sourced metadata, verified external-ID lookup fields, interval validation and indexes. **Exclude:** inferred current-team FK or fabricated affiliation intervals.
- **Accept:** trade/return history retains one Player UUID; unknown bounds remain unknown. **Checks:** migration and I/R invariant tests, duplicate-ID and invalid-interval tests. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B04 — Game, participation and event models
- **Goal:** Persist canonical contest observations. **Depends:** B03. **Read:** DATA_MODEL, DATA_INVARIANTS, COVERAGE_POLICY.
- **Build:** migrations/models for Game, GameLifecycleEvent, PlayerGameParticipation, PlateAppearance, HomeRunEvent and current GameDataCoverage; uniqueness, team/PA/HR validation and core indexes. **Exclude:** totals stored on identity rows or a `(game,player)` participation uniqueness rule.
- **Accept:** doubleheader IDs differ; one player can represent both teams in one contest; HR is 1:1 with an HR PA; finality does not imply coverage. **Checks:** migration, constraint and I/R/G/P/H/M invariant tests. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B05 — Provenance, operational records and safe Admin
- **Goal:** Make source claims and sync state inspectable. **Depends:** B03–B04. **Read:** DATA_MODEL, INGESTION_ARCHITECTURE, DATA_INVARIANTS.
- **Build:** migrations for Provider, ExternalIdentifier, SourceRecordReference, FactSourceLink, ProviderAccessDecision, DataSyncRun/Item, RawSourceSnapshot metadata, DataQualityIssue, QuarantineRecord, CoverageAssessmentHistory, DatasetRevision and lease/invalidation records as needed; Django Admin inspection with provider facts read-only or guarded. **Exclude:** automated fetch, public operational API, casual provider-fact overwrites.
- **Accept:** typed links/aliases validate; default access is deny; Admin inspection cannot silently edit imported facts. **Checks:** migration, uniqueness, permission and safe-admin tests. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B06 — Deterministic canonical fixture pack
- **Goal:** Unblock development without a real MLB dataset. **Depends:** B03–B05. **Read:** DATA_MODEL, DATA_INVARIANTS, KPI_SPEC, WINDOW_SEMANTICS, COVERAGE_POLICY, KPI_TEST_CASES, INGESTION_TEST_CASES.
- **Build:** compact generated fixtures with stable IDs for multi-HR, DNP, zero PA, unknown/partial coverage, trade, doubleheader, suspended/resumed contest, same player on both teams and uncertain same-day order; include synthetic source references. **Exclude:** copied full provider dataset or a claim that fixtures prove G06.
- **Accept:** repeated load yields identical canonical state and no fabricated known zero. **Checks:** fixture idempotency, invariant assertions and scenario smoke tests. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B07 — Window and cutoff selector
- **Goal:** Resolve exact eligible sequences before KPI calculation. **Depends:** B04, B06. **Read:** WINDOW_SEMANTICS, DATA_INVARIANTS, API_CONTRACT.
- **Build:** inclusive official-date cutoff/LATEST, regular/final eligibility, pre-window team/home-away filters, team games, player batting games, shared matrix team-game windows and order-uncertain selection states. **Exclude:** filtering incomplete games out to fill N or treating a player 30G as matrix 30G.
- **Accept:** selection returns actual count only when definitive; suspended game retains official-date position; same-day tie at N boundary is ORDER_UNVERIFIED. **Checks:** executable window fixtures and boundary/dual-team tests. **Reasoning:** HIGH. **Provider/access gate:** NO.

### B08 — Coverage gate and MetricValue core
- **Goal:** Preserve known, partial and unavailable evidence across analytics. **Depends:** B06–B07. **Read:** COVERAGE_POLICY, WINDOW_SEMANTICS, KPI_SPEC, DATA_INVARIANTS.
- **Build:** domain coverage evaluation, reason precedence, MetricValue states, verified-zero proof and participation-to-matrix evidence rules. **Exclude:** deriving DNP from an absent row or NOT_WITH_TEAM from one appearance.
- **Accept:** final/empty HR feed is nonnumeric without COMPLETE; partial stays INCOMPLETE; affirmative DNP/zero-PA states remain distinct. **Checks:** coverage fixtures including downgrade after conflicting correction and all seven matrix states. **Reasoning:** HIGH. **Provider/access gate:** NO.

### B09 — Production and frequency KPIs
- **Goal:** Compute server-side counts/rates with denominators. **Depends:** B07–B08. **Read:** KPI_SPEC, WINDOW_SEMANTICS, KPI_TEST_CASES.
- **Build:** player/team HR, PA, HR/PA, PA/HR, HR/Game, HR Games, Games With HR %, multi-HR games using canonical observations and MetricValue. **Exclude:** any frontend formula or qualification score.
- **Accept:** multi-HR contributes two HR but one HR game; zero denominators and no-game scopes retain specified semantic reasons. **Checks:** translate corresponding KPI_TEST_CASES to executable tests plus coverage precedence cases. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B10 — Gap, drought and streak KPIs
- **Goal:** Compute recurrence and cutoff-state measures. **Depends:** B07–B09. **Read:** KPI_SPEC, WINDOW_SEMANTICS, KPI_TEST_CASES.
- **Build:** ordered gaps, mean/median, current/maximum game and PA droughts, current/maximum streaks; current measures scan decisive suffix before displayed N. **Exclude:** clamping current values to N or connecting across unknown barriers.
- **Accept:** DNP/zero-PA do not advance batting-game runs; current drought can exceed N; unresolved order yields ORDER_UNVERIFIED where material. **Checks:** executable KPI_TEST_CASES for all recurrence IDs and cutoff/coverage barriers. **Reasoning:** HIGH. **Provider/access gate:** NO.

### B11 — API envelope, discovery, games and Today
- **Goal:** Deliver the first read-only service slice. **Depends:** B05, B08–B10. **Read:** API_CONTRACT, COVERAGE_POLICY, WINDOW_SEMANTICS.
- **Build:** `/api/v1/` metadata/error/filter/pagination infrastructure; seasons, teams and players discovery; games list/detail and Today; positive participants only; required GameSummary HR MetricValue; date/season validation. **Exclude:** writes, raw paths, analytics on `/players/` discovery.
- **Accept:** exact 200 semantic null/400/404/503 behavior and one response revision; Today rejects mismatched season/date. **Checks:** contract tests for these six endpoint families, safe provenance and GET-only methods. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B12 — Frontend API boundary and shell
- **Goal:** Establish shared route and state behavior for slices. **Depends:** B02, B11. **Read:** FRONTEND_ARCHITECTURE, API_CONTRACT.
- **Build:** React Router shell, mobile/tablet/desktop nav, URL parameter normalization, Zod DTO boundary, TanStack Query keys/hooks, MetricValue presenter and loading/refresh/empty/error/partial states. **Exclude:** global state store, client KPIs, historical `dataset_revision` parameter.
- **Accept:** invalid payload fails visibly; VALUE=0 differs from UNKNOWN; changing filters changes keys and browser history. **Checks:** Vitest/RTL for DTO rejection, query-key scope, URL restore, semantic labels and keyboard shell. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B13 — Today and Games vertical slice
- **Goal:** Show the first usable 0.1 flow. **Depends:** B11–B12. **Read:** FRONTEND_ARCHITECTURE, API_CONTRACT, SCREEN_MAP.
- **Build:** `/today`, `/games`, `/games/:gameId`; date/status/team filters, game HR count, evidenced participants, HR event list and `#hr-<canonical-event-uuid>` focus with return path. **Exclude:** dedicated HR-event route or current-team inference.
- **Accept:** schedule is visible with incomplete HR data; fragment focuses a matching event without an API filter, and unknown event focus has a graceful fallback. **Checks:** RTL flows, narrow viewport, keyboard/focus and semantic 200 tests. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B14 — Player and leaderboard API family
- **Goal:** Serve comparative and detail analytics. **Depends:** B10–B11. **Read:** API_CONTRACT, KPI_SPEC, WINDOW_SEMANTICS.
- **Build:** `/leaderboards/players/`, `/players/{id}/`, `/players/{id}/home-runs/`; filters, ordering, denominators, row scopes, coverage and paginated verified HR events. **Exclude:** analytical league/division filtering, single best-hitter score or player-current-team claim.
- **Accept:** team filter precedes last N; incomplete rows return 200; HR-log record count is not a complete HR total. **Checks:** contract tests for all three paths, pagination/order and multi-team cases. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B15 — League and Players vertical slice
- **Goal:** Deliver discovery and comparison UI. **Depends:** B12, B14. **Read:** FRONTEND_ARCHITECTURE, API_CONTRACT, SCREEN_MAP.
- **Build:** `/league` and `/players` with TanStack Table, URL-driven search/team/window/sort/page, independent discovery/comparison sections, mobile access to all columns. **Exclude:** current-team fabrication, league/division analytic filters or client KPI sorting/calculation.
- **Accept:** Player 30G is labeled batting games; partial rows show denominators/reasons; mixed revisions are not merged into one asserted figure. **Checks:** RTL filter/history/table tests and responsive/keyboard checks. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B16 — Team detail and HR-log API family
- **Goal:** Support Team Detail's server data. **Depends:** B10–B11. **Read:** API_CONTRACT, KPI_SPEC, WINDOW_SEMANTICS.
- **Build:** `/teams/{id}/` and `/teams/{id}/home-runs/`; scoped metrics, coverage, verified events, semantic total and pagination; reuse existing players/games discovery queries for tabs. **Exclude:** new roster or team-games endpoint.
- **Accept:** team filters/cutoff match contract; incomplete total remains nonnumeric despite verified event rows. **Checks:** contract tests for both paths and Team Detail query composition. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B17 — Teams and Team Detail vertical slice
- **Goal:** Deliver team browsing and tabbed detail. **Depends:** B12, B14, B16. **Read:** FRONTEND_ARCHITECTURE, API_CONTRACT, SCREEN_MAP.
- **Build:** `/teams`, `/teams/:teamId` Overview, Players, Games, HR Log tabs. Players uses `/players/?season&team`; comparative KPI columns additionally use leaderboard with that scope; Games uses `/games/?season&team`; HR Log uses team endpoint. **Exclude:** complete historical roster claim or a new endpoint.
- **Accept:** each tab loads independently; source-supported known association is labeled honestly; trade attribution persists. **Checks:** tab/query composition, partial panel, URL and mobile tests. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B18 — Recurrence API contracts
- **Goal:** Serve team matrix and player observation sequences. **Depends:** B10–B11. **Read:** API_CONTRACT, WINDOW_SEMANTICS, KPI_SPEC, COVERAGE_POLICY.
- **Build:** `/teams/{id}/recurrence/` shared columns/rows/cells and `/players/{id}/recurrence/` observations/gaps; scope, coverage, revision and unresolved-selection behavior. **Exclude:** frontend reconstruction of cells or fake selected columns when membership is unknown.
- **Accept:** every row aligns to columns; positive cell lists canonical event IDs; player current drought may exceed displayed N. **Checks:** contract/fixture tests for all cell states, doubleheader, trade and same-day ordering. **Reasoning:** HIGH. **Provider/access gate:** NO.

### B19 — Team recurrence matrix UI
- **Goal:** Make the hardest view usable and accessible. **Depends:** B12, B17–B18. **Read:** FRONTEND_ARCHITECTURE, API_CONTRACT, WINDOW_SEMANTICS.
- **Build:** `/teams/:teamId/recurrence`, sticky identity/summary, shared game columns, exhaustive state renderer, horizontal/keyboard access, screen-reader labels, mobile linear alternative and Game Detail/event focus. Measure Season before adding column-only TanStack Virtual. **Exclude:** row virtualization by default or new HR-event route.
- **Accept:** all 60×162 benchmark rows/columns remain reachable; UNKNOWN/DNP/NOT_WITH_TEAM are never zero; multiple HR IDs can be focused in Game Detail. **Checks:** RTL semantics/keyboard and measured production-build benchmark in §4. **Reasoning:** HIGH. **Provider/access gate:** NO.

### B20 — Player detail, recurrence and HR-log UI
- **Goal:** Complete the remaining player routes. **Depends:** B12, B14, B18. **Read:** FRONTEND_ARCHITECTURE, API_CONTRACT, SCREEN_MAP, KPI_SPEC.
- **Build:** `/players/:playerId`, `/players/:playerId/recurrence`, `/players/:playerId/home-runs`; optional ECharts recurrence/gap chart with text/table equivalent, event focus through Game Detail. **Exclude:** singular current-team claim, prediction or decorative charts.
- **Accept:** represented team appears only when scope proves it; observations retain per-event team; current drought/streak can exceed displayed N. **Checks:** RTL semantic/route tests, chart alternative and mobile/keyboard tests. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B21 — Synchronous CSV/PDF exports and UI actions
- **Goal:** Reuse analytical service outputs in files. **Depends:** B14, B16, B18–B20. **Read:** API_CONTRACT, FRONTEND_ARCHITECTURE, KPI_SPEC.
- **Build:** five export endpoint families, UTF-8 CSV, HTML/CSS→WeasyPrint PDF (A3 landscape for wide matrix), revision/as-of headers, scope/coverage legends and frontend pending/error/download actions. **Exclude:** separate KPI math, pagination truncation or async jobs.
- **Accept:** JSON/CSV/PDF agree on values, semantic nulls and one revision; Season export is complete. **Checks:** snapshot/contract comparisons and §4 synchronous export benchmarks. **Reasoning:** MEDIUM. **Provider/access gate:** NO.

### B22 — Ingestion gate, immutable raw evidence and commands
- **Goal:** Build a safe offline ingestion skeleton. **Depends:** B05–B06. **Read:** INGESTION_ARCHITECTURE, SOURCE_SNAPSHOT_POLICY, BACKFILL_SYNC_POLICY, PROVIDER_GAPS.
- **Build:** deny-by-default access check, internal management command boundaries, immutable content-addressed raw blobs/metadata, checksum verification, safe references, sync run/item checkpoints and leases using fixture payloads. **Exclude:** live fetch while G12 is open, public write API, secret-bearing raw metadata.
- **Accept:** blocked command makes no HTTP request; retry preserves snapshots; unreferenced blobs are cleaned only after safe reference/grace checks. **Checks:** offline gate, crash/restart, deduplication and path/secret tests. **Reasoning:** HIGH. **Provider/access gate:** NO for fixture implementation; real network execution is gated.

### B23 — Schedule normalization and PA classifier
- **Goal:** Turn fixture source claims into canonical candidates. **Depends:** B22. **Read:** INGESTION_ARCHITECTURE, COVERAGE_POLICY, DATA_MODEL, INGESTION_TEST_CASES.
- **Build:** versioned schedule/status mapping, gamePk identity, lifecycle observations, three-way PA/NON_PA/UNRESOLVED classifier and dense verified PA ordering; unknown event types stay unresolved. **Exclude:** treating every `allPlays` object or `result.type=atBat` as PA.
- **Accept:** the synthetic 76-play/75-PA case excludes only context-proven non-PA; reschedules preserve game identity. **Checks:** classifier, status conflict, doubleheader/suspension and replay tests. **Reasoning:** HIGH. **Provider/access gate:** NO.

### B24 — Reconciliation, coverage and quarantine
- **Goal:** Publish only internally consistent candidate games. **Depends:** B23. **Read:** INGESTION_ARCHITECTURE, COVERAGE_POLICY, DATA_QUALITY_POLICY, DATA_INVARIANTS, INGESTION_TEST_CASES.
- **Build:** per-batter/team PA and HR reconciliation, participation evidence checks, domain coverage assessment/history, source-link conflicts, quality issues and quarantine with prior canonical state retained. **Exclude:** promoting empty feeds or unmatched HRs to COMPLETE.
- **Accept:** mismatches downgrade coverage, preserve evidence and do not partially replace a game; repeated identical input is idempotent. **Checks:** fixture-driven G06, conflict/correction, zero-HR and rollback tests. **Reasoning:** HIGH. **Provider/access gate:** NO.

### B25 — Atomic revision and analytics invalidation
- **Goal:** Make accepted corrections visible consistently. **Depends:** B24. **Read:** INGESTION_ARCHITECTURE, API_CONTRACT, SOURCE_SNAPSHOT_POLICY.
- **Build:** short per-game atomic publish, monotonic DatasetRevision, durable invalidation intent and idempotent recalculation/cache invalidation for affected games/teams/players/leaderboards/current cutoff metrics. **Exclude:** historical `?dataset_revision=X` reads or premature incremental KPI arithmetic.
- **Accept:** no-op input does not advance revision; changed coverage invalidates stale zero; each API/export read observes one current revision. **Checks:** crash/transaction, concurrent-reader and correction/revision tests. **Reasoning:** HIGH. **Provider/access gate:** NO.

### B26 — Approved real-provider validation (G06)
- **Goal:** Validate the implemented classifier/completeness proof on permitted real samples. **Depends:** B22–B25 and externally recorded G12 approval for each operation. **Read:** PROVIDER_GAPS, COVERAGE_POLICY, INGESTION_ARCHITECTURE, INGESTION_TEST_CASES.
- **Build:** bounded, auditable validation of ordinary, zero-HR, multi-HR, doubleheader, postponed/rescheduled, suspended/resumed and known exceptional PA games; record G06 outcomes and unresolved cases. **Exclude:** automated access before G12 approval or CI live requests.
- **Accept:** per-batter/team PA and HR reconciliation demonstrates COMPLETE where justified; failures remain quarantined/UNKNOWN and block analytics launch claims. **Checks:** approved-run evidence, comparison with expected cases and explicit G06 gate decision. **Reasoning:** HIGH. **Provider/access gate:** YES — G12 external approval required before execution.

### B27 — Final 0.1 integration review
- **Goal:** Decide whether the implemented MVP satisfies its existing release gates. **Depends:** B13, B15, B17, B19–B21, B25–B26 (or record B26/G12 as blocking). **Read:** ROADMAP, API_CONTRACT, FRONTEND_ARCHITECTURE, KPI_SPEC, COVERAGE_POLICY, PROVIDER_GAPS.
- **Build:** integrated defect fixes and release evidence for backend/frontend/contract tests, exports, provenance, responsive/accessibility review, performance budgets and missing-data states. **Exclude:** predictions, new phase requirements or a pass while G06/G12 remain open.
- **Accept:** §5 Definition of Done is evidenced; otherwise report blockers without claiming launch readiness. **Checks:** clean CI, targeted critical flows, benchmark report and gate audit. **Reasoning:** MEDIUM. **Provider/access gate:** NO for review; launch remains conditional on G06/G12.

## 3. Dependency and coverage map

| Area | Items | Endpoint/screen coverage |
| --- | --- | --- |
| Domain, fixtures, math | B03–B10 | All canonical entities/migrations; executable windows, coverage and KPI cases. |
| API core | B11 | `seasons/`, `teams/`, `players/`, `games/`, `games/{id}/`, `today/`. |
| Player analytics | B14, B18 | `leaderboards/players/`, `players/{id}/`, `players/{id}/home-runs/`, `players/{id}/recurrence/`. |
| Team analytics | B16, B18 | `teams/{id}/`, `teams/{id}/home-runs/`, `teams/{id}/recurrence/`. |
| Frontend | B12–B13, B15, B17, B19–B20 | All eleven working 0.1 routes and Team Detail's four tabs. |
| Exports | B21 | All five CSV/PDF export families from API_CONTRACT. |
| Ingestion and gates | B22–B27 | Fixture-driven pipeline; B26 alone performs approved real-provider validation. |

## 4. Provisional performance and export budgets

Benchmark a **production React build**, locally served, with a deterministic ~60-player × 162-game Season matrix payload. Record browser version, machine CPU/RAM, viewport, payload size, five runs and median/worst measurements. Reference target: current stable Chrome on a 4-core/8-GB laptop at 1440×900, warm assets, no artificial network delay; also review mobile layout at 390 CSS px. From API data arrival to usable matrix: median ≤2.5 s, worst ≤4 s. After new-window data arrival, filter/window transition to usable view: median ≤600 ms. Horizontal keyboard/scroll interaction: no >100 ms main-thread task in the sampled navigation path, and no inaccessible offscreen column. Matrix DOM ≤30,000 elements and browser heap growth ≤150 MB relative to pre-matrix route; record both, rather than assuming virtualization. If these fail, profile first; add column-only TanStack Virtual when it improves results without losing keyboard/screen-reader reach. Normal 7/15/30/60G views need no automatic virtualization.

Benchmark synchronous exports against the same deterministic 60-player matrix with 30G, 60G and 162-game Season scopes. Record CSV/PDF wall time, peak process memory, output row/page counts, and revision. Provisional upper bounds on the same 4-core/8-GB machine: **30G CSV ≤5 s / PDF ≤15 s; 60G CSV ≤8 s / PDF ≤25 s; Season CSV ≤20 s / PDF ≤60 s; peak export process memory ≤500 MB**. Matrix CSV must contain every selected player×game cell plus metadata; PDF must include every selected game/row across explicit pages, with A3 landscape where useful. No silent Season truncation. If synchronous Season PDF misses its budget, log a visible implementation issue and make an explicit contract/release decision before launch; do not silently add asynchronous export machinery.

## 5. Quota-aware execution and 0.1 Definition of Done

Run one backlog item per Codex execution by default; combine at most two tightly coupled small items. Read only the item's **Read** files and the exact linked section needed for a contradiction. MEDIUM is default; HIGH is reserved for B07/B08/B10/B18/B19/B22–B26. Audit completed architecture-, analytics-, ingestion- or security-changing items before advancing; small UI leaf tasks may be batched. Do not re-read the full documentation set on each run. CI initially runs deterministic local backend/frontend tests, typecheck, lint and migration checks, never live MLB HTTP. A small Playwright set may be added at B27 only if critical matrix-to-game, URL restoration or export flows cannot be adequately checked with the chosen tests.

**0.1 is done only when:** all eleven routes and all read-only API/export families pass contract checks; canonical migrations/invariants, translated KPI/window/coverage cases and correction/idempotency tests pass; web/CSV/PDF agree on scope, values, semantic nulls and revision; DNP/NOT_WITH_TEAM/zero require their evidence; matrix and event focus work with keyboard, screen reader and mobile alternative; responsive and benchmark budgets are measured; safe provenance is visible without raw storage leaks; no predictive/advanced-phase feature is live; G06 real-provider completeness validation passes and G12 externally approved access covers actual automation/publication. If either gate is open, keep the synthetic build usable but do not claim production analytics readiness.
