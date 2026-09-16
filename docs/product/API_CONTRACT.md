# MLB HR Intelligence — DRF API contract (0.0-F, MVP 0.1)

**Specification only.** This document defines a read-only public `/api/v1/` surface. It does not implement serializers, views or routes, approve provider access, change [KPI formulas](KPI_SPEC.md), or make incomplete source data publishable. The domain model, [window semantics](WINDOW_SEMANTICS.md) and [coverage policy](COVERAGE_POLICY.md) remain authoritative. G06 coverage validation and G12 external access approval remain open. No 0.2/0.3/0.4 endpoints are in this version.

## 1. Conventions, versioning and identifiers

- JSON uses `snake_case`; canonical enums are uppercase stable strings. Public resource URLs use internal canonical UUIDs (`{id}`). `mlb_id` and `mlb_game_pk` may appear as nullable lookup metadata, never as URL identity or canonical primary keys. No name matching defines identity.
- Dates are `YYYY-MM-DD`; instants are ISO-8601 UTC strings ending `Z`. Null means unknown, not zero or midnight. Game `official_date` is distinct from scheduled/actual timestamps.
- `/api/v1/` changes only compatibly within v1. New optional fields may appear; existing enum meanings and KPI IDs do not silently change. A breaking contract requires a later namespace. Unknown fields in provider records do not become public API fields automatically.
- Public API methods are `GET` only. No public ingestion mutation, provider access, quarantine or staff workflow endpoint exists. Safe provenance is limited to provider/source labels and freshness times; raw payloads, storage paths, credentials, access-decision records and issue internals stay private.

## 2. Consistency metadata and analytical scope

Every JSON response containing metrics, HR counts, recurrence observations or analytics includes top-level `meta: {dataset_revision, data_as_of}`. Analytical responses additionally put `scope` and, when applicable, `coverage` at the top level; paginated analytical rows may also carry their own `scope`/`coverage` where player denominators differ. `meta` never nests scope or coverage. `dataset_revision` is a monotonic **current-publication consistency token**, serialized as a string; `data_as_of` is the UTC canonical commit time, not the provider event time. One response and one CSV/PDF export read one consistent current revision. A request that cannot maintain that consistency retries internally or fails as a transport/service error. `dataset_revision` is **not** an accepted query parameter and 0.1 does not serve arbitrary historical revision reads. Window-scoped team/player metrics, recurrence, HR logs, leaderboards and Today leaders carry a top-level `scope`; Game Detail and schedule rows are game resources, so they carry game identity, coverage/MetricValue and `meta` without a `WindowScope`. Repeating the same `cutoff` later can produce corrected numbers with a newer revision.

Analytical endpoints require `season=YYYY` and accept `window=7G|15G|30G|60G|SEASON` (default `SEASON`). They analyze final `REGULAR` games only. Filters apply **before** last N. Player `30G` means last 30 verified batting games; team `30G` and team-matrix `30G` mean last 30 team games. A game with incomplete data remains a candidate, never silently replaced by an older complete game.

**Public cutoff:** optional `cutoff=YYYY-MM-DD`, inclusive of **all** games whose `official_date` is that date or earlier. Omission resolves the documented `LATEST` official date for the selected season/subject/team filter; the response always returns the resolved `cutoff_date` and `cutoff_source=EXPLICIT|LATEST`. No server wall-clock `now` is an analytical cutoff. Public game-ID cutoff is not supported in 0.1; clients must not pass a UUID as `cutoff` or assume date and game-ID semantics are interchangeable. Unknown official dates that can change membership yield `selection_state=UNKNOWN`; unresolved same-day order across the last-N boundary yields `ORDER_UNVERIFIED`. `cutoff` outside the selected season's relevant dates is valid and can yield an empty scope; malformed dates or incompatible parameters return 400.

`WindowScope`:

```json
{"season":2024,"subject":"PLAYER","subject_id":"<uuid>","game_type":"REGULAR","window":"30G","requested_n":30,"cutoff_date":"2024-04-30","cutoff_source":"EXPLICIT","team_filter_id":null,"home_away":"ALL","selection_state":"VALUE","actual_game_count":18,"known_eligible_game_count":18}
```

