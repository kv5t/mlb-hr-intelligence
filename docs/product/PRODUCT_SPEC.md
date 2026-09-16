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
4. **Do not invent precision.** Surface denominators, sample size, missing data, provisional status, and uncertainty where relevant. Statistical definitions remain open until 0.0-C.
5. **One analytics definition across outputs.** React, DRF, CSV, and PDF consume the same canonical analytics layer; a report must not silently recompute a KPI differently.
6. **Keep providers at the boundary.** Provider adapters normalize and validate into canonical domain data. Preserve external IDs for traceability; provider field names do not dictate domain models. Exact fields belong to 0.0-B and mappings and authority to 0.0-D.
7. **Descriptive before predictive.** No arbitrary scores, Elo-like HR ratings, or probability claims in 0.1. Models need historical validation, calibration, sample-size and uncertainty communication in 0.4.
8. **Core analytics stand alone.** Social embeds are auxiliary and cannot block core screens, analytics APIs, or exports.

## Information architecture and primary workflows

Desktop primary navigation: **Today, League, Teams, Players, Games, Matchup, Explore**. Social is secondary. Mobile primary navigation: **Today, League, Teams, Players, More**, with Games, Matchup, Explore, and Social under More. Navigation entries for unshipped phases should be absent or clearly marked unavailable; they must not imply working analytics.

| Workflow | Entry → result | First available |
| --- | --- | --- |
| Discover HR leaders | League leaderboard → player/team → underlying games and HR log | 0.1 |
| Compare recurrence | League recurrence view → team matrix → cell/game/event | 0.1; exact cell semantics pending 0.0-B/C |
| Inspect a player | Search/list → player overview → recurrence and HR log | 0.1 |
| Follow today's games | Today → game detail → HR events | 0.1 |
| Export a period | League/team/player view → CSV or panoramic PDF using shared metrics | 0.1 |
| Analyze contact | Player Statcast/pitch views and Explore → observed tracking data | 0.2 |
| Analyze matchup | Batter + pitcher → splits, arsenal, park, weather, evidence | 0.3 |
| Interpret a model | Matchup intelligence → inputs, validation, probability, uncertainty | 0.4 |

The full screen inventory, routes, responsive behavior, and loading/partial/error states are in [SCREEN_MAP.md](SCREEN_MAP.md).

## Scope and boundaries

**0.1 HR Recurrence** covers seasons, all 30 franchises, players, schedule and completed games, HR events, PA where required, leaderboards, team/player/game pages, recurrence matrix and HR logs, 7G/15G/30G/60G/Season selections, CSV and PDF. Today is a simple daily overview. KPI candidates include HR, PA, HR/PA, PA/HR, HR/Game where meaningful, games with HR %, multi-HR games, gaps, droughts, and streaks. Their final definitions are reserved for 0.0-C.

**Later:** 0.2 adds Statcast/contact and pitch analysis; 0.3 adds contextual Matchup Lab, park and weather; 0.4 adds explainable, validated ratings and probabilities. 1.0 covers production readiness. Elo is not presumed appropriate for rare HR events.

**0.1 non-goals:** advanced Statcast, exit velocity and barrel analysis, pitch velocity, park factor intelligence, weather analytics, Matchup Lab calculations, Elo, Power Rating, Matchup Index, HR probability, and machine learning. Phase 0.0-A creates documentation only.

## Traceability and provider strategy

Planned flow: external provider → adapter → normalization/validation → canonical domain data → analytics/aggregation → DRF → React, PDF, CSV. MLB Stats API is the **planned** core source for schedule, games, players, teams, PA and HR events. Baseball Savant/Statcast is the **planned** advanced tracking source, potentially accessed through tooling behind our adapter. A weather provider is deferred to 0.0-D selection; weather becomes relevant in 0.3. Park-factor availability and provenance also require verification. No endpoint, field, coverage, licensing, or provider authority has been verified in 0.0-A.

The intended drill-down is player → matrix cell → game → plate appearance → HR event → source. Later a reconciled Statcast event can attach to an HR event. Missing or conflicting provider data must be visible as incomplete/provisional rather than silently substituted; the exact authority and reconciliation rules are open for 0.0-D.

