# MLB HR Intelligence — Data invariants (0.0-B)

**Status:** Validation-ready conceptual rules. Future database constraints, model validation, ingestion checks and tests should implement them according to actual provider capabilities. A rule marked **conditional** applies only once its prerequisite evidence or coverage exists. The rules do not decide KPI eligibility or provider authority.

## Identity invariants

| ID | Rule | Candidate enforcement |
| --- | --- | --- |
| I-01 | Canonical `Season`, `Team`, `Player`, `Venue`, `Game`, PA and HR event IDs are unique, immutable and independent of provider IDs. | Database PK; update validation. |
| I-02 | `Season.year` is unique within the MLB season namespace; season boundaries, if known, do not define game identity. | Unique key; domain validation. |
| I-03 | A player's current name, team, batting side or position change does not change `Player.id` or rewrite earlier game facts. | Domain/update validation. |
| I-04 | No `(official_date, home_team, away_team)` uniqueness rule exists; two same-day contests may be distinct. | Schema review/test. |

## Relationship and temporal invariants

| ID | Rule | Candidate enforcement |
| --- | --- | --- |
| R-01 | Every `PlayerTeamAffiliation` references an existing player and team; optional season scope, if set, references a season. | FKs. |
| R-02 | If both affiliation bounds are known, `effective_from_date < effective_to_date_exclusive`. Unknown bounds and limited precision remain explicit. | Check/model validation. |
| R-03 | A trade/return creates or corrects intervals without deleting earlier affiliation evidence. Overlap alone is not forbidden when dates are imprecise. | Ingestion validation/audit. |
| R-07 | Date-only affiliation bounds can claim only `DATE` or `UNKNOWN` precision; game-specific team attribution comes from participation/PA. | Model validation. |
| R-04 | Every participation and PA team is one of the game's two teams. `PA.batting_team_id` and `PA.fielding_team_id` differ. | Domain validation; FKs. |
| R-05 | A game's player-team attribution comes from its observed participation/PA, not a current roster lookup. | Domain query test. |
| R-06 | `PlayerGameParticipation` is unique by `(game, player, team)`. The same player may represent both clubs in one suspended/resumed contest; no `(game, player)` unique constraint is allowed. | Unique key plus reconciliation. |

## Game and time invariants

| ID | Rule | Candidate enforcement |
| --- | --- | --- |
| G-01 | Every game references one season and two different home/away teams. | FKs and inequality check. |
| G-02 | `Game.id` represents one contest regardless of schedule date, doubleheader number, postponement or suspension. A merge needs verified identity evidence. | Reconciliation validation. |
| G-03 | Game type is a canonical semantic category with `OTHER/UNKNOWN`; unknown provider values are retained for mapping review rather than forced into regular season. | Enum/domain validation. |
| G-04 | `official_date` is distinct from scheduled/actual/completion instants. Known instants are UTC; local display derives from venue timezone and is not stored as identity. | Type/model validation. |
| G-05 | A postponed, cancelled, suspended or otherwise non-final game never implies an observed 0-HR game merely because its event list is empty. | Analytics precondition test. |
| G-06 | A reschedule or resumed segment may update the same `Game.id` only after identity reconciliation; status/schedule history remains linked. | Ingestion validation. |
| G-07 | `Game.finality=FINAL` does not imply `GameDataCoverage(HR_EVENTS)=COMPLETE` or PA coverage complete. | Domain validation/test. |
| G-08 | Known `GameLifecycleEvent.recorded_at_utc` and `GameDataCoverage.assessed_at_utc` are UTC; unknown event effective time remains null. | Type/model validation. |

## Participation and PA invariants

| ID | Rule | Candidate enforcement |
| --- | --- | --- |
| P-01 | No participation row means unassessed. It cannot be interpreted as `DID_NOT_APPEAR`. | Analytics/query test. |
| P-02 | `DID_NOT_APPEAR` requires affirmative source-backed assessment; it cannot coexist with a verified PA for that player/game/team. A different team row in the same game is assessed separately. | Ingestion/domain validation. |
| P-03 | `APPEARED` may have zero PA. **Conditional:** with `pa_coverage=COMPLETE` and zero PA rows, zero is known; otherwise PA count may be unknown. | Coverage/consistency test. |
| P-04 | `reported_pa_count` is nullable and nonnegative when known; it is a sourced observation, not a replacement for canonical PA rows. Disagreement is flagged. | Check/reconciliation. |
| P-05 | Every PA references exactly one game, batter, batting team and fielding team. Pitcher is nullable only when genuinely unresolved, and pitcher-dependent analysis must then exclude or mark it missing. | FKs/domain validation. |
| P-06 | A verified PA implies player participation in that game for the batting team; an absent/unknown participation row is a reconciliation task, not evidence of DNP. | Ingestion validation. |
| P-07 | `game_pa_ordinal`, when known, is unique within the game and nonnegative/positive per final ordering convention; null means order is unresolved. Import order cannot be used as a silent substitute. | Conditional unique key; domain validation. |
| P-08 | `batter_side_used` is an event observation and does not overwrite `Player.bats`, especially for switch hitters. | Domain/update validation. |

