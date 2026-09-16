# MLB HR Intelligence — Architecture decision log

**Status key:** Accepted = current architectural choice, not necessarily implemented. Planned = intended source/feature awaiting verification or later phase. Each decision can be revisited when its stated condition occurs. Provider claims and verification now live in [PROVIDER_EVIDENCE.md](PROVIDER_EVIDENCE.md); earlier decisions retain their phase provenance.

## ADR-001 — Python and Django 5.2 backend

- **Status:** Accepted.
- **Context:** Canonical MLB domain, ingestion orchestration, analytics and staff tools need one backend platform.
- **Decision:** Use Python and Django 5.2.
- **Rationale:** A coherent Python domain and mature Django application/admin foundation fit the planned data workflow.
- **Consequences:** Domain logic belongs server-side; Django version upgrades require planned maintenance.
- **Revisit when:** Operational or domain requirements expose a material limitation.

## ADR-002 — REST API with Django REST Framework and django-filter

- **Status:** Accepted.
- **Context:** React, reports and future clients need explicit data contracts and query filters.
- **Decision:** Expose REST through Django REST Framework and use django-filter for supported filtering.
- **Rationale:** Clear resource contracts and conventional filtering support the analytics UI.
- **Consequences:** API schemas, pagination, caching and filter semantics must be defined in 0.0-F; no endpoints are specified in this phase.
- **Revisit when:** A documented interaction cannot be served cleanly or efficiently by REST.

## ADR-003 — SQLite with WAL initially

- **Status:** Accepted.
- **Context:** Initial scale and operations favor a simple database; concurrent reads are expected.
- **Decision:** Start with SQLite in WAL mode and avoid unnecessary SQLite-specific domain coupling.
- **Rationale:** Low operational overhead for the first release while leaving a PostgreSQL migration path.
- **Consequences:** Ingestion/write contention and backup behavior require testing; data model and query design should remain portable.
- **Revisit when:** Measured concurrency, volume, availability or operational needs justify PostgreSQL.

## ADR-004 — React, TypeScript and Vite frontend

- **Status:** Accepted.
- **Context:** The product is an interactive analytics application rather than a content/SEO-first site.
- **Decision:** Use React, TypeScript and Vite. Do not introduce Next.js without demonstrated future need; Vue, Nuxt, Angular and Svelte are outside the current stack.
- **Rationale:** Client-side interaction and typed components match the screen map without unnecessary rendering infrastructure.
- **Consequences:** Frontend architecture and deployment details belong to 0.0-G and later work.
- **Revisit when:** Real SEO, rendering or deployment requirements require a different framework.

## ADR-005 — Tailwind CSS and shadcn/ui

- **Status:** Accepted.
- **Context:** Dense responsive analytics screens need a consistent accessible visual system.
- **Decision:** Use Tailwind CSS and shadcn/ui; do not add Bootstrap or jQuery to the current stack.
- **Rationale:** Composable styles and components support responsive layouts and control consistency.
- **Consequences:** Accessibility and responsive behavior remain product obligations, not automatic library guarantees.
- **Revisit when:** The UI system cannot meet measured accessibility or maintainability needs.

## ADR-006 — TanStack Query for server state

- **Status:** Accepted.
- **Context:** Screens share filterable, refreshable server data with loading and error states.
- **Decision:** Use TanStack Query for server state and data fetching.
- **Rationale:** Consistent cache, loading and retry behavior across views.
- **Consequences:** Query keys, freshness and invalidation must align with data update cadence in 0.0-G.
- **Revisit when:** Data synchronization needs exceed the library's fit.

## ADR-007 — TanStack Table and TanStack Virtual

- **Status:** Accepted.
- **Context:** League tables and recurrence matrices can be wide and large.
- **Decision:** Use TanStack Table for complex tables; use TanStack Virtual where row/column scale warrants it.
- **Rationale:** Controlled sorting/filtering and selective rendering support analytical workflows.
- **Consequences:** Sticky columns, keyboard access and semantics need deliberate design; virtualization is conditional, not mandatory everywhere.
- **Revisit when:** Measured performance or accessibility reveals a better approach.

## ADR-008 — Apache ECharts

- **Status:** Accepted.
- **Context:** Recurrence and later contact/matchup trends need charts.
- **Decision:** Use Apache ECharts for data visualization.
- **Rationale:** Supports interactive analytical charts in the chosen frontend.
- **Consequences:** Each chart needs accessible text/table equivalents and responsive behavior.
- **Revisit when:** A chart requirement or accessibility finding cannot be met suitably.

## ADR-009 — Shared analytics for web, CSV and HTML/CSS plus WeasyPrint PDF

