# Provider strategy — Phase 0.0-D

**Status: BLOCKED for unconditional 0.1 launch.** The sampled MLB public responses support game identity, schedule, event-level PA/HR representation and many metadata fields. They do **not yet prove** reliable affirmative `DID_NOT_APPEAR`, complete PA/HR coverage for every game, historical affiliation boundaries, or production reuse rights. G03/G05 reduce matrix fidelity to `UNKNOWN` where necessary; G06 blocks numeric analytics without completeness; G12 blocks automated production access. Source details: [evidence](PROVIDER_EVIDENCE.md), [field mapping](PROVIDER_FIELD_MAPPING.md), [gaps](PROVIDER_GAPS.md).

## Authority by category

| Canonical category | Primary | Secondary / enrichment / fallback | Feasibility |
| --- | --- | --- | --- |
| Season, Team, Player, Venue | MLB observed season/team/people/game-feed resources | No independent fallback selected | VERIFIED_WITH_LIMITATIONS: historical names, franchise identity, venue sparsity |
| Game identity, schedule, scores | MLB schedule `gamePk` | MLB game feed for current contest details | VERIFIED_WITH_LIMITATIONS: schedule changes need snapshots |
| Game status/finality | MLB detailed status plus game feed and lifecycle evidence | None | PROVISIONAL: `abstractGameState=Final` can label a postponed game |
| Player affiliation | Game-specific MLB boxscore/PA team for event attribution | Season roster for contextual association only | GAP for exact interval boundaries and not-with-team certainty |
| Participation | MLB boxscore plus plays/actions | None | VERIFIED_WITH_LIMITATIONS for APPEARED; GAP for reliable DID_NOT_APPEAR |
| PA, HR event | MLB play-by-play `allPlays`, reconciled with boxscore | Statcast may corroborate HR/PA later, never replace missing core PA | VERIFIED_WITH_LIMITATIONS; one sampled 76/75 mismatch |
| Batter/pitcher handedness | MLB profile and event matchup separately | Statcast `stand`/`p_throws` enrichment | VERIFIED_WITH_LIMITATIONS; switch-hitter sample pending |
| Statcast tracking | Baseball Savant CSV/search | pybaseball optional transport wrapper, not authority | VERIFIED_WITH_LIMITATIONS 0.2; one-game five-HR row linkage E17, broader linkage provisional |
| Park factor | Baseball Savant park-factor page | None | VERIFIED_WITH_LIMITATIONS 0.3; 100 baseline, season/handedness views |
| Physical park metadata | MLB hydrated venue game feed | No verified historical fallback | PROVISIONAL 0.3; roof capability, azimuth, elevation, fence distances observed, not game-specific roof state |
| Historical game weather | MLB game feed weather as coarse source observation | WeatherAPI paid history / Open-Meteo model history | PROVISIONAL; observations versus archived forecast/reanalysis differ |
| Forecast weather | WeatherAPI keyed forecast | Open-Meteo commercial plan if licensed | PROVISIONAL 0.3; no authenticated sample |

`PRIMARY` means normalization preference within a category, not universal correctness. Conflicts retain both sources. No first-party Stats API developer contract/support page was located; direct public JSON availability is not an official service guarantee.

## Critical decisions

