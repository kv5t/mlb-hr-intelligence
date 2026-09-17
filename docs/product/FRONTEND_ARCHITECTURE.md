# MLB HR Intelligence — Frontend architecture (0.0-G, MVP 0.1)

**Specification only.** No React/Vite/TypeScript/CSS implementation is created here. The frontend consumes [API_CONTRACT.md](API_CONTRACT.md); it does not recalculate [KPI definitions](KPI_SPEC.md), infer coverage, or turn missing data into zero. Provider access and PA/HR completeness launch gates remain open. This document covers 0.1 only.

## 1. Stack, boundaries and app shell

Use the decided stack: React, TypeScript, Vite, React Router, Tailwind CSS, shadcn/ui, TanStack Query, TanStack Table, TanStack Virtual **only where measured**, Apache ECharts for justified charts, and Zod for runtime DTO validation. No default Redux/MobX/global store, Next.js, Bootstrap, jQuery, alternate table/chart libraries, service worker or offline mode. Components receive typed canonical API view models; provider fields, raw snapshots and ingestion controls never enter public UI state.

Desktop app shell has a persistent primary nav: Today, League, Teams, Players, Games; Matchup and Explore may appear as visibly unavailable future destinations, with no working 0.1 routes or misleading data. Social remains secondary and isolated, not a dependency of core screens. Tablet condenses the same destinations into a compact nav. Mobile primary nav is Today, League, Teams, Players, More; More contains Games and non-actionable future labels for Matchup/Explore. Navigation retains meaningful search parameters where the destination supports them; unsupported parameters are dropped visibly, not silently reinterpreted. Global season selector writes the URL for analytical routes.

## 2. Route → API map

The routes below are the only working 0.1 client routes. `seasons/` supports the season picker; once chosen, analytical links carry explicit `season`. `teams/{id}/home-runs/` powers the HR Log panel inside Team Detail without introducing a separate route.

| React Router path | Primary API queries | Composition / screen contract |
| --- | --- | --- |
| `/today` | `GET /api/v1/today/`, `seasons/` for picker | Explicit `season` and `date`; schedule games and recent descriptive leaders are independent sections. |
| `/league` | `GET /api/v1/leaderboards/players/`, `seasons/` | Analytical table; team filter supported, no analytical league/division filter (G02). |
| `/teams` | `GET /api/v1/teams/`, `seasons/` if season context | Identity browsing; sourced league/division metadata may filter this list only. |
| `/teams/:teamId` | Overview: `GET /api/v1/teams/{id}/`; Players: `players/?season=...&team=...` plus `leaderboards/players/?season=...&team=...` only for comparative KPIs; Games: `games/?season=...&team=...`; HR Log: `teams/{id}/home-runs/` | Lazy tab data; Players is source-supported known association/participation, never a complete historical roster. Invalid UUID/404 gets resource state. |
| `/teams/:teamId/recurrence` | `GET /api/v1/teams/{id}/recurrence/` | Shared team-game matrix; one request supplies columns/rows/cells. |
| `/players` | `GET /api/v1/players/` for identity/search; `leaderboards/players/` only when comparative metrics are shown | Two distinct responsibilities; never assume `/players/` owns rolling KPIs. Do not merge rows from different revisions into one asserted analytic value. |
| `/players/:playerId` | `GET /api/v1/players/{id}/` | Identity and scoped KPI overview; tabs link to recurrence/HR log. |
| `/players/:playerId/recurrence` | `GET /api/v1/players/{id}/recurrence/` | Ordered batting-game strip, gap data and server current/maximum metrics. |
| `/players/:playerId/home-runs` | `GET /api/v1/players/{id}/home-runs/` | Paginated verified HR events and separate semantic total. |
| `/games` | `GET /api/v1/games/` | Schedule/completed table; each GameSummary has `hr_count:MetricValue`. |
| `/games/:gameId` | `GET /api/v1/games/{id}/` | Score/status, positively evidenced participants, HR events and domain coverage. |