`selection_state` is `VALUE|UNKNOWN|INCOMPLETE|ORDER_UNVERIFIED`. `actual_game_count` is numeric only when membership is resolved; otherwise null and `known_eligible_game_count` is a lower bound. In a team matrix, the subject is `TEAM` and count refers to shared team-game columns. `requested_n=null` for `SEASON`. The server returns no claimed last-N observations when membership itself is unresolved.

## 3. MetricValue and coverage semantics

Every KPI uses `MetricValue`; the key is its exact `KPI_SPEC.md` ID (for example `player.hr` or `team.current_hr_drought_games`). No API formula is defined here.

```json
{"state":"VALUE","value":0,"unit":"HR","numerator":0,"denominator":null,"reason":null}
```

`state` is `VALUE`, `NOT_APPLICABLE`, `UNKNOWN`, `INCOMPLETE`, `ORDER_UNVERIFIED`, or `INSUFFICIENT_HISTORY`. `value` is a JSON number only for `VALUE`; otherwise it is null. `numerator`/`denominator` are exact integer counts when the corresponding inputs are established; they are null when unresolved. Ratios are computed without intermediate rounding; clients use the supplied counts/units for presentation. `reason` is a stable code or null. Examples: `NOT_APPLICABLE/NO_GAMES`, `NOT_APPLICABLE/ZERO_DENOMINATOR`, `NOT_APPLICABLE/NO_HOME_RUNS_IN_SCOPE`, `INSUFFICIENT_HISTORY/INSUFFICIENT_HISTORY`, `INCOMPLETE/PA_COUNT_MISMATCH`, `UNKNOWN/PARTICIPATION_POPULATION_UNVERIFIED`, `ORDER_UNVERIFIED/ORDER_UNVERIFIED`. A valid drought value may carry annotation `reason=NO_HR_IN_SCOPE`; that does not make it null. Unknown, DNP and incomplete values are never encoded as numeric zero. The API retains the reason precedence in KPI_SPEC.

`CoverageSummary` is a list of domain assessments `{domain, state, reason_codes}` with `domain=SCHEDULE|PARTICIPATION|PLATE_APPEARANCES|HR_EVENTS` and `state=COMPLETE|PARTIAL|UNKNOWN|UNAVAILABLE`; only public-safe reason codes are returned. Player PA availability may additionally be scoped to a player/game/team. Coverage state is not game finality. A valid resource with unavailable analytics returns HTTP 200 plus semantic state, not an HTTP error.

## 4. Pagination, ordering and filter grammar

Ordinary lists and HR logs use page-number pagination: `page` default 1, `page_size` default 25, maximum 100. Envelope: `{count, next, previous, results, scope?, coverage?, meta}`; `count` is the number of **listed records**, not a substitute for a MetricValue total when coverage is incomplete. `next`/`previous` are URLs preserving filters. Matrix columns/rows and player recurrence observations are not independently paginated. All list orderings have a stable canonical UUID secondary key; null/unavailable metric sort values are last in both directions. A `-` prefix requests descending order.