1. **MVP 0.1:** MLB core is a plausible source for contest, player, PA, HR and scores, but fully populated DNP/NOT_WITH_TEAM matrix states are limited by DNP and affiliation evidence; coverage G06 blocks affected numeric analytics. Product can show `UNKNOWN` cells where evidence is insufficient, yet a fully populated reliable DNP/not-with-team matrix cannot be claimed. 0.0-E defines assessments in [COVERAGE_POLICY.md](COVERAGE_POLICY.md) and fixtures in [INGESTION_TEST_CASES.md](INGESTION_TEST_CASES.md); implementation validation remains open.
2. **PA and HR:** `allPlays[]` at-bat play objects include walks and HBP and expose `atBatIndex`; `result.eventType=home_run` maps to that play. Sampled HR events map 1:1 to PAs. A 76-play/75-boxscore-PA sample prevents declaring universal completeness from raw play count alone.
3. **Lifecycle:** `gamePk` stayed stable in sampled reschedule and suspension. Doubleheader contests had distinct IDs and game numbers. Original official date stayed on a suspended contest; resumed date appeared separately. Ingestion snapshots are needed to preserve prior schedule states. These examples do not prove every historical edge case.
4. **Identity:** The same player can represent both teams in one resumed contest. Participation key is `(game, player, team)`; one unfiltered player batting-game counts that contest once if any qualifying PA. Team-filtered values use PAs attributed to represented team. Verified MLB IDs are high-frequency lookup columns alongside generic aliases; internal UUIDs remain canonical PKs.
5. **Team versus franchise:** Sampled MLB team IDs and game team attribution support a stable Team for MVP. Historical name changes and franchise relocation metadata are not yet verified; do not split Franchise/SeasonTeam solely on this sample. Preserve ID and historical game snapshot labels; revisit on contradictory evidence.

## Provider terms, access and budget

