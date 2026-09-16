# MLB HR Intelligence — Canonical data model (0.0-B)

**Status:** Conceptual 0.0-B architecture, not an ORM or SQL design. Names and fields below are canonical concepts. [KPI_SPEC.md](KPI_SPEC.md) and [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md) resolve 0.0-C formulas and eligibility; 0.0-D provider findings are recorded in [PROVIDER_STRATEGY.md](PROVIDER_STRATEGY.md) and [PROVIDER_FIELD_MAPPING.md](PROVIDER_FIELD_MAPPING.md); 0.0-E ingestion/versioning are specified in [INGESTION_ARCHITECTURE.md](INGESTION_ARCHITECTURE.md) and companion policies. This document remains conceptual.

## 1. Modeling principles and classification

External records pass through adapters, normalization and validation before entering canonical domain data. A provider identifier is a lookup/provenance key, never the canonical primary key. Canonical identity survives team changes, name changes and provider record replacement. Historical facts are attached to the team and contest at the time of the event. Event/opportunity observations, rather than current aggregate columns, are the basis for analytics.

| Category | Model contents | Excluded from canonical identity |
| --- | --- | --- |
| Canonical identity | `Season`, `Team`, `Player`, `Venue`, `Game` stable IDs and descriptive attributes | Current HR, last-30 HR, drought, probability |
| Temporal relationship | `PlayerTeamAffiliation` intervals; observed `PlayerGameParticipation` | A single `Player.team_id` standing for all history |
| Canonical observation | `PlateAppearance`, `HomeRunEvent`, game lifecycle and data-coverage observations | Cached leaderboard values |
| Source/provenance reference | `Provider`, `ExternalIdentifier`, `SourceRecordReference`, `FactSourceLink` | Raw provider JSON as domain entity |
| Derived data | Future reproducible KPI results keyed by definition, scope and cutoff | Source of truth for event counts |
| Model output | Future versioned, validated 0.4 artifact | `Player` or `Game` identity fields |

Surrogate canonical IDs are immutable UUID-like keys; exact storage type is left to implementation. Foreign references use these IDs. Imported metadata may be corrected with provenance without changing an entity's identity. Event records are never replaced by a current total.

## 2. Core entity catalog and conceptual fields

`required` means necessary to consider that entity structurally valid, not that an unverified provider is known to supply it. Nullable fields preserve unknown facts; completeness is separately recorded. Controlled semantic categories are canonical and retain an `OTHER/UNKNOWN` path until 0.0-D maps provider values.

### Season — canonical identity

| Field | Meaning |
| --- | --- |
| `id` (required) | Internal immutable season identity. |
| `year` (required) | MLB season year label; unique within the product's MLB season namespace. |
| `label`, `starts_on`, `ends_on`, `status` (optional) | Display and broad calendar context, not analytical window membership. Dates/status require verification. |

`Game.game_type` independently distinguishes regular season, postseason, spring training, All-Star and other/unknown; season identity alone does not imply game-type inclusion.

### Team — canonical identity

| Field | Meaning |
| --- | --- |
| `id` (required) | Stable franchise/team identity independent of player roster. |
| `display_name`, `abbreviation` (optional, sourced) | Current display metadata; historical labels may be retained in a later metadata-history mechanism if required. |
| `league`, `division`, `active_from/on`, `active_to/on` (optional) | Navigational metadata, potentially temporal; exact representation and source must be verified. |

No season HR, player roster or current-team foreign key is an identity field. A future franchise relocation/name-history requirement may need a separate identity-versus-season-team distinction; see open questions.

### Player — canonical identity

| Field | Meaning |
| --- | --- |
| `id` (required) | Stable person/player identity across teams and seasons. |
| `display_name`, `given_name`, `family_name` (optional, sourced) | Current presentation metadata; changes must not alter historical event identity. |
| `bats` (`L/R/S/UNKNOWN`), `throws` (`L/R/UNKNOWN`), `primary_position` (optional) | General identity/profile attributes, distinct from actual event-side and game role. |

There is **no** `Player.team`, `season_hr`, `last_30_hr`, `current_drought`, or `hr_probability` canonical field. A player's current team display is a temporal query and may be absent or multiple until resolved.