| Parameter | Valid endpoints | Rule |
| --- | --- | --- |
| `season` | analytical detail/recurrence/HR-log/leaderboard/Today endpoints; players/teams browsing optional; games list optional | Four-digit year; required for metrics; games detail identity needs none. On players discovery it scopes known association when `team` is used; it does not attach rolling KPIs. |
| `window` | team/player detail, recurrence, HR logs, leaderboard, exports; Today leader panel | `7G|15G|30G|60G|SEASON`; default `SEASON`. Team HR log uses team-game windows; player HR log uses batting-game windows. |
| `team` | players list, player detail/recurrence/HR log, leaderboard, games list | Canonical team UUID. For player analytics, represented-team filter precedes last N. On players discovery, it limits to source-supported association in the selected season and is not a complete roster claim. Not accepted on team-path endpoints. |
| `home_away` | team/player analytics, matrix, HR logs, leaderboard | `ALL|HOME|AWAY`, default `ALL`; player role follows represented team. |
| `cutoff` | analytical detail/recurrence/HR logs/leaderboard/exports; Today leader panel uses its `date` | Inclusive official date; no game-ID cutoff. Omitted resolves LATEST; returned in scope. |
| `league`, `division` | teams list only | Browsing on sourced current metadata when available. Historical analytical league/division attribution is unverified (G02); these parameters are rejected on the player leaderboard. |
| `search` | teams list, players list, leaderboard | Case-insensitive display-name search; identity still UUID. |
| `position`, `bats` | players list, leaderboard | Sourced profile filters; `bats=L|R|S|UNKNOWN`; no event-side inference. |
| `ordering` | ordinary lists, HR logs, leaderboard | Endpoint allowlist below; unknown field → 400. |
| `page`, `page_size` | ordinary lists, HR logs, leaderboard | Positive integers; page_size ≤100. |
| `date`, `date_from`, `date_to` | Today (`date`); games list (`date_from/date_to`) | Schedule calendar date/range, distinct from analytical official-date cutoff. |
| `status` | games list | Canonical game status enum; not a filter on analytics. |

`seasons` lists by `-year`; teams/players default by display name then UUID. Ordinary list ordering allowlists: teams `name,abbreviation`; players `name,position`; games `official_date,scheduled_start_at_utc`; HR logs `official_date`. Games default by `official_date`, scheduled game number/start then UUID; HR logs by official date, game order, PA ordinal then HR UUID. Leaderboard default is `-hr` then player UUID. Leaderboard allowlist: `name`, `hr`, `pa`, `hr_per_pa`, `pa_per_hr`, `hr_per_game`, `hr_game_pct`, `median_hr_gap_games`, `current_hr_drought_games`, `current_hr_streak_games`; aliases map only to corresponding `player.*` KPI IDs. There is no composite rank or qualification threshold. Unknown query parameters, invalid UUIDs/enums, `dataset_revision`, or unsupported filter combinations return 400 rather than being silently ignored.

## 5. Endpoint inventory and request contracts

All paths are under `/api/v1/`; `{id}` is a canonical UUID. Unless noted, responses are JSON. A resource existing with partial analytics returns 200. Identical filters mean identical scope in JSON and exports.

| GET path | Parameters | Main response / use |
| --- | --- | --- |
| `seasons/` | `page,page_size` | Paginated `SeasonSummary`; newest year first. |
| `teams/` | `season,league,division,search,ordering,page,page_size` | Paginated rows `{team:TeamSummary,metrics?:{team.*:MetricValue},scope?:WindowScope}`; season enables attached season metrics. |
| `teams/{id}/` | `season,window,home_away,cutoff` | `TeamSummary`, scoped KPI map, coverage/meta; `season` required. |
| `teams/{id}/recurrence/` | `season,window,home_away,cutoff` | Shared team-game matrix; `season` required. |
| `teams/{id}/home-runs/` | `season,window,home_away,cutoff,ordering,page,page_size` | Paginated verified `HomeRunEventSummary` plus `total_hr: MetricValue`; `season` required. |
| `players/` | `season,team,search,position,bats,ordering,page,page_size` | Paginated `PlayerSummary` identity/search/discovery only. No rolling KPI map; use `leaderboards/players/` for comparative analytics. |
| `players/{id}/` | `season,window,team,home_away,cutoff` | `PlayerSummary`, scoped KPI map, coverage/meta; `season` required. |
| `players/{id}/recurrence/` | `season,window,team,home_away,cutoff` | Ordered batting-game observations and gap data; `season` required. |
| `players/{id}/home-runs/` | `season,window,team,home_away,cutoff,ordering,page,page_size` | Paginated verified HR events plus `total_hr: MetricValue`; `season` required. |
| `games/` | `season,date_from,date_to,team,status,ordering,page,page_size` | Paginated `GameSummary` including `hr_count:MetricValue` on every game; may show schedule and non-regular games. |
| `games/{id}/` | none | `GameDetail` with `hr_count:MetricValue`, positively evidenced participants, HR events, domain coverage and meta. |
| `leaderboards/players/` | `season,window,team,home_away,cutoff,search,position,bats,ordering,page,page_size` | Paginated `LeaderboardRow`; `season` required. |
| `today/` | `season,date,window` | Date-focused games (each with `hr_count:MetricValue`) and basic descriptive leaders; both season and date required. Date must fall within verified Season calendar bounds or return 400 `DATE_OUTSIDE_SEASON` / `SEASON_CALENDAR_UNVERIFIED`. |