The `/players` route may show a search-first identity list and a distinct comparison table. Its comparative controls (`window`, `cutoff`, `home_away`, metric `ordering`) call the leaderboard contract. `team` on discovery is source-supported association in the season, not a complete roster assertion. Team Detail's HR Log tab and player HR route use their own endpoint rather than reconstructing events from matrix cells. Positive HR event drill-down uses `/games/:gameId` with optional `#hr-<canonical-event-uuid>` to focus a known event; the fragment is local frontend state, never an API filter. A multi-HR cell exposes every matching event ID in Game Detail. There is no separate 0.1 HR-event route or endpoint; no provider ID is a route identity.

## 3. Shareable URL state and navigation rules

React Router search params are the source of truth for analytical state: `season`, `window`, `cutoff`, `team`, `home_away`, `search`, `position`, `bats`, `ordering`, `page`, `page_size`; `date` for Today and `date_from/date_to/status` for Games. Team browsing may use `league`/`division` **only** on `/teams`; `/league` rejects them. Use the API's enum spellings and canonical UUIDs. Sort/filter changes reset `page=1`; a window or team change keeps an explicit cutoff only when it remains a valid intended request. All filters apply before last N on the server; the client never slices a returned Season sequence to fake 30G.

On first visit without `season`, load `seasons/`, choose a visible available season and `replace` the URL with the explicit year before analytical queries. On Today without `date`, derive a local calendar date solely as a UI default, then write the explicit date to the URL; the API validates its relationship to season. On analytical responses whose omitted cutoff resolves to `LATEST`, show the returned `scope.cutoff_date` and offer a share link that writes it as an explicit `cutoff`. A shared explicit date fixes the opportunity boundary; the dataset may still change after source correction, so show `data_as_of`. `dataset_revision` is **never** a search parameter or query-key input. Ephemeral state (open tooltip/dialog, mobile filter sheet, transient focus, local column chooser) stays local; no global client store is needed.

Unknown or invalid URL parameters are surfaced through validation/error UI or removed with a visible canonicalization action; do not silently query a different scope. Browser back/forward restores URL-driven filters and pagination. A link from a positive matrix cell to game detail carries the source season/filter context only for return navigation, never changes game identity.

## 4. Typed data boundary and TanStack Query

One conceptual API module owns base URL, parameter serialization, GET calls, error decoding, Zod runtime DTO validation and response envelope typing. TypeScript types provide compile-time checks; Zod is the single runtime schema dependency. React components and hooks never build endpoint URLs. Typed mappings include `MetricValue` as a discriminated state, `MatrixCell` as a discriminated state, nullable fields, top-level `scope`/`coverage`, and global `meta:{dataset_revision,data_as_of}`. Boundary checks reject an unknown enum or malformed essential field as a schema/error state; they never coerce it to zero. Presentation adapters format units and reasons but do not compute KPI totals, gap lengths, droughts, percentages, affiliations or coverage.

TanStack Query hooks are named by resource/route purpose. Query keys use a stable tuple such as `['v1','leaderboard','players',normalizedParams]` or `['v1','team',teamId,'recurrence',normalizedParams]`; `normalizedParams` contains **every accepted parameter that changes data or ordering**, including season, window, cutoff, represented team, home/away, search, position, bats, ordering, page and page_size where valid. Normalize omitted defaults once at the API boundary. `dataset_revision` comes only from responses; it is not an input to fetch or a hidden historical selector. A mutation-free 0.1 API needs no client optimistic updates.

Do not combine two analytical payloads into one claimed same-revision value unless their `meta.dataset_revision` matches. `/players` may render discovery and leaderboard sections independently if their revisions differ, with each section's freshness label; it must not join a profile row and stale metric into one unqualified number. On focus/manual refresh, refetch according to modest configurable freshness settings. Keep prior data during a same-scope page refresh only with a visible “refreshing” state; on scope change, do not show old-scope figures under new filters. A later higher revision invalidates/reloads affected visible queries by ordinary query refresh, without a second custom cache layer.