### Venue — canonical identity

| Field | Meaning |
| --- | --- |
| `id` (required) | Stable park/location identity. |
| `name`, `location` (optional, sourced) | Presentation context. |
| `timezone_id` (nullable) | IANA-style venue-local timezone identifier when known; never a substitute for a UTC instant. |

0.3 field orientation, roof, elevation, dimensions and park factors belong to separate time-aware context extensions, not required 0.1 venue fields.

### PlayerTeamAffiliation — temporal relationship

| Field | Meaning |
| --- | --- |
| `id`, `player_id`, `team_id` (required) | One observed association interval. A player may have several intervals, including return to a team. |
| `effective_from_date`, `effective_to_date_exclusive` (nullable) | Date-granularity interval bounds; a missing bound is unknown/open, not infinite certainty. |
| `boundary_precision` (`DATE/UNKNOWN`, optional) | Records whether the date bounds are source-supported; no instant precision is claimed by date-only fields. |
| `season_id` (nullable) | Optional season association for source scope; interval is not forced to one season. |
| `affiliation_kind/status` (nullable) | Only a small verified canonical classification if needed; no invented provider roster states. |
| provenance link(s) | Evidence for association and boundary changes. |

Intervals may overlap when sources or date precision cannot establish a unique same-day ordering. An interval requires verified temporal roster/transaction or equivalent dated evidence; a single game appearance cannot create a continuous interval. An interval is historical association evidence, **not** proof of appearance in every team game. Actual team represented is attached to `PlayerGameParticipation` and `PlateAppearance`. No historical interval is overwritten by a trade.

### Game — canonical identity plus current contest snapshot

| Field | Meaning |
| --- | --- |
| `id`, `season_id`, `home_team_id`, `away_team_id` (required) | One contest, independent of date; teams must differ. |
| `game_type` (required canonical category) | `REGULAR/POSTSEASON/SPRING/ALL_STAR/OTHER/UNKNOWN`; exact provider mapping and product inclusion remain open. |
| `venue_id` (nullable) | Venue if known; neutral/changed sites remain possible. |
| `official_date` (nullable) | Baseball's designated game date, distinct from scheduled and actual start. |
| `scheduled_start_at_utc`, `actual_start_at_utc`, `completed_at_utc` (nullable) | UTC instants when known; no naive local timestamps. |
| `status` (required) | Canonical broad state `SCHEDULED/POSTPONED/RESCHEDULED/IN_PROGRESS/SUSPENDED/COMPLETED/CANCELLED/OTHER/UNKNOWN`; semantics mapped in 0.0-D. |
| `finality` (required) | Separate `FINAL/NOT_FINAL/UNKNOWN` observation so a status label alone does not assert event coverage. |
| `scheduled_game_number` (nullable) | Source-supported doubleheader/order hint, not identity. |
| `home_score`, `away_score` (nullable) | Observed score if available; unknown remains null. |

`Game.id` identifies one contest. `official_date` and `scheduled_game_number` support display/order but are never unique identity. External game IDs attach through `ExternalIdentifier`. A reschedule or suspension should update the same contest when reconciliation establishes continuity; sampled provider identity behavior is in [PROVIDER_EVIDENCE.md](PROVIDER_EVIDENCE.md). Ambiguous identity is quarantined for reconciliation rather than merged by date/teams alone.

### GameLifecycleEvent — canonical observation of schedule/status history

| Field | Meaning |
| --- | --- |
| `id`, `game_id`, `event_kind` (required) | Schedule/status change such as scheduled, postponed, rescheduled, started, suspended, resumed, completed, cancelled or other. |
| `effective_at_utc`, `recorded_at_utc` (nullable/required respectively) | When change took effect if known, and when it was recorded. |
| `scheduled_start_at_utc` (nullable) | New scheduled instant for a schedule change, if known. |
| provenance link(s) | Source evidence; prior events are retained. |

This small history prevents a postponement/reschedule from erasing the fact that an earlier schedule existed. It is not a provider-specific lifecycle state machine. Exact event sequencing and transitions require 0.0-D evidence and 0.0-E update policy.

