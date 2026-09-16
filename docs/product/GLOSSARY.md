# MLB HR Intelligence — Product glossary

**Status:** Terminology updated through 0.0-E. [DATA_MODEL.md](DATA_MODEL.md) defines structures; [KPI_SPEC.md](KPI_SPEC.md) defines formulas; [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md) defines eligibility, windows and cutoff. Sampled provider mapping and authority are in [PROVIDER_STRATEGY.md](PROVIDER_STRATEGY.md) and [PROVIDER_FIELD_MAPPING.md](PROVIDER_FIELD_MAPPING.md); open gaps are in [PROVIDER_GAPS.md](PROVIDER_GAPS.md). Ingestion/update behavior is specified in [INGESTION_ARCHITECTURE.md](INGESTION_ARCHITECTURE.md), [COVERAGE_POLICY.md](COVERAGE_POLICY.md) and companion 0.0-E documents.

| Term | Product meaning and boundary | Pending |
| --- | --- | --- |
| HR | Home run credited to a batter; a production count. | Sampled source mapping documented; completeness validation remains open. |
| PA | Canonical plate appearance, used as an opportunity denominator where appropriate. | Sampled source mapping documented; implementation validation remains open. |
| HR/Game | HR divided by eligible player batting games or team games respectively; a **production rate**, never recurrence. | Formula in KPI_SPEC; sampled source mapping documented; implementation validation open. |
| HR/PA | HR divided by canonical PA in the same scope; undefined at zero PA. | Formula in KPI_SPEC; sampled source mapping documented; implementation validation open. |
| PA/HR | Canonical PA divided by HR in the same scope; `NULL(NO_HOME_RUNS_IN_SCOPE)` at zero HR, never infinity. | Formula in KPI_SPEC. |
| Games With HR | Count of eligible subject games with ≥1 HR. | Formula in KPI_SPEC. |
| Games With HR % | 100 times HR games divided by eligible subject games; recurrence frequency. | Formula in KPI_SPEC. |
| HR Game | One eligible player batting game or team game with ≥1 HR, even if multiple HR events occur. | Formula in KPI_SPEC. |
| Multi-HR Game | Eligible subject game with ≥2 HR; one game in this count. | Formula in KPI_SPEC. |
| HR Gap | Count of eligible non-HR games strictly between consecutive HR games; consecutive HR games have gap 0. | Formula in KPI_SPEC. |
| Average HR Gap | Arithmetic mean of consecutive HR gaps; needs ≥2 HR games. | Formula in KPI_SPEC. |
| Median HR Gap | Statistical median of consecutive HR gaps; needs ≥2 HR games. | Formula in KPI_SPEC. |
| Current HR Drought | Trailing non-HR run at cutoff across the same season and filters, explicitly labeled in eligible games or player PAs; it can extend before the displayed N-game window. | Formulas in KPI_SPEC. |
| Maximum HR Drought | Longest non-HR run inside scope, including leading and trailing edges; label game or PA unit. | Formulas in KPI_SPEC. |
| HR Streak | Consecutive eligible games with ≥1 HR. | Formula in KPI_SPEC. |
| Current HR Streak | Trailing HR-game run at cutoff across the same season and filters; it can extend before the displayed N-game window. | Formula in KPI_SPEC. |
| Maximum HR Streak | Longest HR-game run inside selected scope. | Formula in KPI_SPEC. |
| Production | Count or rate of HR output and opportunities, including HR/Game, HR/PA and PA/HR. | MVP formulas in KPI_SPEC. |
| Recurrence | Pattern of HR games: frequency, gaps, droughts and streaks; never a synonym for HR/Game. | MVP formulas in KPI_SPEC. |
| Contact Quality | Tracked characteristics of batted balls, such as exit velocity, barrels and launch angle; primarily 0.2. | Sampled source fields documented; later KPI specification. |
| Context | Conditions/dimensions for interpretation: handedness, pitch type/velocity, park, weather, wind, roof. Not itself a prediction. | Candidate sources evaluated; later phase selection and validation. |
| Observed Statistic | Count or reported measurement tied to actual events, such as HR total or measured exit velocity. | Provider evidence documented; coverage validation open. |
| Derived Metric | Reproducible calculation from canonical data, such as HR/PA or median HR gap. | MVP formulas in KPI_SPEC. |
| Rating | A modeled or composite assessment, distinct from observed facts; deferred to 0.4 and requires validation. | Model design 0.4. |
| Prediction | Estimate of a future/unknown outcome, such as HR probability; deferred to 0.4. | Evaluation/calibration 0.4. |
| Window | Explicit bounded set of selected subject opportunities; required coverage gates numeric results. | Semantics in WINDOW_SEMANTICS. |
| Season Window | All selected regular-season subject games through cutoff. | Semantics in WINDOW_SEMANTICS. |
| Game Window | Last N team games or player batting games (7G/15G/30G/60G), selected after filters. | Semantics in WINDOW_SEMANTICS. |
| Plate Appearance | Canonical batter opportunity in one game, distinct from at-bat, with stable internal identity. | Sampled source mapping documented; implementation validation remains open. |
| Game | Distinct MLB contest with immutable internal identity; doubleheaders stay separate and a suspended/resumed contest can stay one game. | Sampled identity behavior documented; broader validation open. |
| Game Type | Canonical category for regular, postseason, spring, All-Star and other/unknown. MVP analytics include regular season only. | Sampled mapping documented; broader validation open. |
| Player-Team Affiliation | Date-granularity sourced historical association; actual game team is recorded with participation/PA. | Temporal-boundary evidence remains open. |
| Player Game Participation | Assessed `APPEARED`, `DID_NOT_APPEAR` or `UNKNOWN`; no row is unassessed. Zero-PA appearance is not a batting game. | Sampled source mapping documented; implementation validation remains open. |
| Data Coverage | Explicit complete, partial, unknown or unavailable assessment for a game/domain or a player's PA set. Empty events alone do not prove zero. | Provider evidence and coverage policy documented; implementation validation open. |
| Home Run Event | Distinct canonical observation linked 1:1 to one HR-producing PA, which supplies player, game and team; carries source provenance and can later link to tracking data. | Sampled matching documented; broader validation open. |
| Provider | External source of facts or context, accessed through an adapter and verified before relying on its fields. | Sampled verification documented; access approval open. |
| Source Data | Provider-reported record/field retained with provenance, before or alongside normalization. | Sampled provider mapping and 0.0-E storage/update policy documented; implementation validation open. |
| Canonical Data | Normalized, validated domain representation independent of a particular provider schema, with separately preserved external IDs. | Conceptual model 0.0-B; implementation later. |
| Derived Data | Stored or computed result of a reproducible transformation of canonical data; not source observation or model output. | MVP formulas in KPI_SPEC; persistence/versioning 0.0-E. |

Displayed labels must identify subject (player/team), season/window and opportunity unit where ambiguity matters. A missing value is distinct from zero.

## 0.0-E operational terms

| Term | Definition | Owner |
| --- | --- | --- |
| Provider access approved | Externally recorded authorization covering a provider and automated operation; public response access does not set this gate. | INGESTION_ARCHITECTURE. |
| Raw source snapshot | Immutable retrieved response bytes plus safe retrieval metadata, retained for replay and audit. | SOURCE_SNAPSHOT_POLICY. |
| Analytics-ready domain | A game/domain with required complete coverage and resolved membership; distinct from game finality. | COVERAGE_POLICY. |
| Dataset revision | Monotonic committed version of canonical facts/coverage pinned by web, CSV and PDF. | INGESTION_ARCHITECTURE. |