## 5. Page states and MetricValue presentation

Separate **initial loading** (skeleton with preserved labels), **refreshing** (previous same-scope data labeled), **transport error** (retry), **empty valid scope** (no results), **partial data** (valid resource with semantic nulls), and **stale freshness** (show `data_as_of` and retry). HTTP 200 with `UNKNOWN`/`INCOMPLETE` is not an error screen. A 400 invalid filter gives a recoverable filter message; 404 gives a resource-not-found view; 503 gives retry without inventing empty data. Each page can keep valid sections visible if another section fails. If window membership is unresolved, do not draw a last-N strip/matrix from a fabricated selection; explain the `scope.selection_state` and any lower-bound count.

One `MetricValue` presenter owns text, unit, optional numerator/denominator, reason help and accessible label. Mapping: `VALUE` shows the returned number including **0**; `NOT_APPLICABLE` shows “—” plus the reason; `UNKNOWN` shows “Unknown”; `INCOMPLETE` shows “Partial data”; `ORDER_UNVERIFIED` shows “Order unverified”; `INSUFFICIENT_HISTORY` shows “Not enough history”. `reason=NO_HR_IN_SCOPE` on a VALUE is an annotation, not a null. Labels distinguish batting games, team games and PA. Current drought/streak values come directly from the server and may exceed displayed N; never clamp or recompute them client-side. Provide tooltips **and** visible/help text or accessible descriptions so meaning is not tooltip-only.

Game HR counts use the same presenter on Games, Today and Game Detail. A nonfinal/unknown HR count remains nonnumeric. `HomeRunEventSummary[]` can show verified events while `total_hr` is incomplete; list length or pagination count is not presented as the definitive total.

## 6. Tables and recurrence matrix

TanStack Table owns column definitions, server-allowed sorting aliases, visible columns and page controls for League, Players comparison, Games and HR logs. URL filters/sorts drive API requests; do not sort incomplete KPI values locally into a false numeric rank. Unavailable values render their semantic text and sort according to the server (last in both directions). Identity/search tables use the discovery contract; comparative columns use leaderboard rows. Keep table headers, row labels, caption/summary, loading rows and “no results” state accessible. On narrow screens, prioritize identity and a few key metrics while retaining horizontal access or a detail view to every field; no data is permanently removed.

The team recurrence matrix renders **server-supplied shared columns once** and each row's aligned cells. Sticky player identity and season/window HR summary columns remain visible while game columns scroll horizontally. The default 7/15/30/60G views use ordinary rendering; ~162-column Season may use TanStack Virtual for **columns only** after measurement and accessible-focus testing. Rows are normally rendered without virtualization. Header shows official date, game number/opponent/home-away and links to game; suspended games stay at their official-date position. `scope.actual_game_count` is displayed only when definitive.

Cell rendering is exhaustive by `MatrixCell.state`: `HR_COUNT` shows the positive integer and opens Game Detail with optional HR-event fragment focus; `KNOWN_ZERO` shows numeric 0; `DNP` shows “DNP”; `ZERO_PA_APPEARANCE` shows “0 PA”; `NOT_WITH_TEAM` shows “Not with team”; `UNKNOWN` shows “?” with explanation; `INCOMPLETE` shows “Partial”. Never infer a different state from missing `hr_count` or from row absence. DNP and NOT_WITH_TEAM are server-evidenced states; G03/G05 may yield UNKNOWN instead. A two-HR game is one column with cell 2. Column order and row/cell alignment are validated at the typed boundary; mismatch is an error, not best-effort shifted cells.

