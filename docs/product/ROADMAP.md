# MLB HR Intelligence — Roadmap and phase gates

**Status:** Updated through Phase 0.0-E (specification complete). Current phase: 0.0-F; provider access and coverage launch gates remain open. A phase is complete only when its exit criteria are met. Later features are not implicitly authorized by completion of an earlier phase.

## 0.0 — Product and data specification

- **Objective / user value:** Establish coherent product, statistical, data, provider and implementation contracts before code; users eventually see trustworthy and consistent metrics.
- **In scope:** 0.0-A product scope/screen map; 0.0-B canonical data model; 0.0-C KPI dictionary/formulas; 0.0-D provider verification/mapping; 0.0-E ingestion architecture; 0.0-F DRF API contracts (current phase); 0.0-G frontend architecture; 0.0-H final 0.1 backlog.
- **Out of scope:** Application code, provider integrations, fabricated data, reports, predictive models, and unverified endpoint claims.
- **Dependencies:** Existing product concept and stack decisions. B/C/D must resolve the recorded open questions before their dependent contracts are finalized.
- **Deliverables:** Versioned specifications, provider evidence and mappings, architecture contracts, implementation backlog. 0.0-A delivered five product documents; 0.0-B added the canonical model, ERD and invariants; 0.0-C defines KPIs, windows and synthetic acceptance cases.
- **Exit criteria:** All 0.0 subphases reviewed and mutually consistent; formulas, data authority, provider feasibility, API and frontend contracts explicit; 0.1 backlog ready. Completing 0.0-A alone does not satisfy this gate.

## 0.1 — HR Recurrence

- **Objective / user value:** Traceable descriptive HR production and recurrence across league, teams, players and games.
- **In scope:** MLB seasons/all 30 franchises, players, schedules/completed games, HR events and PA where needed; Today overview, League, Teams, Players, Games, team matrix, player recurrence and HR logs; 7G/15G/30G/60G/Season; CSV and PDF from shared analytics. Django Admin initial data inspection.
- **Out of scope:** Advanced Statcast/contact, park/weather intelligence, contextual matchup calculations, Elo, ratings, probability and machine learning. Social is not a dependency.
- **Dependencies:** Approved 0.0 data/KPI/provider/ingestion/API/frontend contracts and validated core provider data.
- **Deliverables:** Responsive application and descriptive exports, provenance and missing-data states, tested recurring ingestion and KPI calculations.
- **Exit criteria:** Users can navigate from a leaderboard or matrix cell to its supporting game/HR event; documented KPIs match web/CSV/PDF; all window and exceptional-game rules follow 0.0-C; mobile/tablet/desktop and accessibility review pass; no predictive claims.

## 0.2 — Statcast Intelligence

- **Objective / user value:** Explore observed contact quality and pitch-level patterns alongside HR history.
- **In scope:** Verified Statcast batted-ball/pitch linkage and provenance; exit velocity, launch angle, distance, barrel/hard-hit/sweet-spot and expected-stat candidates when verified; pitch type/velocity/location and hand-aware splits; Player Statcast, Pitch Profile, Splits and initial Explore views.
- **Out of scope:** Weather/park-based matchup conclusions, composite ratings, HR probability and unvalidated prediction.
- **Dependencies:** Stable 0.1 events/identifiers, verified 0.0-D advanced provider coverage and permissions, defined denominators/sample-size rules.
- **Deliverables:** Normalized tracking data and observed/derived contact analyses with coverage indicators.
- **Exit criteria:** Advanced values link to their source events where possible, missing coverage is visible, and pitch-type and velocity comparisons retain proper context and sample sizes.

## 0.3 — Matchup Lab

- **Objective / user value:** Examine evidence about a batter/pitcher pairing and today's environment.
- **In scope:** Batter/pitcher selection; handedness, direct history, pitcher arsenal/usage/velocity and HR/contact allowed; batter pitch-type response; verified park, roof, weather and wind context; Explore park/context sections. Auxiliary Social may ship independently here or later.
- **Out of scope:** Arbitrary matchup scores, calibrated probabilities, model claims, and Social as an analytics dependency.
- **Dependencies:** 0.2 event-level coverage; verified weather/park sources, provenance, latency and terms; contextual definitions and missing-data rules.
- **Deliverables:** Evidence-based Matchup Lab with factor explanations and sample sizes; isolated optional Social if scheduled.
- **Exit criteria:** Every displayed factor is attributable to data and time context; unavailable sources leave other panels usable; velocity analysis respects pitch type; wind interpretation uses direction, field orientation and roof status where supportable.

## 0.4 — HR Intelligence

- **Objective / user value:** Offer interpretable, historically validated HR estimates with uncertainty.
- **In scope:** Candidate Batter Power and Pitcher HR Suppression ratings, Matchup Index and per-PA/per-game HR probability only where justified; historical evaluation, calibration, explainability, sample-size and uncertainty display.
- **Out of scope:** Presenting arbitrary composite scores as scientific facts; defaulting to Elo for rare HR events; training/evaluation leakage.
- **Dependencies:** Reliable 0.1-0.3 data, stable definitions, sufficient historical coverage and a documented evaluation design.
- **Deliverables:** Model specification, versioned evaluation, calibrated outputs and clearly distinct UI labels.
- **Exit criteria:** Train/evaluation separation and calibration are documented; claims match evidence; users can inspect key inputs and uncertainty; model outputs are visually distinct from observed facts.

## 1.0 — Production

- **Objective / user value:** Reliable, maintainable public service.
- **In scope:** Operational hardening, observability, accessibility/performance review, backup/recovery, data freshness monitoring, deployment and support processes.
- **Out of scope:** New analytical claims solely to meet the release number; a database migration without demonstrated need.
- **Dependencies:** Product phases selected for launch have passed their gates; provider terms and operational reliability confirmed.
- **Deliverables:** Production deployment and runbooks, incident/data-quality monitoring, documented service expectations.
- **Exit criteria:** Reliability, privacy/security, accessibility, performance, data correctness and recovery criteria are verified against a release checklist set before launch.

## Phase boundary rule

0.1 displays descriptive HR data only. Statcast belongs primarily to 0.2, contextual Matchup Lab/park/weather to 0.3, and validated predictive models to 0.4. Planned navigation and future labels in documentation do not authorize or imply working functionality in an earlier phase. Social is auxiliary and cannot gate core analytics.