`players/` always returns identity/profile rows, with no rolling analytics. `teams/` without season returns identity rows; with season it may attach season metrics, with row scopes and coverage. Both include `meta` for consistency. The `/players` frontend route may compose discovery and leaderboard queries, but neither API contract silently inherits the other’s filters. `games/`, `today/` games and `games/{id}/` always include `hr_count:MetricValue`; unavailable or nonfinal counts use semantic null state, never missing field or zero by default. Games may span game types and HR count obeys coverage. Today is a screen aggregate for an explicit `date`, not a live prediction. `window` for its leader panel uses that date as official-date cutoff; only completed eligible games through that date contribute, and incomplete results remain semantic nulls. `today/` never claims that schedule `date` and official-date cutoff are the same concept for every game. `date` is checked inclusively against verified `Season.starts_on/ends_on` calendar bounds; absent bounds return 400 `SEASON_CALENDAR_UNVERIFIED`, and an outside date returns 400 `DATE_OUTSIDE_SEASON` rather than combining unrelated season/date values.

## 6. Resource schemas (compact)

Fields marked `?` may be null or omitted where not applicable; full response examples follow. `meta` is global consistency metadata on all endpoint envelopes. Analytical `scope` and applicable `coverage` are top-level siblings of `meta`; paginated rows may additionally carry row-specific scope/coverage.

| Schema | Fields |
| --- | --- |
| `SeasonSummary` | `id:UUID`, `year:int`, `label:string?`, `starts_on:date?`, `ends_on:date?`, `status:string?` |
| `TeamSummary` | `id:UUID`, `mlb_id:int?`, `display_name:string?`, `abbreviation:string?`, `league:string?`, `division:string?` |
| `PlayerSummary` | `id:UUID`, `mlb_id:int?`, `display_name:string?`, `given_name:string?`, `family_name:string?`, `bats:L|R|S|UNKNOWN`, `throws:L|R|UNKNOWN`, `primary_position:string?`, `represented_team:TeamSummary?` only when scope establishes it; no unsourced current-team assertion |
| `GameSummary` | `id:UUID`, `mlb_game_pk:int?`, `season:int`, `game_type:REGULAR|POSTSEASON|SPRING|ALL_STAR|OTHER|UNKNOWN`, `official_date:date?`, `scheduled_start_at_utc:timestamp?`, `status`, `finality:FINAL|NOT_FINAL|UNKNOWN`, `home_team:TeamSummary`, `away_team:TeamSummary`, `home_score:int?`, `away_score:int?`, `scheduled_game_number:int?`, `venue:{id,name,timezone_id}?`, `hr_count:MetricValue` always on games list, Today games and game detail |
| `GameDetail` | `game:GameSummary`, `participants:[{player:PlayerSummary,team:TeamSummary,participation_state:APPEARED,roles:[BATTER|PITCHER|FIELDER],pa_count:MetricValue}]` (positive appearance and each role require evidence), `home_runs:[HomeRunEventSummary]`, `coverage:CoverageSummary`, `meta` |
| `HomeRunEventSummary` | `id:UUID`, `game_id:UUID`, `plate_appearance_id:UUID`, `official_date:date?`, `batter:PlayerSummary`, `pitcher:PlayerSummary?`, `batting_team:TeamSummary`, `inning:int?`, `half_inning:TOP|BOTTOM|UNKNOWN`, `game_pa_ordinal:int?`, `provenance:{source_label,retrieved_at}?` |
| `MetricValue` | `state`, `value:number|null`, `unit:string`, `numerator:int?`, `denominator:int?`, `reason:string?` as §3 |
| `WindowScope` | Fields in §2, including resolved date, selection state and definitive or lower-bound count |
| `CoverageSummary` | `[{domain,state,reason_codes:string[]}]`; safe reason codes only |
| `MatrixColumn` | `game_id`, `official_date`, `scheduled_game_number?`, `opponent:TeamSummary`, `home_away:HOME|AWAY`, `game_status`, `coverage:CoverageSummary` |
| `MatrixCell` | `state:HR_COUNT|KNOWN_ZERO|DNP|ZERO_PA_APPEARANCE|NOT_WITH_TEAM|UNKNOWN|INCOMPLETE`, `hr_count:int|null`, `home_run_event_ids:UUID[]`, `reason:string?` |
| `MatrixPlayerRow` | `player:PlayerSummary`, `player_season_hr:MetricValue` (all teams), `window_hr:MetricValue` (matrix team only), `cells:MatrixCell[]` |
| `TeamRecurrenceResponse` | `team`, `scope`, `metrics:{team.*:MetricValue}`, `columns:MatrixColumn[]`, `rows:MatrixPlayerRow[]`, `coverage`, `meta` |
| `PlayerRecurrenceResponse` | `player`, `scope`, `metrics:{player.*:MetricValue}`, `observations:[{game_id,official_date,represented_teams:[TeamSummary],pa:MetricValue,hr:MetricValue}]`, `gaps:[{from_game_id,to_game_id,non_hr_games:MetricValue}]`, `coverage`, `meta` |
| `LeaderboardRow` | `player:PlayerSummary`, `metrics:{player.*:MetricValue}`, `scope:WindowScope` (row-specific player batting-game count), `coverage:CoverageSummary` |