Use a semantic table with row/column headers and focusable cell action/detail controls. Arrow keys may move among cells; Home/End moves within a row; Enter/Space opens the cell detail or linked game; Escape closes detail and restores focus. No keyboard trap. Each cell's accessible name includes player, official date/game number/opponent, represented team, and value/state, for example “Player X, April 12, game 2, two home runs” or “Player X, April 12, participation unknown”. Color and tooltip are never the sole signal. A linear game-by-game detail list/table is available on mobile and to assistive technology when the wide grid is difficult to navigate. If Season columns are virtualized, focused/offscreen columns must remain reachable by keyboard and the accessible alternative stays complete.

## 7. Charts, responsive behavior and design tokens

Use ECharts only for useful player recurrence timeline/gap distribution or a simple observed trend supported by the API. The chart consumes server observations/metrics, marks unknown barriers rather than connecting across them, and has a text/table equivalent with the same values. Loading, empty, partial and error states are explicit; resize with container and respect reduced motion. No decorative or predictive chart.

| Viewport concept | Shell and filters | Tables/matrix |
| --- | --- | --- |
| Mobile (<640 CSS px) | Bottom primary nav; Games in More; filters in shadcn sheet with Apply/Reset and focus return. | Search-first lists, key columns plus horizontal/detail access; matrix starts with short selected window and sticky identity, with accessible linear detail. |
| Tablet (640–1023 CSS px) | Compact nav and filter toolbar/sheet as space requires. | Condensed visible columns with horizontal scroll; shared matrix headers and sticky summaries remain. |
| Desktop (≥1024 CSS px) | Persistent primary nav and toolbar filters. | Full sortable tables; matrix has sticky identity/summary and horizontally reachable game columns. |

Breakpoints describe behavior, not a visual redesign. Tailwind/shadcn supply controls, tabs, dialogs/sheets, tooltips, filter forms, status badges and table affordances. Define semantic tokens for known/value, unknown, incomplete, not applicable, warning and selection with text/icon/shape as well as color. Test contrast, zoom, large text, touch targets and reduced motion. Do not encode HR/non-HR or data quality solely as red/green.

## 8. Export, accessibility and performance boundaries

CSV/PDF buttons call the corresponding **server export contracts** with the current normalized URL scope (`season`, `window`, explicit/resolved cutoff, team/home-away and other supported filters). The frontend never regenerates KPI values or renders a local PDF from table numbers. Export has a synchronous pending state, success/download affordance, clear error and retry; no async job UI. Display the returned/current revision and as-of when useful, and do not imply two separately fetched sections had identical revisions unless checked. Exports from Team Detail target its supported recurrence/HR-log views, not an invented detail export.

Keyboard and screen-reader behavior extends beyond matrix: skip link, visible focus, logical heading order, table captions and headers, filter sheet focus management, dialogs returning focus, status changes announced without excessive chatter, and text alternatives for charts. A cell/metric label says what is known (“0 home runs in a verified batting game”) or unknown (“home-run count unavailable: partial event coverage”), not merely a color or symbol. Touch targets and horizontally scrollable tables preserve access at mobile zoom.

Performance is measured per screen. Route-level code splitting can defer matrix/charts; TanStack Query avoids duplicate GETs and uses modest stale times; table pagination stays server-side. Profile League/Season matrix and ECharts before adding TanStack Virtual or memoization beyond normal component boundaries. No new global cache, service worker or offline data store in MVP. A slow export remains a visible synchronous action; operational sizing/limits belong to 0.0-H.

## 9. Future boundary and 0.0-H handoff

There are no working Matchup, Explore, Statcast, weather, park, model or Social routes in 0.1. Future navigation labels may communicate availability without loading nonexistent APIs. 0.0-H should turn these architecture rules into a prioritized implementation backlog, resolve practical export/matrix performance acceptance thresholds and implementation sequencing, and carry G06/G12 as launch gates. It must not reinterpret provider-access approval or coverage evidence as frontend decisions.
