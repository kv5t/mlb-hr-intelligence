# MLB HR Intelligence — Product specification

**Status:** Canonical product scope for Phase 0.0-A. This document defines product behavior and boundaries, not data schemas, formulas, verified provider capabilities, or implementation contracts.

## Mission and problem

Turn a static home-run recurrence report into a responsive, traceable MLB analytics product. A season HR total describes production but does not show how regularly a hitter homers, whether HR games cluster, or the length of current and historical gaps. Fans and analysts need to compare those patterns, inspect the games behind them, and eventually add contact quality and matchup context without confusing an observed fact with a prediction.

The original manually generated PDF is a **UX reference only**. Its example statistics are not production data. Production facts must come from validated providers or reproducible calculations over canonical stored data.

## Questions the product answers

- **0.1, descriptive:** Who has the most HR? Who has HR in the largest share of relevant games? Who has the shortest median HR gap, a current drought, a streak, or clustered multi-HR games? Which games and HR events support a displayed count?
- **0.2, contact quality:** Which hitters have strong recent tracked contact, and how do pitch type, pitch velocity, and handedness splits change the observed profile?
- **0.3, matchup context:** Which observed batter, pitcher, park and weather factors characterize the matchup, and how do they compare with historical outcomes?
- **0.4, validated models:** What is an estimated HR probability, what inputs explain it, and how well was it calibrated on held-out historical data?

## Product principles

1. **Production and recurrence are separate.** HR, HR/Game, HR/PA, and PA/HR describe production or rate. HR-game frequency, gaps, droughts, and streaks describe recurrence. HR/Game must never be labeled recurrence.
2. **Show evidence.** Every displayed HR should eventually trace from player and matrix cell to game, HR event, and provider source. Derived KPIs must be reproducible. Show data provenance and freshness when available.
3. **Label knowledge type.** Distinguish observed statistics, derived metrics, context, and model outputs in labels and visual treatment. A rating or probability is never presented as an observed statistic.
4. **Do not invent precision.** Surface denominators, sample size, missing data, provisional status, and uncertainty where relevant. Statistical definitions are in [KPI_SPEC.md](KPI_SPEC.md) and [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md).
5. **One analytics definition across outputs.** React, DRF, CSV, and PDF consume the same canonical analytics layer; a report must not silently recompute a KPI differently.
6. **Keep providers at the boundary.** Provider adapters normalize and validate into canonical domain data. Preserve external IDs for traceability; provider field names do not dictate domain models. Exact fields belong to 0.0-B and mappings and authority to 0.0-D.
7. **Descriptive before predictive.** No arbitrary scores, Elo-like HR ratings, or probability claims in 0.1. Models need historical validation, calibration, sample-size and uncertainty communication in 0.4.
8. **Core analytics stand alone.** Social embeds are auxiliary and cannot block core screens, analytics APIs, or exports.

## Information architecture and primary workflows

Desktop primary navigation: **Today, League, Teams, Players, Games, Matchup, Explore**. Social is secondary. Mobile primary navigation: **Today, League, Teams, Players, More**, with Games, Matchup, Explore, and Social under More. Navigation entries for unshipped phases should be absent or clearly marked unavailable; they must not imply working analytics.

| Workflow | Entry → result | First available |
| --- | --- | --- |
| Discover HR leaders | League leaderboard → player/team → underlying games and HR log | 0.1 |
| Compare recurrence | League recurrence view → team matrix → cell/game/event | 0.1; cell semantics in [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md) |
| Inspect a player | Search/list → player overview → recurrence and HR log | 0.1 |
| Follow today's games | Today → game detail → HR events | 0.1 |
| Export a period | League/team/player view → CSV or panoramic PDF using shared metrics | 0.1 |
| Analyze contact | Player Statcast/pitch views and Explore → observed tracking data | 0.2 |
| Analyze matchup | Batter + pitcher → splits, arsenal, park, weather, evidence | 0.3 |
| Interpret a model | Matchup intelligence → inputs, validation, probability, uncertainty | 0.4 |

The full screen inventory, routes, responsive behavior, and loading/partial/error states are in [SCREEN_MAP.md](SCREEN_MAP.md).

## Scope and boundaries