### PlayerGameParticipation — canonical observation, including explicit DNP

| Field | Meaning |
| --- | --- |
| `id`, `game_id`, `player_id`, `team_id` (required) | A player assessed for one team's participation in a contest; team must be a game participant. |
| `participation_state` (required) | `APPEARED`, `DID_NOT_APPEAR`, or `UNKNOWN`. No row means **not assessed**, not DNP. |
| `started` (nullable) | True/false only when observed; null means unknown. |
| `reported_pa_count` (nullable) | Provider-reported count retained as a source observation/reconciliation aid, not a substitute for PA events. Zero is meaningful only with adequate coverage. |
| `pa_coverage` (required) | `COMPLETE/PARTIAL/UNKNOWN/NOT_APPLICABLE` for this player/game. |
| provenance link(s) | Evidence for appearance, DNP, count and coverage. |

`DID_NOT_APPEAR` requires affirmative evidence that the player was in the relevant assessed population and did not appear; an absent box-score row or mere team affiliation is insufficient. `APPEARED` with complete PA coverage and zero PA rows represents a pinch-runner/defensive appearance; a pinch hitter who walked has a PA even without an at-bat. `UNKNOWN` preserves uncertainty. Eligibility and drought effects are defined in [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md). A player may have separate participation rows for both teams in one suspended/resumed contest.

### PlateAppearance — canonical opportunity observation

| Field | Meaning |
| --- | --- |
| `id`, `game_id`, `batter_id`, `batting_team_id`, `fielding_team_id` (required) | One batter opportunity in one contest; both teams are game participants and differ. |
| `pitcher_id` (nullable) | Player who pitched when verified; null preserves unknown and limits pitcher analysis. |
| `inning`, `half_inning` (nullable) | Baseball sequence context when known. |
| `game_pa_ordinal` (nullable) | Canonical within-game order if established; unique per game when present. Unknown order remains null. |
| `outcome_category` (required) | Broad `HOME_RUN/NON_HR/UNKNOWN`; finer outcome taxonomy is later work. |
| `batter_side_used`, `pitcher_hand_used` (nullable) | Actual event-side observations, separate from player profile handedness. |
| provenance link(s) | Provider record(s) and identifiers where available. |

Each PA belongs to exactly one game and batter; a complete event set supports an opportunity count. Source at-bat IDs are external identifiers/references, not canonical primary keys. Inning/half/ordinal provide deterministic ordering when verified; arbitrary import order must not masquerade as game order. The player participation record must be `APPEARED` for a verified PA, or be reconciled if source coverage is incomplete.

### HomeRunEvent — canonical observation

| Field | Meaning |
| --- | --- |
| `id`, `plate_appearance_id` (required, unique) | One credited batter HR tied 1:1 to one HR-producing PA. |
| `batter_id`, `game_id` (via PA; optionally denormalized later only with validation) | Trace to player and contest without an independent, conflicting event identity. |
| provenance link(s) | Evidence for the HR event and later source reconciliation. |

**Chosen over PA outcome alone:** A distinct entity gives the HR log, matrix drill-down, provenance, and future Statcast matching a stable HR-specific target. PA outcome remains `HOME_RUN` for consistency. A PA cannot yield two batter HR events. A two-HR game has two distinct PAs and two `HomeRunEvent` rows in one `Game`; 0.0-C defines it as one HR game for recurrence. Tracking data attaches through a future event-link layer rather than columns on this entity. If a source asserts an HR but its PA cannot yet be reconciled, retain the source record as unresolved, mark event coverage incomplete, and do not fabricate a canonical PA or silently publish a verified HR.

### GameDataCoverage — canonical coverage observation

| Field | Meaning |
| --- | --- |
| `id`, `game_id`, `domain` (required) | Coverage for `SCHEDULE/PARTICIPATION/PLATE_APPEARANCES/HR_EVENTS`, with one current assessment per game/domain and history handled by 0.0-E. |
| `state` (required) | `COMPLETE/PARTIAL/UNKNOWN/UNAVAILABLE`; never inferred from an empty event list. |
| `assessed_at_utc` (required), provenance link(s) | Freshness and basis of the assessment. |

