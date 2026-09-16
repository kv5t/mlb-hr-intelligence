# MLB HR Intelligence — Architecture decision log

**Status key:** Accepted = current architectural choice, not implemented in 0.0-A. Planned = intended source/feature awaiting verification or later phase. Each decision can be revisited when its stated condition occurs. No provider endpoint or capability is claimed verified here.

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
- **Decision:** Use Django Admin. Treat provider-owned MLB statistics as imported, generally read-only authoritative facts.
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