- **Status:** Accepted.
- **Context:** The original panoramic report should become exportable without diverging KPI definitions.
- **Decision:** Render reports with HTML/CSS and WeasyPrint, using A3 landscape where appropriate. DRF/web, CSV and PDF consume common canonical analytics definitions.
- **Rationale:** One definition avoids conflicting numbers across delivery formats.
- **Consequences:** Report layout must handle wide matrices, provenance and missing values; PDF generation starts in 0.1, not 0.0-A.
- **Revisit when:** Real report fidelity or scale cannot be achieved with this pipeline.

## ADR-010 — Django Admin for administration

- **Status:** Accepted.
- **Context:** Staff need to inspect imported entities, providers and sync health and later manage X sources/settings.
- **Decision:** Use Django Admin. Treat provider-owned MLB statistics as imported, generally read-only source records. Data authority by category is determined during Phase 0.0-D.
- **Rationale:** A conventional staff interface limits bespoke admin work and protects source integrity.
- **Consequences:** Permissions, auditability and exact admin representations require later design.
- **Revisit when:** Staff workflows require a dedicated interface.

## ADR-011 — Provider adapters and canonical domain boundary

- **Status:** Accepted.
- **Context:** MLB, tracking and weather sources differ in identifiers, coverage and event representation.
- **Decision:** Place adapters, normalization and validation between external providers and canonical data; prevent provider schemas from defining domain architecture. Preserve external player/team/gamePk/venue identifiers for traceability.
- **Rationale:** Analytics can remain stable when a provider changes, and displayed facts can be traced.
- **Consequences:** 0.0-B defines canonical entities; 0.0-D verifies fields, authority, reconciliation and mapping; 0.0-E designs ingestion.
- **Revisit when:** A verified source or domain requirement exposes an insufficient boundary.

## ADR-012 — Planned MLB core source

- **Status:** Planned; unverified.
- **Context:** 0.1 needs teams, players, seasons, schedules, games, PA and HR events.
- **Decision:** Evaluate MLB Stats API as the planned core provider.
- **Rationale:** It is the nominated source for core MLB categories, subject to evidence.
- **Consequences:** No endpoint, schema, coverage, rate limit, terms or data authority is assumed; 0.0-D must verify before integration.
- **Revisit when:** 0.0-D finds unsuitable coverage, reliability or licensing.

## ADR-013 — Planned advanced tracking source

- **Status:** Planned; unverified.
- **Context:** 0.2 needs event-level contact and pitch tracking.
- **Decision:** Evaluate Baseball Savant/Statcast as the planned advanced provider. pybaseball, if used, remains behind our adapter and never defines the canonical domain.
- **Rationale:** It is the nominated source for future tracking analysis, pending verification and reconciliation.
- **Consequences:** Event matching, field definitions, provenance and usage conditions belong to 0.0-D; no 0.1 Statcast claim.
- **Revisit when:** Verification shows unavailable or unsuitable data or terms.

## ADR-014 — Weather and park providers deferred

- **Status:** Planned; deferred.
- **Context:** 0.3 matchup context may need forecast/historical weather and park characteristics.
- **Decision:** Select a weather provider (WeatherAPI or another verified option) in 0.0-D; verify Baseball Savant/Statcast park-factor availability and other park facts before use. Implement contextual analysis in 0.3.
- **Rationale:** Availability, provenance, latency, limits and licensing are not established in 0.0-A.
- **Consequences:** No weather, wind or park intelligence in 0.1; roof and field orientation must inform any later wind interpretation.
- **Revisit when:** 0.0-D evidence changes provider choice or available context.

## ADR-015 — Descriptive analytics precede models

- **Status:** Accepted.
- **Context:** HR is a rare event and arbitrary scores could mislead users.
- **Decision:** 0.1 is descriptive, 0.2 adds observed tracking, 0.3 adds context, and only 0.4 may add historically validated ratings/probabilities. Do not assume traditional Elo is suitable for player HR prediction.
- **Rationale:** Trust depends on definitions, provenance, sample sizes, historical evaluation and calibration.
- **Consequences:** Ratings and probability are hidden until validated and visually distinct from observed statistics.
- **Revisit when:** Formal evidence supports a justified model design and product claim.

## ADR-016 — Original PDF is concept reference, not data

- **Status:** Accepted.
- **Context:** The original report demonstrates a useful matrix but contains manually generated example values.
- **Decision:** Reuse the interaction concept, not its statistics as production facts.
- **Rationale:** Production claims require verified provider data or reproducible canonical calculations.
- **Consequences:** No copied or fake MLB statistics in the product or this specification.
- **Revisit when:** Never for data authority; layout ideas may evolve through user testing.

## ADR-017 — Social is isolated and auxiliary