## HR event invariants

| ID | Rule | Candidate enforcement |
| --- | --- | --- |
| H-01 | Every `HomeRunEvent` references exactly one existing PA; `plate_appearance_id` is unique among HR events. | FK and unique key. |
| H-02 | An HR event requires `PA.outcome_category=HOME_RUN`. Conversely, a PA confidently classified HOME_RUN should have its HR event or be flagged incomplete pending reconciliation. | Domain/ingestion validation. |
| H-03 | A PA cannot produce multiple credited batter HR events. Two HR in one game require two PA and two HR events. | Unique key and scenario test. |
| H-04 | HR event batter/game/team are derived from its PA. Any later denormalized copy must match the PA. | Domain validation. |
| H-05 | An HR event has at least one provenance link before being published as verified; conflicting source links may coexist with explicit unresolved status. | Publication/ingestion validation. |

## Missing-data and coverage invariants

| ID | Rule | Candidate enforcement |
| --- | --- | --- |
| M-01 | Null/unknown is never converted to numeric zero or `DID_NOT_APPEAR` by default. | Analytics/API/export tests. |
| M-02 | An empty PA or HR set does not establish zero unless the matching coverage assessment is complete for the relevant scope. | Analytics precondition test. |
| M-03 | Coverage state is explicit per game/domain; a current assessment is unique by `(game, domain)` and has an assessment time and provenance. Historical assessments are retained by 0.0-E policy. | Unique key/domain validation. |
| M-04 | Player PA coverage and game HR-event coverage are independent; neither is inferred from game finality alone. | Domain validation/test. |
| M-05 | A matrix cell shows `KNOWN_ZERO` only with complete required coverage and ≥1 player PA; DNP, zero PA, not-with-team, unknown and incomplete retain distinct states. | API/UI acceptance test. |
| M-06 | A final regular-season game with incomplete required coverage stays in a selected team-game window; it cannot be skipped and replaced by an older complete game. The affected KPI is nonnumeric. | Window/analytics test. |

## External-ID and provenance invariants

| ID | Rule | Candidate enforcement |
| --- | --- | --- |
| X-01 | Active `(provider, entity_kind, external_value)` identifies at most one canonical entity. Provider namespace and kind are part of identity. | Conditional unique key. |
| X-02 | An external ID may be superseded, but its prior mapping and source record are retained for reconciliation. Ambiguous mappings are flagged, never auto-merged by value alone. | Ingestion/audit validation. |
| X-03 | `ExternalIdentifier` and `FactSourceLink` typed targets must resolve to an existing entity of the declared kind; unsupported kinds are rejected. | Domain/ingestion validation. |
| X-04 | Every source record reference identifies its provider and retrieval time; stable source keys are unique within their verified provider namespace when available. | FK/conditional unique key. |
| X-05 | A source record is evidence, not category authority. Multiple supporting/conflicting links may exist until 0.0-D decides reconciliation. | Domain/review rule. |
| X-06 | Correcting a canonical observation retains evidence of prior source records and correction through the 0.0-E update design; no silent hard deletion of sports history. | Ingestion audit test. |

## Scenario validation against the conceptual model

| # | Scenario | Result | Structural reason |
| --- | --- | --- | --- |
| 1 | Team A → Team B trade, HR for both | PASS | Affiliation intervals plus represented team on participation/PA preserve both histories. |
| 2 | Same-day doubleheader | PASS | Two `Game.id` values; date/number are not identity. |
| 3 | Postponed game | PASS | Lifecycle/status and incomplete coverage prevent a false zero-HR observation. |
| 4 | Game starts then finishes another day | PASS | One game with separate official date, start/completion and lifecycle events. |
| 5 | Rostered player does not appear | PASS | Affirmative `DID_NOT_APPEAR`; absence of row stays unassessed. |
| 6 | Pinch hitter walks, no AB | PASS | `APPEARED` plus one PA; AB is not required for PA identity. |
| 7 | Pinch runner, zero PA | PASS | `APPEARED`, complete PA coverage and zero PA rows. |
| 8 | Two HR in one game | PASS | Two PAs and two HR events linked to one game. |
| 9 | Future Statcast enrichment | PASS | Tracking layer can link to PA/HR event without adding tracking columns to core HR. |
| 10 | MLB/Statcast disagree | PASS | Both source references and conflicting fact links survive reconciliation. |
| 11 | Incomplete event import | PASS | Coverage `PARTIAL/UNKNOWN` blocks interpreting absent HR events as zero. |
| 12 | League/Team A/Team B/full-season query | PASS | Stable player, temporal affiliation, game-specific team and scoped events support each view; window rules are in `WINDOW_SEMANTICS.md`. |

**PASS means structurally representable**, not that provider behavior, KPI rules or implementation has been verified.
