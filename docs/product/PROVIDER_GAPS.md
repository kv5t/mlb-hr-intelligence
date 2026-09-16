# Provider gaps and feasibility gate — Phase 0.0-D

`GAP` = no adequate source proof for required behavior; `UNVERIFIED` = capability may exist but not checked; `PROVISIONAL` = sampled behavior awaiting broader validation. Evidence IDs are in [PROVIDER_EVIDENCE.md](PROVIDER_EVIDENCE.md).

| ID | State; severity | Affected field/KPI/screen | MVP blocker? | Evidence / next action | Owner |
| --- | --- | --- | --- | --- | --- |
| G01 | UNVERIFIED; low | Season.status | No | Verify season state field or leave nullable; never derive analytical eligibility from it. E08. | 0.0-E |
| G02 | PROVISIONAL; medium | Team abbreviation/league/division/history, franchise identity | No | Sample first-party team responses across relocation/name history; preserve stable IDs and game snapshot names. | 0.0-E |
| G03 | GAP; high | Affiliation interval dates, matrix `NOT_WITH_TEAM` | **Yes for complete matrix semantics** | Locate dated transactions/roster snapshots and validate effective boundaries; otherwise show `UNKNOWN`, not DNP or not-with-team. E08. | 0.0-E |
| G04 | GAP; low | Game.completed_at_utc, lifecycle events | No if nullable | Find explicit completion time or leave null; ingest successive snapshots for status transitions. E05/E07. | 0.0-E |
| G05 | GAP; critical | `DID_NOT_APPEAR`, team matrix DNP cell | **Yes for promised DNP cell** | Establish affirmative assessed population and nonappearance from game roster/boxscore/action evidence across normal games; absence from batting table is insufficient. If impossible, replace DNP with `UNKNOWN` and revise product cell promise. E07. | 0.0-E/product |
| G06 | PROVISIONAL; critical | PA completeness, HR known zeros, HR/PA, all recurrence KPIs | **Yes until coverage gate is designed/validated** | Explain 76 plays vs 75 reported PA for game 746656, classify non-PA play, test game/boxscore/event reconciliation, validate known-zero fixtures. E06. | 0.0-E |
| G07 | UNVERIFIED; medium | Actual switch-hitter event side, pinch runner/defensive replacement, ordinary trade | No for core HR counts; yes for exact context/cells if claimed | Sample targeted real games and substitution actions. E07/E10 show candidate fields but not all cases. | 0.0-E |
| G08 | UNVERIFIED; medium | Same-day order, window cutoff | Yes where tied N boundary occurs | Validate `gameNumber`, schedule/actual times for more doubleheader types; return `ORDER_UNVERIFIED` if unresolved. E05. | 0.0-E |
| G09 | PROVISIONAL; high | General MLB/Statcast PA linkage, 0.2 tracking | No for 0.1 | E17 matches five HR rows in one game with `at_bat_number=atBatIndex+1`; test additional games and non-HR PAs before universalizing; retain unmatched rows. | 0.2 design |
| G10 | UNVERIFIED; medium | Park factor export/history, field dimensions/heights, actual roof state | No | Verify first-party table download, temporal granularity and physical metadata; do not infer game roof from roof capability. E02/E12. | 0.3 design |
| G11 | GAP; high | Multi-season historical training weather | No for 0.1 | Price/licensing and sampling study for historical hourly weather; WeatherAPI Starter is seven-day history, Open-Meteo historical is model-derived. E13/E14. | 0.3/0.4 |
| G12 | GAP; critical | Production storage, redistribution and commercial release | **Yes before launch** | Obtain legal/terms review or licensed access for MLB/Savant data; public HTTP 200 is not a reuse grant. E16. | Product/legal before 0.1 launch |
| G13 | UNVERIFIED; medium | Provider cadence, rate limits, support/SLA | No for research; operational gate | Verify published terms/support or agree conservative usage plan; do not invent unlimited quota. | 0.0-E |
| G14 | PROVISIONAL; medium | WeatherAPI/Open-Meteo live forecast and historical payload mapping | No for 0.1 | Test authenticated/allowed small weather response, timezone/site proximity and archived-forecast semantics before 0.3. E13/E14. | 0.3 design |

**Gate decision:** 0.0-D research documents the blockers; it does not claim 0.1 is implementable without them. The next task is 0.0-E ingestion, backfill, sync, coverage and reconciliation architecture, with G03/G05/G06/G12 explicit launch gates. Do not start 0.0-E automatically.
