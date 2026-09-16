# Reconciliation policy — Phase 0.0-D

This is a specification; ingestion mechanics belong to 0.0-E. Preserve raw source references, retrieved time, provider field and canonical claim. Never overwrite a conflicting claim without retaining its earlier evidence.

## Identity and matching

1. Core MLB game: exact namespaced `gamePk` → one internal `Game.id`. Same teams/date alone are insufficient: doubleheaders and reschedules collide. If a source reuses or changes a game key unexpectedly, quarantine and retain both records until reviewed.
2. Player/team/venue: exact namespaced MLB IDs map to internal IDs, never to canonical PKs. Verify typed aliases and unique nullable core MLB lookup columns agree. Name matching is a candidate hint, not auto-merge proof.
3. MLB play to canonical PA: `(gamePk, about.atBatIndex)` is preferred within sampled feeds, with batter/pitcher IDs, inning/half and event outcome cross-check. Duplicate/missing ordinal or mismatch is unresolved; do not invent order from ingestion sequence.
4. HR: an MLB `result.eventType=home_run` on a reconciled PA creates one `HomeRunEvent` linked by unique PA FK. A multi-HR player game yields separate PAs/HR rows. Source HR without matched PA remains unresolved and blocks complete HR coverage.
5. Statcast future linkage: documented `game_pk`, MLB `batter`/`pitcher` IDs, `at_bat_number`, `pitch_number` and `events` are candidate keys. In the paired game 746977, five HR rows matched by MLB game/batter/pitcher/outcome and `Statcast.at_bat_number = MLB.about.atBatIndex + 1` (E17). This offset is **verified only for that game**; test other games and non-HR PAs before making it a universal join rule. Match by game + batter + pitcher + candidate PA number + event/inning cross-check; never match by `sv_id` alone (documented non-unique). Collision, missing row or conflicting HR designation stays unmatched and cannot silently modify MLB core. Confidence is high for the five sampled HR matches and provisional for other games/outcomes.

## Authority and publication

| Conflict | Preferred claim | Retention and publication effect |
| --- | --- | --- |
| Schedule vs later MLB schedule/game feed | Latest verified MLB contest snapshot for current display | Keep prior scheduled time/status as lifecycle evidence; ambiguous game identity blocks merge/publication. |
| MLB play vs boxscore PA count | Neither silently wins completeness | Record both counts and discrepancy; PA/HR coverage remains PARTIAL/UNKNOWN pending event-level reconciliation. |
| MLB HR vs Statcast event | MLB core for canonical credited HR; Statcast for tracking enrichment | Preserve both; unmatched/conflicting tracking does not erase a core HR. Inconsistent core HR/PA blocks verified HR publication. |
| MLB profile side vs play side | Profile for `Player.bats/throws`, play matchup for actual event side | Never overwrite profile with single-game side or infer switch-hitter event side from `S`. |
| Roster vs game boxscore/PA team | Game evidence for represented team | Roster supplies contextual affiliation only; unverified date boundary cannot justify DNP/not-with-team. |
| MLB weather vs external weather | Each remains separately typed (recorded game note, forecast, reanalysis) | Do not blend provenance or represent archived forecast as measured stadium weather. |

An unmatched source record remains `UNRESOLVED` with its payload reference and reason. An ambiguous mapping has no published canonical fact until resolved. `UNKNOWN`/`INCOMPLETE` analytic output is preferable to a false zero. Completion requires domain-specific evidence; game `Final` is only one input. A postponed schedule item labeled `abstractGameState=Final` is not treated as completed. Exact thresholds, retry cadence and correction workflow are 0.0-E deliverables.
