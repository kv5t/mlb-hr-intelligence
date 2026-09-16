# MLB HR Intelligence — Product glossary

**Status:** Product terminology updated through 0.0-B. Definitions describe product meaning, not finalized computation. [DATA_MODEL.md](DATA_MODEL.md) defines the structural entities; **0.0-C** must specify eligible games/PA, denominators, windows, null behavior, and formulas.

| Term | Product meaning and boundary | Pending |
| --- | --- | --- |
| HR | Home run credited to a batter; a production count. | Source/event authority 0.0-D. |
| PA | Plate appearance, used as an opportunity denominator where appropriate. | Eligibility and source mapping 0.0-B/C/D. |
| HR/Game | Home runs per relevant game for a stated subject and window; a **production rate**, never recurrence. | Relevant-game denominator 0.0-C. |
| HR/PA | HR relative to PA; a production rate. | Zero/unknown PA and window rules 0.0-C. |
| PA/HR | PA per HR; a production efficiency expression. | Zero-HR display and window rules 0.0-C. |
| Games With HR | Count of relevant games with at least one HR for the subject. | Relevant-game eligibility 0.0-C. |
| Games With HR % | Share of relevant games with at least one HR; recurrence frequency. | Denominator 0.0-C. |
| HR Game | Relevant game in which the subject has at least one HR; one candidate recurrence occurrence even if multiple HR. | Multi-HR rule 0.0-C. |
| Multi-HR Game | Game with at least two HR by the subject (player or team must be explicit). | Eligible-game and subject rules 0.0-C. |
| HR Gap | Separation between consecutive HR games in an ordered relevant-game sequence. | Between-game count vs index difference 0.0-C. |
| Average HR Gap | Mean of defined HR gaps; recurrence metric. | Gap and insufficient-history behavior 0.0-C. |
| Median HR Gap | Median of defined HR gaps; recurrence metric. | Gap and insufficient-history behavior 0.0-C. |
| Current HR Drought | Current span without an HR in an explicitly stated opportunity unit. | Games vs PA, absent games, cutoff 0.0-C. |
| Maximum HR Drought | Longest defined no-HR span in a stated window/season. | Unit and endpoint rules 0.0-C. |
| HR Streak | Consecutive relevant games with at least one HR. | Eligible-game sequence 0.0-C. |
| Current HR Streak | HR streak active at the selected cutoff. | Cutoff and absence rules 0.0-C. |
| Maximum HR Streak | Longest HR streak in stated scope. | Eligible-game sequence/ties 0.0-C. |
| Production | Count or rate of HR output and opportunities, such as HR, HR/Game, HR/PA, PA/HR. | Exact formulas 0.0-C. |
| Recurrence | Pattern of HR games across opportunities: frequency, gaps, droughts, streaks and dispersion. Not a synonym for HR/Game. | Exact formulas 0.0-C. |
| Contact Quality | Tracked characteristics of batted balls, such as exit velocity, barrels and launch angle; primarily 0.2. | Source definitions 0.0-D and KPI rules 0.0-C/later. |
| Context | Conditions/dimensions for interpretation: handedness, pitch type/velocity, park, weather, wind, roof. Not itself a prediction. | Representation 0.0-B; sources 0.0-D. |
| Observed Statistic | Count or reported measurement tied to actual events, such as HR total or measured exit velocity. | Provenance/coverage 0.0-D. |
| Derived Metric | Reproducible calculation from canonical data, such as HR/PA or median HR gap. | Formula 0.0-C. |
| Rating | A modeled or composite assessment, distinct from observed facts; deferred to 0.4 and requires validation. | Model design 0.4. |
| Prediction | Estimate of a future/unknown outcome, such as HR probability; deferred to 0.4. | Evaluation/calibration 0.4. |
| Window | Explicit bounded set of relevant opportunities used for a display/calculation. | Membership/cutoff 0.0-C. |
| Season Window | Selected season's eligible observations through a stated cutoff. | Membership/cutoff rules 0.0-C. |
| Game Window | Last N eligible games (7G/15G/30G/60G) for a specified subject. | Player/team eligibility 0.0-C. |
| Plate Appearance | Canonical batter opportunity recorded in one game; may differ from at-bat and has its own stable internal identity. | Eligibility/edge-case KPI rules 0.0-C; provider mapping 0.0-D. |
| Game | Distinct MLB contest with an immutable internal identity; doubleheader contests remain separate and a suspended/resumed contest can remain one game. Official date differs from UTC start/completion and local display date. | Window/order rules 0.0-C; provider identity mapping 0.0-D. |
| Game Type | Canonical category distinguishing regular season, postseason, spring training, All-Star and other/unknown. | Product inclusion 0.0-C; provider mapping 0.0-D. |
| Player-Team Affiliation | Sourced temporal association between stable player and team identities; actual game team is recorded with participation/PA. | Source precision 0.0-D; window treatment 0.0-C. |
| Player Game Participation | Assessed `APPEARED`, `DID_NOT_APPEAR`, or `UNKNOWN` state for a player and game; no row means unassessed. An appearance may have zero PA. | Eligibility effects 0.0-C; source mapping 0.0-D. |
| Data Coverage | Explicit complete, partial, unknown or unavailable assessment for a game/domain or a player's PA set. Empty events alone do not prove zero. | Provider evidence 0.0-D; update policy 0.0-E. |
| Home Run Event | Distinct canonical observation linked 1:1 to one HR-producing PA, which supplies player, game and team; carries source provenance and can later link to tracking data. | Source matching 0.0-D. |
| Provider | External source of facts or context, accessed through an adapter and verified before relying on its fields. | Verification 0.0-D. |
| Source Data | Provider-reported record/field retained with provenance, before or alongside normalization. | Provider mapping 0.0-D; storage/update policy 0.0-E. |
| Canonical Data | Normalized, validated domain representation independent of a particular provider schema, with separately preserved external IDs. | Conceptual model 0.0-B; implementation later. |
| Derived Data | Stored or computed result of a reproducible transformation of canonical data; not source observation or model output. | Formula/versioning 0.0-C/E. |

Displayed labels must identify subject (player/team), season/window and opportunity unit where ambiguity matters. A missing value is distinct from zero.
