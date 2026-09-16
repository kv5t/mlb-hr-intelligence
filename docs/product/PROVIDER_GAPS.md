# Provider gaps and feasibility gate — Phase 0.0-D

`GAP` = no adequate source proof for required behavior; `UNVERIFIED` = capability may exist but not checked; `PROVISIONAL` = sampled behavior awaiting broader validation. Evidence IDs are in [PROVIDER_EVIDENCE.md](PROVIDER_EVIDENCE.md).

| ID | State; severity | Affected field/KPI/screen | MVP blocker? | Evidence / next action | Owner |
| --- | --- | --- | --- | --- | --- |
| G01 | UNVERIFIED; low | Season.status | No | Verify season state field or leave nullable; never derive analytical eligibility from it. E08. | 0.0-E |
| G02 | PROVISIONAL; medium | Team abbreviation/league/division/history, franchise identity | No | Sample first-party team responses across relocation/name history; preserve stable IDs and game snapshot names. | 0.0-E |
| G03 | GAP; high | Affiliation interval dates, matrix `NOT_WITH_TEAM` | No for core 0.1; FEATURE-FIDELITY for `NOT_WITH_TEAM` | Locate dated transactions/roster snapshots and validate effective boundaries; otherwise show `UNKNOWN`, not DNP or not-with-team. E08. | 0.0-E |
| G04 | GAP; low | Game.completed_at_utc, lifecycle events | No if nullable | Find explicit completion time or leave null; ingest successive snapshots for status transitions. E05/E07. | 0.0-E |
| G05 | GAP; critical | `DID_NOT_APPEAR`, team matrix DNP cell | No for core 0.1; FEATURE-FIDELITY for DNP | Establish affirmative assessed population and nonappearance from game roster/boxscore/action evidence across normal games; absence from batting table is insufficient. If impossible, replace DNP with `UNKNOWN` and revise product cell promise. E07. | 0.0-E/product |
| G06 | PROVISIONAL; critical | PA completeness, HR known zeros, HR/PA, all recurrence KPIs | **Yes: HARD ANALYTICS correctness gate until validated** | E18 explains one non-PA caught-stealing play in game 746656; validate the versioned event classifier, per-batter reconciliation and known-zero fixtures across more games. | 0.0-E |
| G07 | UNVERIFIED; medium | Actual switch-hitter event side, pinch runner/defensive replacement, ordinary trade | No for core HR counts; yes for exact context/cells if claimed | Sample targeted real games and substitution actions. E07/E10 show candidate fields but not all cases. | 0.0-E |
| G08 | UNVERIFIED; medium | Same-day order, window cutoff | Yes where tied N boundary occurs | Validate `gameNumber`, schedule/actual times for more doubleheader types; return `ORDER_UNVERIFIED` if unresolved. E05. | 0.0-E |
| G09 | PROVISIONAL; high | General MLB/Statcast PA linkage, 0.2 tracking | No for 0.1 | E17 matches five HR rows in one game with `at_bat_number=atBatIndex+1`; test additional games and non-HR PAs before universalizing; retain unmatched rows. | 0.2 design |
| G10 | UNVERIFIED; medium | Park factor export/history, field dimensions/heights, actual roof state | No | Verify first-party table download, temporal granularity and physical metadata; do not infer game roof from roof capability. E02/E12. | 0.3 design |
| G11 | GAP; high | Multi-season historical training weather | No for 0.1 | Price/licensing and sampling study for historical hourly weather; WeatherAPI Starter is seven-day history, Open-Meteo historical is model-derived and commercial historical use requires Professional or higher (E19). E13/E14. | 0.3/0.4 |
| G12 | GAP; critical | Production storage, redistribution and commercial release | **Yes: OPEN_EXTERNAL access gate before automation/launch** | Obtain legal/terms review or licensed access for MLB/Savant data; public HTTP 200 is not a reuse grant. E16. | Product/legal before 0.1 launch |
| G13 | UNVERIFIED; medium | Provider cadence, rate limits, support/SLA | No for research; operational gate | Verify published terms/support or agree conservative usage plan; do not invent unlimited quota. | 0.0-E |
| G14 | PROVISIONAL; medium | WeatherAPI/Open-Meteo live forecast and historical payload mapping | No for 0.1 | Test authenticated/allowed small weather response, timezone/site proximity and archived-forecast semantics before 0.3. E13/E14. | 0.3 design |

**0.0-E classification:** The architecture defines safe behavior; it does not turn missing external evidence into resolved provider capabilities. G06 remains an open engineering correctness gate until the event classifier and completeness proof pass implementation validation. G12 remains an external access gate until externally approved. G03/G05 degrade matrix fidelity to UNKNOWN without blocking positively evidenced core HR analytics.

## End-of-0.0-E gap classification

| Gap | Status | Reason / remaining action |
| --- | --- | --- |
| G01 | MITIGATED | Season.status optional and not used for eligibility; verify when available. |
| G02 | OPEN_ENGINEERING | Historical team/franchise metadata sample and temporal names need validation. |
| G03 | DEGRADED_FEATURE | No synthetic affiliation intervals; NOT_WITH_TEAM becomes UNKNOWN absent dated evidence. |
| G04 | MITIGATED | Completion instant remains nullable; lifecycle uses recorded snapshot time separately. |
| G05 | DEGRADED_FEATURE | DNP becomes UNKNOWN absent affirmative assessed population. |
| G06 | OPEN_ENGINEERING | E18 explains one 76/75 case, but classifier, broad event taxonomy and per-batter coverage proof need implementation validation. Hard analytics correctness gate. |
| G07 | OPEN_ENGINEERING | Pinch-runner, defensive-only, switch and trade fixtures need targeted evidence/validation. |
| G08 | MITIGATED | Unresolved tied N boundary returns ORDER_UNVERIFIED, not a number; further source validation optional. |
| G09 | DEFERRED_LATER_PHASE | Statcast cross-game/non-HR linkage belongs to 0.2. |
| G10 | DEFERRED_LATER_PHASE | Park export/history and roof/physical context belong to 0.3. |
| G11 | DEFERRED_LATER_PHASE | Multi-season training weather belongs to 0.3/0.4; E19 clarifies commercial historical plan. |
| G12 | OPEN_EXTERNAL | `PROVIDER_ACCESS_APPROVED` has no external approval evidence; no automated production/backfill use. |
| G13 | OPEN_EXTERNAL | Provider rate/support terms remain unverified; conservative configured limits and disable switch mitigate operations only after access approval. |
| G14 | DEFERRED_LATER_PHASE | Weather payload/provider selection belongs to 0.3. |