| Provider | Access/auth | Published price/limit evidence | Production status |
| --- | --- | --- | --- |
| MLB Stats API direct public responses | No credential used for sampled HTTP 200 JSON. No formal support/rate-limit promise located. | No official API price or rate limit verified. Absence of a limit is **not** unlimited use. | **LEGAL/TERMS REVIEW REQUIRED** for data storage, publication, redistribution and commercial use; [MLB terms](https://www.mlb.com/official-information/terms-of-use). |
| Baseball Savant CSV/search and park factors | First-party web/download surfaces; no credential used for page reading. | No production rate limit or licensing grant verified. | **LEGAL/TERMS REVIEW REQUIRED**; row-level downloads and redistribution require review. |
| pybaseball | Open-source wrapper; provider conditions still apply. | Package price does not grant provider data rights. | Optional convenience only; direct provider schema is preferred for authoritative adapter/reconciliation. |
| WeatherAPI | API key required. | [Pricing](https://www.weatherapi.com/pricing.aspx): Free $0, 100K/month and 1 historical day; Starter $7/month, 3M/month and 7 historical days; Pro+ $25/month and 365 days; Business $65/month and history since 2010. Verify checkout/current plan before purchase. | Forecast/current use plausible within ~$10/month; historical training beyond one week is **not** within Starter. [Terms](https://www.weatherapi.com/terms.aspx) require Free attribution; storage/redistribution review. Historical product says archived forecasts, not necessarily actual observations. |
| Open-Meteo | Free/Open-Access endpoint for evaluation/noncommercial use; commercial access requires subscription/customer endpoint. | [Pricing](https://open-meteo.com/en/pricing) and [historical docs](https://open-meteo.com/en/docs/historical-weather-api) describe hourly modeled/reanalysis history since 1940. Commercial Historical Weather API requires Professional or higher per E19; plan/price fit requires selection. | Credible historical alternative but free use is not a general commercial license; station/ballpark representativeness needs validation. |

**Future weather split:** live/future matchup conditions need forecasts at a venue/time. Model training needs historical hourly observations or defensible reanalysis across many seasons. MLB weather is coarse recorded game context; WeatherAPI Starter history horizon is too short for multi-season training. No historical provider is selected for production modeling yet.

## 0.0-E architecture handoff

The 0.0-E documents now specify snapshotting, idempotent gamePk reconciliation, PA/boxscore exceptions, participation and coverage proof, backfill/correction cadence and the external access gate. Implementation validation remains open. `Final`, an empty HR list and HTTP success are never completeness proofs. No production integration was added.

## 0.0-D quality gate audit

`PASS` means the research/specification criterion was documented, not that the underlying provider capability or 0.1 launch is ready. `BLOCKED` marks an unresolved capability or external approval. The source checklist is evaluated item by item.

| # | Criterion | Result / evidence |
| --- | --- | --- |
| 1 | 0.0-C closeout corrections applied | PASS: KPI, window, tests, product, roadmap, screen, glossary, ADRs updated. |
| 2 | Current game drought/streak not truncated by N | PASS: KPI_SPEC and synthetic 41/30, 10/7 cases. |
| 3 | Current PA drought cutoff-state | PASS: KPI_SPEC and 45/29 case. |
| 4 | Same-day unresolved order invalidates boundary membership | PASS: WINDOW_SEMANTICS and N=1 test. |
| 5 | Unknown official date invalidates possible cutoff membership | PASS: WINDOW_SEMANTICS and test. |
| 6 | Uncertain player membership has no definitive actual count | PASS: WINDOW_SEMANTICS and test. |
| 7 | Stale wording cleaned | PASS: PRODUCT_SPEC, ROADMAP, SCREEN_MAP, DATA_MODEL, DECISIONS. |
| 8 | Every MVP entity evidenced or gap | PASS: PROVIDER_FIELD_MAPPING. |
| 9 | Every 0.1 field mapped or marked unavailable | PASS: field mapping, 103 primary rows plus provenance. |
| 10 | Undocumented endpoint not called official | PASS: direct observation label E01–E09. |
| 11 | No invented rate limit | PASS: unknown limits explicitly stated. |
| 12 | Pricing verified against current page | PASS: E13/E14, verification date. |
| 13 | Terms/support status documented | PASS: E13–E16, legal gate G12. |
| 14 | MLB game identity verified | PASS: gamePk E01/E05/E07. |
| 15 | Doubleheader verified or unresolved | PASS: E05, ordering caveat G08. |
| 16 | Reschedule behavior verified or unresolved | PASS: E05, snapshot caveat. |
| 17 | Suspension behavior verified or unresolved | PASS: E07, one-contest model and two-team exception. |
| 18 | PA representation verified | PASS WITH LIMITATION: E02/E06; completeness G06. |
| 19 | HR representation verified | PASS WITH LIMITATION: E02–E04; full coverage G06. |
| 20 | Participation evidence verified | PASS WITH LIMITATION: APPEARED E07, DNP G05. |
| 21 | DNP feasibility explicitly answered | PASS: not reliable yet, G05. |
| 22 | Zero-PA feasibility explicitly answered | PASS WITH LIMITATION: E07 Jansen example, routine cases G07. |
| 23 | Switch-hitter event side explicitly answered | PASS WITH LIMITATION: field observed, actual switch case G07. |
| 24 | Coverage evidence documented | PASS: E02–E07 and G06; no automatic COMPLETE. |
| 25 | FINAL not automatic completeness | PASS: KPI and reconciliation policy. |
| 26 | MLB/Statcast linkage tested | PASS WITH LIMITATION: five HR rows in one paired game match, E17; broader sample G09. |
| 27 | Statcast fields from current evidence | PASS: first-party CSV schema E10. |
| 28 | pybaseball tooling, not authority | PASS: E15. |
| 29 | Park factors verified | PASS WITH LIMITATION: first-party page E12; export/history G10. |
| 30 | Weather price/coverage/terms verified | PASS WITH LIMITATION: first-party pages E13/E14; live payload G14. |
| 31 | Historical vs forecast distinguished | PASS: weather split above. |
| 32 | Authority per category | PASS: matrix above. |
| 33 | Reconciliation retains conflicts/unmatched | PASS: RECONCILIATION_POLICY. |
| 34 | Every gap has owner/severity/blocker | PASS: PROVIDER_GAPS. |
| 35 | No production integration code | PASS: Markdown documentation only. |

**Phase result: BLOCKED** under the user’s gate because G06 and G12 are hard 0.1 gates; G03/G05 are feature-fidelity degradations. The research and documents are complete enough to hand these explicit decisions to 0.0-E, but this is not a green light for implementation or release.

**0.0-E access gate:** `PROVIDER_ACCESS_APPROVED` must be externally recorded before any automated production or season backfill use. Public HTTP success is not that approval.