- **Status:** Accepted.
- **Context:** Public X timelines may be useful but external embeds can fail or load slowly.
- **Decision:** Keep Social secondary and independent. Admin may later configure about ten public sources and official embeds; no paid X API is required for the initial concept. Social cannot block Today, League, Teams, Players, Games or analytics APIs.
- **Rationale:** Core analytics must remain reliable regardless of third-party embed behavior.
- **Consequences:** Separate loading/error states and no data dependency from social to analytics. Release timing is independent, no earlier than planned 0.3 work.
- **Revisit when:** Product demand, embed terms or availability warrant a different auxiliary design.

## ADR-018 — Stable identities and temporal player-team affiliation

- **Status:** Accepted for 0.0-B conceptual model.
- **Context:** Trades, returns and metadata changes must not rewrite historical team views.
- **Decision:** Give Player and Team immutable internal identities; represent historical association with `PlayerTeamAffiliation` intervals and record represented team on each game participation/PA. Do not use a sole `Player.team` field.
- **Rationale:** An interval captures membership history while a game observation identifies the team for an actual event even when boundary dates are imprecise.
- **Consequences:** Current team is a temporal query; overlaps/unknown interval bounds need reconciliation. Metrics using affiliation require 0.0-C rules.
- **Revisit when:** Verified provider data shows franchise/season-team distinctions or participation exceptions requiring more identity structure.

## ADR-019 — Contest identity, lifecycle and UTC time

- **Status:** Accepted for 0.0-B conceptual model.
- **Context:** Doubleheaders, postponements and suspended games cannot be identified by calendar date.
- **Decision:** Use one immutable Game ID per contest, distinct game type/status/finality, official date, optional UTC scheduled/actual/completion instants, venue timezone, and a small `GameLifecycleEvent` history.
- **Rationale:** Separate identity, baseball date, schedule and observed time preserve distinct contests and status changes.
- **Consequences:** Same-day games remain separate; local display is derived. Game continuity and status mapping need provider verification in 0.0-D; window order is specified in 0.0-C.
- **Revisit when:** Verified game identity/lifecycle behavior requires a different reconciliation or segment representation.

## ADR-020 — Explicit participation and completeness

- **Status:** Accepted for 0.0-B conceptual model.
- **Context:** DNP, zero-PA appearance and incomplete source coverage cannot share one zero value.
- **Decision:** Use `PlayerGameParticipation` with `APPEARED/DID_NOT_APPEAR/UNKNOWN`, separate player PA coverage, and `GameDataCoverage` by game/domain. No row means unassessed.
- **Rationale:** Known zero and missing observations remain distinguishable for later recurrence calculations.
- **Consequences:** DNP needs affirmative evidence; final game status does not prove event coverage. Drought/window effects are specified in [KPI_SPEC.md](KPI_SPEC.md) and [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md).
- **Revisit when:** Provider coverage requires finer assessment scope or participation cases exceed the 0.1 model.

## ADR-021 — PA opportunity and separate HR event

- **Status:** Accepted for 0.0-B conceptual model.
- **Context:** HR logs, matrix drill-down and future tracking matching need event-specific identity while PA is the opportunity unit.
- **Decision:** Represent each PA as a canonical opportunity and each credited batter HR as a separate `HomeRunEvent` linked 1:1 to an HR-producing PA. Keep event-specific batting side separate from player profile side.
- **Rationale:** A distinct HR target supports provenance, enrichment and multi-HR games without storing aggregates on Player.
- **Consequences:** Outcome/event consistency must be validated; two HR in a game require two PAs. Provider PA ordering and matching await 0.0-D.
- **Revisit when:** Verified source representation cannot support the required PA/event linkage without a documented alternate observation layer.

## ADR-022 — Typed external identifiers and fact provenance

- **Status:** Accepted for 0.0-B conceptual model.
- **Context:** Multiple providers may name the same player/game differently or disagree on a fact.
- **Decision:** Use provider-namespaced, entity-typed `ExternalIdentifier` references and separate `SourceRecordReference`/`FactSourceLink` evidence. Canonical IDs do not embed provider IDs; multiple source links may support or conflict with a fact.
- **Rationale:** Reconciliation stays possible without making provider JSON the domain schema.
- **Consequences:** Typed polymorphic targets require explicit domain validation and indexes. Authority, namespace/mapping and conflict policy are in the 0.0-D provider documents; ingestion history remains 0.0-E.
- **Revisit when:** Measured lookup cost or verified identifier behavior warrants typed per-entity storage.

## ADR-023 — Regular-season-only MVP analytical scope