## Responsive and accessible behavior

Desktop supports dense tables and a horizontally scrolling matrix with sticky identity/summary columns and roughly 30 reachable game columns. Tablet starts with a shorter window and preserves all columns through scrolling. Mobile starts with a small window, retains player identity, uses touch-friendly cells and filter sheets, and allows the full dataset through navigation or export. The A3 landscape PDF is a panoramic static output; the website remains interactive. Virtualization may be used where scale justifies it.

Cells carry numeric or textual meaning, never color alone. Use semantic tables where suitable, keyboard navigation, visible focus, screen-reader labels that identify player/game/value, sufficient contrast, browser zoom, responsive text, reduced motion, and adequate touch targets. Positive cells lead to game/event detail when available. DNP, zero PA, postponements, suspended games, and appearances require definitions before final cell semantics.

## Export concept

CSV and PDF are planned for 0.1. PDF may use A3 landscape with period/team header, KPI cards, recurrence matrix, legend, and descriptive analysis. Both export formats include the selected window, metric labels, and provenance/freshness where available. Exporting must use the same canonical definitions as the web view. No report generation is part of 0.0-A.

## Open questions and ownership

The structural aspects of Q02, Q05-06, Q08-11, Q13, Q15 and Q18-19 are addressed in [DATA_MODEL.md](DATA_MODEL.md). The questions below retain their unresolved calculation, product inclusion or provider-mapping aspects. Product displays should use honest neutral labels or defer a metric until its meaning is fixed.

| ID | Question | Phase |
| --- | --- | --- |
| Q01 | Is HR gap the count of completed relevant games between HR games, or the difference in HR-game indices? | 0.0-C |
| Q02 | A multi-HR game has multiple HR events structurally; does it count as one recurrence occurrence? | 0.0-C |
| Q03 | Is a player's 30G window based on team games, appearances, games with PA, or another set? | 0.0-C |
| Q04 | Does a team game without player appearance extend that player's drought? | 0.0-C |
| Q05 | How does a structurally represented pinch-hit-only appearance enter each KPI/window? | 0.0-C; source mapping 0.0-D |
| Q06 | How does an explicitly represented zero-PA appearance enter each KPI/window? | 0.0-C; source mapping 0.0-D |
| Q07 | Are current droughts expressed in games, PA, or both? | 0.0-C |
| Q08 | Distinct doubleheader games are modeled; what is matrix/window ordering? | 0.0-C; source mapping 0.0-D |
| Q09 | Postponement is modeled; how does it affect schedules/windows and source identity? | 0.0-C/D |
| Q10 | One suspended/resumed contest is representable; what official-date/window rules and provider identity behavior apply? | 0.0-C/D |
| Q11 | Affiliation and event team are historical; how do traded players enter team windows? | 0.0-C; source precision 0.0-D |
| Q12 | Do league player windows follow appearances or team schedules? | 0.0-C |
| Q13 | Player profile side and event-used side are distinct; how does the provider supply/map actual side? | 0.0-D |
| Q14 | Which minimum sample-size indicators appear for each KPI/split? | 0.0-C |
| Q15 | Explicit unknown/coverage states exist; what provider evidence sets them, and how does UI label partial coverage? | 0.0-D; UI contract 0.0-F/G |
| Q16 | How are MLB/Statcast disagreements or unmatched events reconciled? | 0.0-D |
| Q17 | Which provider is authoritative for each category, and what are coverage, latency, licensing and limits? | 0.0-D |
| Q18 | Game types are structurally distinct; which enter product analytics (regular season, postseason, spring training, All-Star, other)? | 0.0-C scope; 0.0-D mapping |
| Q19 | Official date, UTC starts/completion and venue timezone are distinct; which determines windows/display and how does provider data map? | 0.0-C window rules; 0.0-D mapping |

See [GLOSSARY.md](GLOSSARY.md) for provisional terminology and [ROADMAP.md](ROADMAP.md) for gates.