This is separate from game `finality`: a completed game may have incomplete imported HR events. A known zero HR observation requires eligible game context and complete relevant HR coverage; eligibility itself is defined in 0.0-C. Coverage may later need team/player granularity if provider evidence demands it; player PA coverage already lives on participation.

## 3. Supporting identity and provenance references

### Provider

`id`, stable `code` and display name identify an external system, not its authority. Planned candidates are MLB Stats API and Baseball Savant/Statcast; weather is deferred. Provider configuration and sync operations belong to 0.0-E, and authority by category to 0.0-D.

### ExternalIdentifier — typed aliases alongside verified MLB IDs

`id`, `provider_id`, `entity_kind`, `external_value`, `canonical_entity_id`, optional `valid_from/valid_to` and `resolution_state` (`ACTIVE/SUPERSEDED/AMBIGUOUS`) preserve MLB player/team/gamePk/venue IDs and future identifiers. `entity_kind` is restricted to known canonical kinds; a domain validator ensures `canonical_entity_id` targets the corresponding entity. Unique active `(provider, entity_kind, external_value)` maps to at most one canonical entity. Multiple source IDs may map to one canonical entity over time; ambiguous/misassigned IDs are flagged, not silently reused. For high-volume MLB lookup, 0.0-D selects a hybrid: nullable unique `mlb_id` on Player/Team/Venue and `mlb_game_pk` on Game, alongside generic typed aliases for secondary providers and historic corrections. These are lookup keys, never canonical PKs. Keep alias-to-core consistency and provider namespace validation; physical schema belongs to later phases.

### SourceRecordReference and FactSourceLink

`SourceRecordReference` has `id`, `provider_id`, `source_record_key` (or stable raw-payload reference), `retrieved_at_utc`, optional provider-reported timestamp and payload pointer/checksum. It identifies a **source record**, not a trusted domain fact. `FactSourceLink` has `id`, `source_record_reference_id`, typed `canonical_entity_kind/id`, optional `field_or_claim` and `relation` (`SUPPORTS/CONFLICTS/WITHDRAWN/UNRESOLVED`). It links any canonical observation or identity assertion to one or more source records without embedding provider schema. Target-kind validation and source-link integrity are domain/ingestion checks; SQL FK coverage for a polymorphic target is not assumed. Conflicting links may coexist until 0.0-D reconciliation. Raw import storage and correction/version policies are 0.0-E.

The intended evidence path is player → matrix cell → game → PA → HR event → one or more source references. A derived metric instead points to canonical inputs plus its 0.0-C definition/version; a 0.4 model output points to input snapshot and model version. Neither is source data.

## 4. Relationships and cardinalities

| Relationship | Cardinality / optionality |
| --- | --- |
| Season → Game | One season to many games; every game has one season. |
| Team ↔ Player | Many-to-many through zero or more `PlayerTeamAffiliation` intervals. |
| Game → Team | Exactly one home and one away team; they differ. |
| Venue → Game | One venue to many games; game venue may be unknown. |
| Game → GameLifecycleEvent / GameDataCoverage | One to many history events; one current coverage assessment per domain, possibly absent before assessment. |
| Game → PlayerGameParticipation | One to many; absence of a row is not a DNP assertion. |
| Player/Team → PlayerGameParticipation | One to many; participation is game-specific. |
| Game → PlateAppearance | One to many; zero may mean no data until coverage says complete. |
| Player → PlateAppearance | One to many as batter; zero to many as pitcher, with pitcher nullable if unknown. |
| PlateAppearance → HomeRunEvent | Zero or one HR event; every HR event has exactly one PA. |
| Provider → ExternalIdentifier / SourceRecordReference | One to many. |
| SourceRecordReference ↔ canonical fact | Many-to-many through `FactSourceLink`. |

See [ERD.md](ERD.md) for the diagram and [DATA_INVARIANTS.md](DATA_INVARIANTS.md) for validation-ready rules.

## 5. Time, game identity and lifecycle

Canonical instants are UTC. `Venue.timezone_id` enables local presentation; local display date/time is derived for UI and is not identity. `official_date` is a baseball designation, possibly different from the venue-local date and either UTC timestamp. `scheduled_start_at_utc` is a plan, `actual_start_at_utc` is observed start, and `completed_at_utc` is observed completion; none alone identifies a game. Null means unknown, not midnight or no game.