- **Status:** Accepted for 0.0-C MVP definitions.
- **Context:** Canonical storage distinguishes multiple game types, but mixed leaderboards would compare unlike competitions.
- **Decision:** MVP 0.1 descriptive leaderboards, recurrence KPIs and default matrices include final `REGULAR` games only; other/unknown game types remain stored and navigable but outside these analytics.
- **Rationale:** One explicit competition scope makes rates and recurrence comparable.
- **Consequences:** Every KPI result carries season/game-type scope; provider game-type mapping still needs 0.0-D evidence.
- **Revisit when:** A separately labeled postseason or other-type product view is specified and validated.

## ADR-024 — Distinct team, player and matrix windows

- **Status:** Accepted for 0.0-C MVP definitions.
- **Context:** A team schedule and an individual player's batting opportunities differ, especially with DNP, zero PA and trades.
- **Decision:** Team rolling N uses final regular-season team games; player rolling N uses games with verified appearance and ≥1 PA; team matrix columns use the shared team-game window. Apply team/home-away filters before last N. DNP and zero-PA appearances remain visible but outside player batting-game sequences.
- **Rationale:** The selected opportunity unit is explicit for every display and denominator.
- **Consequences:** `Player 30G` and `Matrix 30G` can cover different dates; labels and actual denominators must show that difference.
- **Revisit when:** Research supports a separately named team-schedule-based player metric; do not silently change these IDs.

## ADR-025 — HR-gap and multi-HR recurrence semantics

- **Status:** Accepted for 0.0-C MVP definitions.
- **Context:** HR event counts and HR-game spacing answer different questions.
- **Decision:** One game with ≥1 HR contributes one recurrence HR game, though all its HR events count toward production. HR Gap is the number of eligible non-HR games strictly between consecutive HR games; adjacent HR games have gap 0.
- **Rationale:** The recurrence unit is the game, while production retains event multiplicity.
- **Consequences:** Gap summaries need at least two HR games, and labels must not call HR/Game recurrence.
- **Revisit when:** A separately named interval-distance metric is requested; do not redefine HR Gap in place.

## ADR-026 — Coverage gates and separate game/PA droughts

- **Status:** Accepted for 0.0-C MVP definitions.
- **Context:** Skipping an incomplete final game can fabricate a zero, gap or streak; PA and games are different opportunity units.
- **Decision:** Select final candidate games before checking KPI coverage; incomplete/unknown evidence makes affected KPI nonnumeric rather than substituting an older complete game. Define game droughts for player/team and separate, secondary PA droughts for players. Current/maximum droughts include applicable scope edges; no-HR scope is annotated.
- **Rationale:** Results remain reproducible and do not hide missing observations or mix denominators.
- **Consequences:** Some windows display nonnumeric KPIs until data is repaired; request N, actual count, cutoff and coverage reason must be visible. API/UI representation is specified later.
- **Revisit when:** Verified coverage and user research justify a separately named partial-data estimate; never relabel it as the complete KPI.

## ADR-027 — Cutoff-state current metrics and uncertain selection

- **Status:** Accepted in 0.0-D closeout of 0.0-C.
- **Decision:** Current game/PA drought and game streak scan backward beyond displayed N through the same season/filter scope. Maximum runs remain window-local. An unresolved same-day tie crossing N invalidates all window membership KPIs; an unknown official date may invalidate date-cutoff membership.
- **Evidence:** Definition correction and deterministic cases in [KPI_TEST_CASES.md](KPI_TEST_CASES.md).

## ADR-028 — Player participation uniqueness includes represented team

- **Status:** Accepted from first-party game evidence.
- **Decision:** Key participation by `(game, player, team)`. Full-season player batting-game count deduplicates one contest across represented teams; team-filtered events use their actual team.
- **Evidence:** MLB game 746942, Danny Jansen 643376, documented in [PROVIDER_EVIDENCE.md](PROVIDER_EVIDENCE.md).

## ADR-029 — Hybrid MLB lookup keys and provider aliases

- **Status:** Accepted conceptually for 0.0-D; storage design remains 0.0-E/implementation.
- **Decision:** Keep internal canonical PKs; add unique nullable verified MLB ID lookup columns on Player, Team, Venue and Game, plus generic typed `ExternalIdentifier` for aliases and secondary providers. Enforce consistency between any duplicated MLB alias and core key.
- **Rationale:** The observed gamePk/player/team/venue IDs are frequent join and retrieval keys. Direct unique indexes and FKs on canonical entities simplify SQLite lookup and remain portable to PostgreSQL. Typed aliases preserve cross-provider linkage. The cost is explicit MLB coupling in nullable lookup fields, without making a provider ID the canonical identity.
- **Evidence:** [PROVIDER_EVIDENCE.md](PROVIDER_EVIDENCE.md).
