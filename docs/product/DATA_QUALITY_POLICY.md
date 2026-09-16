# Data quality, quarantine and publication — Phase 0.0-E

A data-quality issue is an auditable claim about a provider target, canonical candidate or coverage domain. It has stable code, severity, affected scope, evidence/source refs, opened/last-seen/resolved times, status and operator resolution. A quarantine record retains the rejected candidate, reason and replay pointer. Neither is a substitute for raw evidence.

| Severity | Meaning | Publication and coverage effect |
| --- | --- | --- |
| INFO | Expected classified exception or metadata note (e.g., E18 non-PA play). | Publish if all other checks pass. |
| WARNING | Limited context or optional metadata gap. | Publish unaffected core facts; mark dependent context unknown. |
| ERROR | Deterministic mismatch affecting a fact/domain, possibly local to one player or game. | Quarantine affected claim; preserve prior facts; affected domain cannot be COMPLETE until resolved. |
| BLOCKING | Ambiguous identity, missing/contradictory PA/HR proof, access denial for automation, or an invariant that can corrupt published analytics. | No affected canonical candidate publication; numeric dependent KPIs blocked; issue visible to operator. Access denial blocks fetch globally for that provider scope. |

Examples: `AMBIGUOUS_GAME_ID`, `DUPLICATE_PROVIDER_ID`, `DUPLICATE_ATBAT_INDEX`, `UNMATCHED_PA`, `HR_WITHOUT_PA`, `INVALID_HOME_AWAY`, `TEAM_ATTRIBUTION_CONFLICT`, `UNSUPPORTED_STATUS`, `SCHEMA_DRIFT`, `BOX_SCORE_PA_MISMATCH`, `BOX_SCORE_HR_MISMATCH`, `ACCESS_NOT_APPROVED`. Unknown provider fields are retained in raw evidence; disappearance of a required field raises `SCHEMA_DRIFT`, not default zero. Issue fingerprint `(code,provider,target,domain,source-claim key)` prevents endless duplicates while recording recurrence.

An unresolved source claim stays inspectable but is not promoted to a canonical fact. Identity ambiguity stops the game transaction. A local player PA discrepancy may be quarantined while preserving unaffected prior game state; game-wide PA/HR coverage remains PARTIAL/UNKNOWN, so no affected numeric full-game recurrence result is published. Positive APPEARED evidence can be retained even if DNP population is unknown. DNP or NOT_WITH_TEAM is never inferred from absence. A new contradiction can downgrade coverage of previously published facts, with a new revision and invalidation.

Operator resolution requires evidence references, reason, chosen mapping/rule version, actor and time. Supported actions are retry transient failure, reprocess immutable snapshot, reassess coverage, accept source correction, or resolve documented ambiguity. Manual overriding of provider-owned MLB HR/PA facts without source-backed correction is not a routine admin action. Later Django Admin should display SyncRun/items, snapshot metadata/checksum, coverage/current and history, issues, quarantine, source links and revision history; write actions should be explicit audited workflows, not direct row edits.

## Observability contract

Track per provider/run: attempted/succeeded/partial/blocked targets; games discovered/updated; raw snapshots new/deduplicated; source bytes; PAs and HRs proposed/accepted/quarantined; coverage states by domain; open/resolved issues by severity/code; conflicts; 429/5xx/timeouts, retry count, request/processing duration, last successful sync and data freshness; lease contention/stale recovery; dataset revision and invalidation lag. Logs correlate run/item/snapshot/game/revision IDs and stage transitions, redact credentials and avoid raw payloads. Alert on blocked access, repeated schema drift, sustained incomplete coverage, stuck lease, or invalidation backlog. A dashboard must distinguish source freshness from analytics readiness.