Two games on the same date and between the same clubs retain separate `Game.id` and source mappings. `scheduled_game_number`, start times and official date help order/display them, but 0.0-C defines matrix/window order and 0.0-D verifies source semantics. A postponed game has a lifecycle observation and non-final state, with no inferred zero-HR observation. A rescheduled contest retains identity only when source reconciliation supports it. A suspended contest can have started, suspended, resumed and completed lifecycle events while retaining one `Game.id`; its official date and actual/completion instants remain separate. Window entry is defined in [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md).

## 6. Missing, unknown and zero

No participation row means unassessed, not DNP. `UNKNOWN` participation means assessed but unresolved. `APPEARED` plus complete PA coverage plus no PA rows means known zero PA. `DID_NOT_APPEAR` is affirmative DNP evidence. An empty HR event set means known zero only if relevant `GameDataCoverage(HR_EVENTS)` is complete and 0.0-C says the observation is eligible; otherwise it is unknown/incomplete. A final score does not prove complete PA or HR imports. Null identity/time/count fields mean unknown, never numeric zero. The UI and exports must preserve these distinctions.

## 7. Uniqueness and invariants

Canonical IDs are unique and immutable. A game has distinct home/away teams and one contest identity independent of date. Each participation is unique per `(game, player, team)`; a player may have two represented-team rows in one contest, as observed for game 746942. A PA belongs to one game and batter, has a unique `(game, game_pa_ordinal)` when ordinal is known, and valid batting/fielding game teams. `HomeRunEvent.plate_appearance_id` is unique and requires `PA.outcome_category=HOME_RUN`; one HR event cannot exist without its PA. A sourced external ID in an active provider namespace cannot silently identify two canonical entities. Affiliation intervals are retained; overlap alone is not invalid while boundary precision is limited. Fact/source links must resolve to existing typed targets. More detailed validation rules are in [DATA_INVARIANTS.md](DATA_INVARIANTS.md).

## 8. Lookup and index strategy

**Required uniqueness:** canonical PKs; `Season.year` within MLB namespace; active external `(provider, kind, value)`; `PlayerGameParticipation(game, player, team)`; non-null `PlateAppearance(game, game_pa_ordinal)`; `HomeRunEvent(plate_appearance)`; current `GameDataCoverage(game, domain)`; provider/source record identity where a stable key exists. Do **not** impose a unique `(teams, date)` game constraint.

**Likely 0.1 indexes:** `Game(season, official_date, game_type)` and team/date access for home and away; `PlayerGameParticipation(player, game)` and `(team, game)`; `PlateAppearance(game, ordinal)`, `(batter, game)`, `(pitcher, game)`; HR lookup through PA by batter/game/date (consider a validated join/index or measured denormalization); affiliation `(player, effective_from_date)` and `(team, effective_from_date)`; source links by canonical target and by source; external IDs by provider/kind/value. The team matrix joins team games, participation, PA/HR events and coverage. League source queries traverse the same observations.

**Wait for workload evidence:** extra covering/partial indexes, materialized leaderboards, duplicated HR batter/date fields, and cross-database optimization. SQLite WAL is the initial storage mode; use portable constraints/types/query concepts so PostgreSQL remains possible. Check SQLite write contention and query plans during 0.1 rather than inventing specialized indexes now.

## 9. History, corrections and deletion

Do not hard-delete a player, team, game, PA or HR event merely because metadata changes or a player is traded. Close/correct an affiliation with retained provenance; historical event team attribution remains on the participation/PA. A provider correction may amend canonical observations only through an auditable 0.0-E sync policy that retains source reference and correction history. Duplicate or withdrawn source records must not trigger silent merge/deletion. Exact tombstone, raw payload retention and backfill mechanics are 0.0-E; category authority is 0.0-D.

## 10. Future extension points, not 0.1 tables