`MatrixCell.hr_count` is positive only for `HR_COUNT`, exactly 0 only for `KNOWN_ZERO`, and null for every other state. `home_run_event_ids` is nonempty only for `HR_COUNT`; other states use `[]`. `DNP` requires affirmative nonappearance evidence, `NOT_WITH_TEAM` affirmative non-affiliation evidence, and `ZERO_PA_APPEARANCE` positive participation plus complete PA proof. G03/G05 can therefore produce `UNKNOWN` cells. Cells and columns have equal length and align by array index. A player on both teams in one contest can have separate team participation evidence; matrix rows are for the matrix team.

## 7. Recurrence and game-detail response examples

Examples use placeholder UUIDs and **synthetic values**, not real MLB results. No example establishes coverage for a provider game.

**Team recurrence, shortened to two columns:**

```json
{
  "team":{"id":"<team-uuid>","mlb_id":144,"display_name":"Example Team"},
  "scope":{"season":2024,"subject":"TEAM","subject_id":"<team-uuid>","game_type":"REGULAR","window":"30G","requested_n":30,"cutoff_date":"2024-04-30","cutoff_source":"EXPLICIT","team_filter_id":null,"home_away":"ALL","selection_state":"VALUE","actual_game_count":2,"known_eligible_game_count":2},
  "metrics":{"team.hr":{"state":"VALUE","value":1,"unit":"HR","numerator":1,"denominator":null,"reason":null}},
  "columns":[{"game_id":"<game-1>","official_date":"2024-04-28","scheduled_game_number":1,"opponent":{"id":"<opponent-uuid>","display_name":"Opponent"},"home_away":"HOME","game_status":"COMPLETED","coverage":[{"domain":"HR_EVENTS","state":"COMPLETE","reason_codes":[]}]},{"game_id":"<game-2>","official_date":"2024-04-30","scheduled_game_number":null,"opponent":{"id":"<opponent-uuid>","display_name":"Opponent"},"home_away":"AWAY","game_status":"COMPLETED","coverage":[{"domain":"HR_EVENTS","state":"COMPLETE","reason_codes":[]}]}],
  "rows":[{"player":{"id":"<player-uuid>","display_name":"Example Batter"},"player_season_hr":{"state":"VALUE","value":1,"unit":"HR","numerator":1,"denominator":null,"reason":null},"window_hr":{"state":"UNKNOWN","value":null,"unit":"HR","numerator":null,"denominator":null,"reason":"PARTICIPATION_POPULATION_UNVERIFIED"},"cells":[{"state":"HR_COUNT","hr_count":1,"home_run_event_ids":["<hr-uuid>"],"reason":null},{"state":"UNKNOWN","hr_count":null,"home_run_event_ids":[],"reason":"PARTICIPATION_POPULATION_UNVERIFIED"}]}],
  "coverage":[{"domain":"HR_EVENTS","state":"COMPLETE","reason_codes":[]},{"domain":"PARTICIPATION","state":"UNKNOWN","reason_codes":["PARTICIPATION_POPULATION_UNVERIFIED"]}],
  "meta":{"dataset_revision":"42","data_as_of":"2024-05-01T12:00:00Z"}
}
```