**0.1 HR Recurrence** covers seasons, all 30 franchises, players, schedule and completed games, HR events, PA where required, leaderboards, team/player/game pages, recurrence matrix and HR logs, 7G/15G/30G/60G/Season selections, CSV and PDF. Today is a simple daily overview. MVP analytical scope is regular-season games. HR, PA, HR/PA, PA/HR, HR/Game, Games With HR %, multi-HR games, gaps, droughts and streaks are defined in [KPI_SPEC.md](KPI_SPEC.md) and [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md).

**Later:** 0.2 adds Statcast/contact and pitch analysis; 0.3 adds contextual Matchup Lab, park and weather; 0.4 adds explainable, validated ratings and probabilities. 1.0 covers production readiness. Elo is not presumed appropriate for rare HR events.

**0.1 non-goals:** advanced Statcast, exit velocity and barrel analysis, pitch velocity, park factor intelligence, weather analytics, Matchup Lab calculations, Elo, Power Rating, Matchup Index, HR probability, and machine learning. Phase 0.0-A creates documentation only.

## Traceability and provider strategy

Planned flow: external provider → adapter → normalization/validation → canonical domain data → analytics/aggregation → DRF → React, PDF, CSV. MLB Stats API is the **planned** core source for schedule, games, players, teams, PA and HR events. Baseball Savant/Statcast is the **planned** advanced tracking source, potentially accessed through tooling behind our adapter. A weather provider is deferred to 0.0-D selection; weather becomes relevant in 0.3. Park-factor availability and provenance also require verification. No endpoint, field, coverage, licensing, or provider authority has been verified in 0.0-A.

The intended drill-down is player → matrix cell → game → plate appearance → HR event → source. Later a reconciled Statcast event can attach to an HR event. Missing or conflicting provider data must be visible as incomplete/provisional rather than silently substituted; the exact authority and reconciliation rules are open for 0.0-D.

## Responsive and accessible behavior

Desktop supports dense tables and a horizontally scrolling matrix with sticky identity/summary columns and roughly 30 reachable game columns. Tablet starts with a shorter window and preserves all columns through scrolling. Mobile starts with a small window, retains player identity, uses touch-friendly cells and filter sheets, and allows the full dataset through navigation or export. The A3 landscape PDF is a panoramic static output; the website remains interactive. Virtualization may be used where scale justifies it.

Cells carry numeric or textual meaning, never color alone. Use semantic tables where suitable, keyboard navigation, visible focus, screen-reader labels that identify player/game/value, sufficient contrast, browser zoom, responsive text, reduced motion, and adequate touch targets. Positive cells lead to game/event detail when available. DNP, zero PA, postponements, suspended games and appearances follow [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md); provider evidence limits are in [PROVIDER_GAPS.md](PROVIDER_GAPS.md).

## Export concept

CSV and PDF are planned for 0.1. PDF may use A3 landscape with period/team header, KPI cards, recurrence matrix, legend, and descriptive analysis. Both export formats include the selected window, metric labels, and provenance/freshness where available. Exporting must use the same canonical definitions as the web view. No report generation is part of 0.0-A.

## Question closeout and remaining ownership

Q01–Q12, Q14 and the product/metric portions of Q18–Q19 are resolved by [KPI_SPEC.md](KPI_SPEC.md) and [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md): HR gap counts intervening non-HR batting/team games; a multi-HR game is one recurrence game; player rolling windows use batting games; team matrix windows use team games; DNP and zero-PA appearances do not advance player batting-game droughts or break streaks; both game and player PA droughts are explicitly labeled. Filters precede last N, regular season is the MVP analytical type, and denominators are displayed. [KPI_TEST_CASES.md](KPI_TEST_CASES.md) supplies synthetic expected results.

| Question | Remaining issue | Owner |
| --- | --- | --- |
| Q05–Q06, Q08–Q11 | Provider evidence for participation/PA, doubleheader ordering, reschedule/suspension identity and affiliation precision. | 0.0-D |
| Q13 | Map actual switch-hitter side at PA level. | 0.0-D |
| Q15 | Determine provider evidence for complete/partial coverage and present it in API/UI. | 0.0-D; 0.0-F/G |
| Q16 | Reconcile MLB and Statcast disagreements/unmatched events. | 0.0-D |
| Q17 | Determine provider authority, coverage, latency, limits and terms by category. | 0.0-D |
| Q18–Q19 | Map provider game types, official dates, UTC instants and venue timezones. | 0.0-D |

See [GLOSSARY.md](GLOSSARY.md) for terminology and [ROADMAP.md](ROADMAP.md) for gates.