- **0.2 Statcast:** A separate pitch/batted-ball tracking layer can link to `PlateAppearance` and `HomeRunEvent` via reconciled event identity. Its pitch type, speed, location, exit velocity, launch angle and distance remain outside the 0.1 HR table. It can retain separate source records when matching is unresolved.
- **0.3 Matchup:** `PlateAppearance.batter_id/pitcher_id`, actual sides, `Game.venue_id` and future pitch events provide join keys. Time-aware park/roof and weather observations can later attach to venue/game/time without changing core identity. No weather or park-factor schema is specified here.
- **0.4 Models:** Versioned derived/model artifacts may reference a subject, scope/cutoff, input snapshot, model version and evaluation metadata. No rating/probability field belongs on `Player` or `Game`.

## 11. KPI candidate → canonical source observations (no formulas)

| Candidate | Source entities / observations needed | Definition owner |
| --- | --- | --- |
| HR | `HomeRunEvent`, its PA/batter and Game; coverage | 0.0-C |
| PA | `PlateAppearance`, batter, Game; PA coverage | 0.0-C |
| HR/Game | HR events; Games, team/participation and coverage | 0.0-C |
| HR/PA | HR events and PAs for the same subject/scope; coverage | 0.0-C |
| PA/HR | PAs and HR events; coverage | 0.0-C |
| Games With HR % | Distinct Games, HR events, participation/affiliation and coverage | 0.0-C |
| Multi-HR Games | Game-linked HR events by subject; coverage | 0.0-C |
| Average HR Gap | Ordered Games, HR events, participation, coverage, official/start times | 0.0-C |
| Median HR Gap | Same ordered observations as average gap | 0.0-C |
| Current HR Drought | Games, participation, PAs, HR events, cutoff and coverage | 0.0-C |
| Maximum HR Drought | Same opportunity/history observations as current drought | 0.0-C |
| Current HR Streak | Ordered Games, participation, HR events and coverage | 0.0-C |
| Maximum HR Streak | Same ordered observations as current streak | 0.0-C |

This mapping proves availability of structural inputs, **not** a formula, eligibility decision or claim of provider completeness.

## 12. Decisions made in 0.0-B

1. Stable UUID-like identities for player, team, season, venue and contest, independent of external IDs and current team.
2. Historical `PlayerTeamAffiliation` intervals plus game-specific represented team; no mutable sole `Player.team`.
3. Separate `Game` identity, broad lifecycle state and small lifecycle history; UTC instants and venue timezone are distinct from official date.
4. Explicit participation state and PA coverage; absence of a row is not DNP.
5. PAs are canonical opportunities; HRs get a separate 1:1 `HomeRunEvent` for event-level traceability and enrichment.
6. Generic typed external-ID and source-reference links preserve multiple providers without making their schemas canonical.
7. Explicit coverage assessments prevent missing events from becoming zero.

The matching ADRs are in [DECISIONS.md](DECISIONS.md).

## 13. Unresolved questions and phase ownership

### 0.0-C — resolved in the KPI and window specifications

The 0.0-B handoffs—gap definition, multi-HR recurrence, 7G/15G/30G/60G membership, DNP/pinch-hit/zero-PA/trade treatment, denominators, drought/streak behavior, doubleheader/suspension order, regular-season scope and sample-size display—are resolved in [KPI_SPEC.md](KPI_SPEC.md) and [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md). This data-model document itself remains formula-free.

### 0.0-D — provider verification and mapping

Endpoints and actual fields; whether MLB Stats API and Statcast supply each proposed observation and identifier; gamePk lifecycle on postponement/reschedule/suspension; game-type/status/time mapping; source precision for affiliations, participation and PA ordering; coverage and latency; MLB/Statcast matching, conflicts and authority by category; provider limits, terms and licensing. No endpoint or provider authority is asserted here.

### 0.0-E — ingestion/update architecture

Source-record retention, change history/tombstones, retries, coverage-assessment update policy, ambiguity quarantine and reconciliation workflow. The domain needs these capabilities; their operational design is later.

### Domain follow-ups

Verify whether MLB franchise versus season-team identity requires separate canonical entities, whether name/league/division metadata needs temporal history, whether game/domain coverage needs finer granularity. The `(game, player)` participation exception is verified and resolved above. Decide from provider evidence and real 0.1 queries, not guesses.