`player_season_hr` uses all represented teams through the same cutoff; it is independent of the two displayed columns. `window_hr` remains UNKNOWN because one applicable matrix cell is unresolved, even though one verified HR exists. If window membership itself is not VALUE, `columns=[]`, `rows=[]` and aggregate metrics are nonnumeric; the response carries `scope.selection_state` and known count instead of asserting a selected last N.

**Player recurrence:**

```json
{"player":{"id":"<player-uuid>","display_name":"Example Batter"},"scope":{"season":2024,"subject":"PLAYER","subject_id":"<player-uuid>","game_type":"REGULAR","window":"7G","requested_n":7,"cutoff_date":"2024-04-30","cutoff_source":"EXPLICIT","team_filter_id":null,"home_away":"ALL","selection_state":"VALUE","actual_game_count":7,"known_eligible_game_count":7},"metrics":{"player.current_hr_drought_games":{"state":"VALUE","value":41,"unit":"BATTING_GAMES","numerator":41,"denominator":null,"reason":null},"player.max_hr_drought_games":{"state":"VALUE","value":7,"unit":"BATTING_GAMES","numerator":7,"denominator":null,"reason":"NO_HR_IN_SCOPE"}},"observations":[{"game_id":"<game-uuid>","official_date":"2024-04-30","represented_teams":[{"id":"<team-uuid>","display_name":"Example Team"}],"pa":{"state":"VALUE","value":4,"unit":"PA","numerator":4,"denominator":null,"reason":null},"hr":{"state":"VALUE","value":0,"unit":"HR","numerator":0,"denominator":null,"reason":null}}],"gaps":[],"coverage":[{"domain":"HR_EVENTS","state":"COMPLETE","reason_codes":[]}],"meta":{"dataset_revision":"42","data_as_of":"2024-05-01T12:00:00Z"}}
```

The shortened `observations` array illustrates shape; a real resolved 7G response returns all seven observations. Current drought/streak and current PA drought scan their decisive suffix before displayed N within the same season/filters. Maximum runs and gap summaries remain window-local. An uncertain batting-game candidate makes window membership nonnumeric and prevents a falsely definitive `actual_game_count`.

**Game detail:**

```json
{"game":{"id":"<game-uuid>","mlb_game_pk":null,"season":2024,"game_type":"REGULAR","official_date":"2024-04-01","status":"COMPLETED","finality":"FINAL","home_team":{"id":"<home-uuid>","display_name":"Home"},"away_team":{"id":"<away-uuid>","display_name":"Away"},"home_score":null,"away_score":null,"hr_count":{"state":"INCOMPLETE","value":null,"unit":"HR","numerator":null,"denominator":null,"reason":"BOX_SCORE_PA_MISMATCH"}},"participants":[],"home_runs":[],"coverage":[{"domain":"PLATE_APPEARANCES","state":"PARTIAL","reason_codes":["BOX_SCORE_PA_MISMATCH"]},{"domain":"HR_EVENTS","state":"UNKNOWN","reason_codes":["PA_COVERAGE_UNRESOLVED"]}],"meta":{"dataset_revision":"42","data_as_of":"2024-05-01T12:00:00Z"}}
```

The example is synthetic; it illustrates why an empty `home_runs` list does not mean zero. In a real response `participants` contains only positively evidenced `APPEARED` players and only supported BATTER/PITCHER/FIELDER roles. DNP and UNKNOWN belong to matrix/coverage logic; no missing batting row becomes a participant or DNP. Safe `provenance` may show `source_label="MLB"` and retrieval time, never a raw path or access detail.

## 8. Leaderboard, Today and safe publication

Player leaderboard rejects `league`/`division` analytical filters until historical attribution semantics are verified (G02); TEAM filtering remains supported. Leaderboard `results[]` contain per-player metric maps using exact KPI IDs, a row `WindowScope`, and actual denominators via `MetricValue` plus `actual_game_count`. Recurrence columns include `player.hr_game_pct`, `player.median_hr_gap_games`, `player.current_hr_drought_games` and optional streaks; production columns include `player.hr`, `player.pa`, `player.hr_per_pa`, `player.pa_per_hr`, `player.hr_per_game`. Unavailable values sort last and display their state/reason. No qualification cutoff, single score or prediction is defined. Pagination metadata and global `meta` share the response revision.

`today/?season=2024&date=2024-04-30&window=30G` returns `{date,games:[GameSummary],recent_leaders:[LeaderboardRow],scope,coverage,meta}`. `games` are the schedule items for the requested calendar date and may include nonfinal/nonregular games; recent leaders use final regular-season games with official-date cutoff at that date. If recent leaders cannot be evaluated, the screen still returns known schedule games and semantic availability for the leader panel. No weather, matchup, Statcast or probability fields.

Game detail and HR logs expose only canonical HR events that have reconciled PAs. Logs may show verified events even while `total_hr` is `INCOMPLETE`, provided window membership itself is resolved. If last-N membership is unresolved, return no claimed selected records and expose the nonnumeric scope state. Their pagination `count` is the count of currently listed verified event records, **not** proof of a complete historical HR total. No provider raw-storage location or private issue detail is exposed.

## 9. HTTP errors and exports

Transport/resource errors differ from valid semantic unavailability. `404` means canonical UUID resource absent; `400` means invalid or unsupported parameter/combination; `405` for non-GET; `503` only when a consistent API read cannot be served. A valid known player with `player.hr=UNKNOWN` is `200`, not 404/503. Error envelope:

```json
{"error":{"code":"INVALID_FILTER","message":"Unsupported cutoff format","details":{"cutoff":"Use YYYY-MM-DD"}},"meta":{"dataset_revision":"42","data_as_of":"2024-05-01T12:00:00Z"}}
```

Errors never reveal raw provider payloads or internal paths. `dataset_revision`/`data_as_of` may be null when the service fails before a consistent current revision is available.

Synchronous `GET /api/v1/exports/leaderboards/players/`, `/exports/teams/{id}/recurrence/`, `/exports/players/{id}/recurrence/`, `/exports/teams/{id}/home-runs/`, and `/exports/players/{id}/home-runs/` accept the corresponding JSON filters plus `format=csv|pdf` (required). Pagination parameters are rejected: exports cover the full selected view. CSV is UTF-8 with explicit metric `value`, `state`, `reason`, `unit`, `numerator`, `denominator` columns; scope/revision fields are repeated in rows and also sent in headers so an empty file still has metadata. Matrix CSV has one row per player/game cell with its game ID/date/order columns rather than forcing a wide unknown-state encoding. PDF prints scope, denominator, revision/as-of, missing-value legend and the same KPI values. Both use one consistent current revision and response headers `X-Dataset-Revision`, `X-Data-As-Of`, appropriate `Content-Type` and `Content-Disposition`. Incomplete analytics are exported with semantic nulls, never substituted zero. No async export infrastructure is specified for 0.1.

## 10. Future boundary

Later versions may add tracking, park/weather, matchup or model resources under versioned contracts after their own evidence and rights gates. None are available through `/api/v1/` 0.1 routes above. Frontend presentation and component/state architecture belong to 0.0-G; final implementation backlog and operational sizing belong to 0.0-H.
