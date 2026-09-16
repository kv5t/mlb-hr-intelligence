# MLB HR Intelligence — MVP 0.1 KPI dictionary (0.0-C)

**Canonical for formulas.** This document defines descriptive statistics only. [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md) defines the observation set, filters, ordering, cutoff and matrix states. No provider endpoint or availability is asserted. Every example below is **synthetic**. Stable IDs are semantic IDs, not API paths.

## Shared mathematical contract

For subject `s` and resolved window `W`, let `G_s(W)=(g₁,…,gₘ)` be the ordered, eligible team games or player batting games selected under [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md). `m=|G|` is the **actual** denominator; requested N and m are both displayed. Let `P_s(g)` be canonical PAs by that subject in `g`, and `H_s(g)` be canonical HR events on those PAs. Define `p_i=|P_s(g_i)|`, `h_i=|H_s(g_i)|`, `P=Σp_i`, `H=Σh_i`, and `b_i=1` if `h_i≥1`, else `0`. For TEAM, all PAs batting for that team count; for PLAYER, only that batter's PAs count. One HR event belongs to one PA. Games outside W and HR before its lower boundary are never used to seed a **maximum** window-local drought or streak. Current droughts and streaks are cutoff-state metrics and may scan before W within the same season and filters.

**Coverage gate:** HR totals/rates, HR-game counts, gaps and maximum runs require `HR_EVENTS=COMPLETE` for every selected game. Current drought/streak needs the latest decisive suffix only, as specified in its entry: a complete latest HR proves drought 0 and a complete latest non-HR proves streak 0 even if older HR coverage is incomplete. `PLATE_APPEARANCES=COMPLETE` for every team game is required for team PA/PA-rate KPIs; complete player `pa_coverage` and canonical PA rows are required for player PA/PA-rate KPIs. Participation/PA evidence is required to establish player batting-game membership. If a required observation is partial, value=`NULL`, reason=`INCOMPLETE`; if unavailable/unresolved, value=`NULL`, reason=`UNKNOWN`. This precedes denominator/zero handling. No complete game is skipped to replace a partial one. PA-sequence KPIs additionally require verified within-game PA order. If an unresolved same-day order changes last-N window membership, every KPI using that membership is `NULL(ORDER_UNVERIFIED)`, including counts and rates. If membership is fixed, order-sensitive KPIs are nonnumeric when the tie changes their value.

**Shared fields for every entry below:** Phase introduced is **0.1**. Window behavior is Season or last N selected games in `G_s(W)`; cutoff is the resolved inclusive game/date; home/away and represented-team filters are applied **before** last N. Each entry explicitly states any exception. DNP and verified zero-PA appearances are outside player `G`; neither advances game drought nor breaks streak. A multi-HR game contributes `h_i` to production counts but only one `b_i` to recurrence counts. `NULL` is never numeric zero. Calculations use exact integer counts and full-precision division; format/round only at presentation, never before downstream calculations. Count output is integer, median can be integer or half-integer, other ratios are full-precision conceptual values.

**Reason precedence:** unresolved selection/coverage (`INCOMPLETE`, `UNKNOWN`, `ORDER_UNVERIFIED`) first; then mathematical reasons (`NO_GAMES`, `ZERO_DENOMINATOR`, `NO_HOME_RUNS_IN_SCOPE`, `INSUFFICIENT_HISTORY`). A complete empty scope permits HR, PA, HR Games and multi-HR games to be numeric 0; game rates, gaps, droughts and streaks have `NO_GAMES` or another specified reason. For maximum droughts, a complete W with `H=0` has length `m` (or `P`) and `NO_HR_IN_SCOPE`. For current droughts the annotation applies only when no HR exists in the complete season/filter scope through cutoff.

The per-entry **eligible set, coverage, window, cutoff, filters, DNP and zero-PA** fields below reference this contract; their stated values are part of each KPI definition, not optional guidance. `Synthetic example` values assume complete evidence unless specified.

## Production KPIs

### HR

- **KPI ID / display / category / subjects / unit / phase:** `player.hr`, `team.hr` / HR / Production / PLAYER, TEAM / HR count / 0.1.
- **Definition / formula / numerator / denominator:** Credited HR events in W; `H=Σh_i`; numerator `H`; denominator none.
- **Eligible set / required coverage:** `G_s(W)` and its PA-linked HR events; HR_EVENTS complete, plus player membership evidence.
- **Window / cutoff / filters:** Shared W, inclusive cutoff and pre-window filters; team matrix row HR uses its distinct team-game W, not this player's own W.
- **Zero / null / unknown / minimum history:** Complete `H=0` → 0, including complete empty scope; null only if required evidence unresolved; no positive history required.
- **Multi-HR / DNP / zero-PA:** Count each HR event; DNP and zero-PA do not create player HR or player batting games.
- **Synthetic example / source entities:** Player A's `h=(0,2,1)` → HR=3; `HomeRunEvent`, `PlateAppearance`, `Game`, participation, coverage.

### PA

- **KPI ID / display / category / subjects / unit / phase:** `player.pa`, `team.pa` / Plate Appearances / Production opportunity count / PLAYER, TEAM / PA count / 0.1.
- **Definition / formula / numerator / denominator:** Canonical batter opportunities in W; `P=Σp_i`; numerator `P`; denominator none. `reported_pa_count` does not replace PA rows.
- **Eligible set / required coverage:** `G_s(W)`; complete relevant player PA coverage or team PLATE_APPEARANCES coverage. HR coverage is not required for PA alone.
- **Window / cutoff / filters:** Shared W, inclusive cutoff and pre-window filters.
- **Zero / null / unknown / minimum history:** Complete empty scope → 0; missing PA evidence → nonnumeric; no positive history required.
- **Multi-HR / DNP / zero-PA:** Each HR PA counts once; DNP and zero-PA contribute no PA, and zero-PA is outside player G.
- **Synthetic example / source entities:** Player A walks once with no AB → PA=1; `PlateAppearance`, `Game`, participation, coverage.

### HR/PA

- **KPI ID / display / category / subjects / unit / phase:** `player.hr_per_pa`, `team.hr_per_pa` / HR/PA / Production rate / PLAYER, TEAM / HR per PA / 0.1.
- **Definition / formula / numerator / denominator:** `H/P` when `P>0`; numerator HR `H`; denominator PA `P` in the same W.
- **Eligible set / required coverage:** `G_s(W)`; complete HR and PA coverage for all selected games/opportunities.
- **Window / cutoff / filters:** Shared W, inclusive cutoff and pre-window filters.
- **Zero / null / unknown / minimum history:** Complete `H=0,P>0` → 0; `P=0` → NULL `ZERO_DENOMINATOR`; unresolved coverage precedes that reason; no HR history minimum.
- **Multi-HR / DNP / zero-PA:** Multiple HR count separately; DNP/zero-PA outside player G.
- **Synthetic example / source entities:** `H=2,P=8` → 0.25 HR/PA; HR events, PAs, Game, participation, coverage.

### PA/HR

- **KPI ID / display / category / subjects / unit / phase:** `player.pa_per_hr`, `team.pa_per_hr` / PA/HR / Production efficiency / PLAYER, TEAM / PA per HR / 0.1.
- **Definition / formula / numerator / denominator:** `P/H` when `H>0`; numerator PA `P`; denominator HR `H` in the same W.
- **Eligible set / required coverage:** `G_s(W)`; complete HR and PA coverage.
- **Window / cutoff / filters:** Shared W, inclusive cutoff and pre-window filters.
- **Zero / null / unknown / minimum history:** `H=0` → NULL `NO_HOME_RUNS_IN_SCOPE`, never infinity; unresolved coverage takes precedence; at least one HR for a numeric result.
- **Multi-HR / DNP / zero-PA:** Multiple HR count separately in denominator; DNP/zero-PA outside player G.
- **Synthetic example / source entities:** `P=8,H=2` → 4 PA/HR; HR events, PAs, Game, participation, coverage.

### HR/Game

- **KPI ID / display / category / subjects / unit / phase:** `player.hr_per_game`, `team.hr_per_game` / Player HR/Batting Game, Team HR/Team Game / **Production** rate / PLAYER, TEAM / HR per eligible game / 0.1.
- **Definition / formula / numerator / denominator:** `H/m`; numerator HR `H`; denominator `m` player batting games or team games respectively, never an unstated generic “game.”
- **Eligible set / required coverage:** `G_s(W)`; complete HR coverage and player batting-game membership evidence.
- **Window / cutoff / filters:** Shared W, inclusive cutoff and pre-window filters.
- **Zero / null / unknown / minimum history:** `H=0,m>0` → 0; `m=0` → NULL `NO_GAMES`; no HR history minimum.
- **Multi-HR / DNP / zero-PA:** Multiple HR increase H, not m; DNP/zero-PA outside player m.
- **Synthetic example / source entities:** Two HR across three player batting games → 2/3 HR/Game; HR events, PAs, Game, participation, coverage.

## Recurrence counts and frequency

### HR Games

- **KPI ID / display / category / subjects / unit / phase:** `player.hr_games`, `team.hr_games` / Games With HR / Recurrence count / PLAYER, TEAM / games / 0.1.
- **Definition / formula / numerator / denominator:** `B=Σb_i`; numerator count of HR games; denominator none.
- **Eligible set / required coverage:** `G_s(W)`; complete HR coverage and player batting-game membership evidence.
- **Window / cutoff / filters:** Shared W, inclusive cutoff and pre-window filters.
- **Zero / null / unknown / minimum history:** Complete no-HR or empty scope → 0; unresolved evidence → nonnumeric; no minimum history.
- **Multi-HR / DNP / zero-PA:** A multi-HR game contributes one; DNP/zero-PA outside player G.
- **Synthetic example / source entities:** `h=(0,2,1)` → 2 HR games; HR events, PAs, Game, participation, coverage.

### Games With HR %

- **KPI ID / display / category / subjects / unit / phase:** `player.hr_game_pct`, `team.hr_game_pct` / Games With HR % / Recurrence frequency / PLAYER, TEAM / percent / 0.1.
- **Definition / formula / numerator / denominator:** `100×B/m` when `m>0`; numerator HR games `B`; denominator player batting games or team games `m`.
- **Eligible set / required coverage:** `G_s(W)`; complete HR coverage and player batting-game membership evidence.
- **Window / cutoff / filters:** Shared W, inclusive cutoff and pre-window filters.
- **Zero / null / unknown / minimum history:** `B=0,m>0` → 0%; `m=0` → NULL `NO_GAMES`; no HR minimum.
- **Multi-HR / DNP / zero-PA:** Multi-HR contributes one numerator game; DNP/zero-PA outside player m.
- **Synthetic example / source entities:** `h=(0,2,1)` → 2/3×100%; HR events, PAs, Game, participation, coverage.

### Multi-HR Games

- **KPI ID / display / category / subjects / unit / phase:** `player.multi_hr_games`, `team.multi_hr_games` / Multi-HR Games / Recurrence pattern count / PLAYER, TEAM / games / 0.1.
- **Definition / formula / numerator / denominator:** `Σ1[h_i≥2]`; numerator count of games with at least two subject HR; denominator none.
- **Eligible set / required coverage:** `G_s(W)`; complete HR coverage and player batting-game membership evidence.
- **Window / cutoff / filters:** Shared W, inclusive cutoff and pre-window filters.
- **Zero / null / unknown / minimum history:** Complete no multi-HR or empty scope → 0; unresolved evidence → nonnumeric; no minimum history.
- **Multi-HR / DNP / zero-PA:** Two or three HR in one game contribute one multi-HR game; DNP/zero-PA outside player G.
- **Synthetic example / source entities:** `h=(0,2,1)` → 1 multi-HR game; HR events, PAs, Game, participation, coverage.

## Gaps, droughts and streaks

### Individual HR gaps

- **KPI ID / display / category / subjects / unit / phase:** `player.hr_gap_games`, `team.hr_gap_games` / HR Gap / Recurrence interval / PLAYER, TEAM / non-HR eligible games / 0.1.
- **Definition / formula / numerator / denominator:** Let HR-game indices be `i₁<…<iₖ`; each consecutive gap `d_j=i_{j+1}-i_j-1`, for `j=1,…,k-1`. Numerator number of eligible **non-HR** games strictly between that HR-game pair; denominator none. Raw index difference is not the gap.
- **Eligible set / required coverage:** Ordered `G_s(W)`; complete HR coverage, player membership and verified order when value could change.
- **Window / cutoff / filters:** Shared W, inclusive cutoff and pre-window filters; pairs must both lie inside W.
- **Zero / null / unknown / minimum history:** Consecutive HR games → gap 0; `k<2` → no gap values, reason `INSUFFICIENT_HISTORY`; uncertainty/barrier → nonnumeric affected gap(s).
- **Multi-HR / DNP / zero-PA:** Multi-HR game is one HR-game endpoint; DNP/zero-PA outside player index sequence.
- **Synthetic example / source entities:** `h=(1,0,1)` → one gap `1`; Game, HR events, PAs, participation, coverage.

### Average HR Gap

- **KPI ID / display / category / subjects / unit / phase:** `player.avg_hr_gap_games`, `team.avg_hr_gap_games` / Average HR Gap / Recurrence interval summary / PLAYER, TEAM / games / 0.1.
- **Definition / formula / numerator / denominator:** For `k≥2`, `Σd_j/(k-1)`; numerator sum of consecutive gap lengths; denominator number of gaps `k-1`.
- **Eligible set / required coverage:** Ordered `G_s(W)` and all gaps; complete HR and membership coverage, verified order where material.
- **Window / cutoff / filters:** Shared W, inclusive cutoff and pre-window filters; no HR before W is used.
- **Zero / null / unknown / minimum history:** All consecutive HR games → 0; `k<2` → NULL `INSUFFICIENT_HISTORY`; any relevant unresolved gap → nonnumeric.
- **Multi-HR / DNP / zero-PA:** One endpoint per multi-HR game; DNP/zero-PA outside player sequence.
- **Synthetic example / source entities:** `h=(1,0,1,1)` → gaps `(1,0)`, mean 0.5; Game, HR events, PAs, participation, coverage.

### Median HR Gap

- **KPI ID / display / category / subjects / unit / phase:** `player.median_hr_gap_games`, `team.median_hr_gap_games` / Median HR Gap / Recurrence interval summary / PLAYER, TEAM / games / 0.1.
- **Definition / formula / numerator / denominator:** Median of sorted `d₁,…,dₖ₋₁`; odd count → middle gap, even count → arithmetic mean of two middle gaps. Numerator/denominator are the two middle values/2 only in the even case; otherwise not a ratio.
- **Eligible set / required coverage:** Ordered `G_s(W)` and all gaps; complete HR and membership coverage, verified order where material.
- **Window / cutoff / filters:** Shared W, inclusive cutoff and pre-window filters.
- **Zero / null / unknown / minimum history:** Consecutive HR pairs may yield median 0; `k<2` → NULL `INSUFFICIENT_HISTORY`; unresolved gap → nonnumeric. Value may end in `.5`.
- **Multi-HR / DNP / zero-PA:** One endpoint per multi-HR game; DNP/zero-PA outside player sequence.
- **Synthetic example / source entities:** `h=(1,0,1,1)` → gaps `(1,0)`, median 0.5; Game, HR events, PAs, participation, coverage.

### Current HR Drought — games

- **KPI ID / display / category / subjects / unit / phase:** `player.current_hr_drought_games`, `team.current_hr_drought_games` / Current HR Drought — Batting Games or Team Games / Recurrence / PLAYER, TEAM / games / 0.1.
- **Definition / formula / numerator / denominator:** Length of the trailing non-HR run through cutoff across the same season/subject/game type/team and home-away filters; numerator trailing non-HR games; denominator none. Scan before W until an HR or the beginning of that full scope. If no HR exists in the complete full scope, annotate `NO_HR_IN_SCOPE`.
- **Eligible set / required coverage:** Ordered eligible games through cutoff, including before W; known membership and HR coverage from the latest game backward through the trailing non-HR run and its first preceding HR, or to the start of the season/filter scope. A complete latest HR alone proves value 0. Verify order where material.
- **Window / cutoff / filters:** Inclusive cutoff and shared filters; requested N affects window-local metrics but does not cap the cutoff-state scan.
- **Zero / null / unknown / minimum history:** Latest complete HR game → 0 even if older HR coverage is incomplete; `m=0` → NULL `NO_GAMES`; unresolved latest/relevant run → nonnumeric; no prior HR required.
- **Multi-HR / DNP / zero-PA:** Any HR ends drought; DNP/zero-PA do not increment player game drought.
- **Synthetic example / source entities:** `h=(1,0,0)` → 2 games; Game, HR events, PAs, participation, coverage.

### Maximum HR Drought — games

- **KPI ID / display / category / subjects / unit / phase:** `player.max_hr_drought_games`, `team.max_hr_drought_games` / Maximum HR Drought — Batting Games or Team Games / Recurrence / PLAYER, TEAM / games / 0.1.
- **Definition / formula / numerator / denominator:** Maximum length among all runs of `b_i=0` inside W, including leading, internal and trailing runs; numerator longest run length; denominator none. If `B=0,m>0`, value `m` with `NO_HR_IN_SCOPE` annotation.
- **Eligible set / required coverage:** Ordered `G_s(W)`; complete HR/membership coverage, verified order where material.
- **Window / cutoff / filters:** Shared W, inclusive cutoff and pre-window filters.
- **Zero / null / unknown / minimum history:** All HR games → 0; `m=0` → NULL `NO_GAMES`; any unresolved selected observation → nonnumeric; no prior HR required.
- **Multi-HR / DNP / zero-PA:** Any positive HR ends a run; DNP/zero-PA outside player sequence.
- **Synthetic example / source entities:** `h=(0,0,1,0)` → max drought 2; Game, HR events, PAs, participation, coverage.

### Current HR Drought — PA

- **KPI ID / display / category / subjects / unit / phase:** `player.current_hr_drought_pa` / Current HR Drought — PA / Recurrence opportunity run / PLAYER only / PA / 0.1, secondary to game drought.
- **Definition / formula / numerator / denominator:** In ordered canonical PAs through cutoff across the same season/subject/game type/team and home-away filters, count trailing PAs without an HR event; denominator none. Scan before W until an HR or the beginning of that scope. Annotate `NO_HR_IN_SCOPE` only if no HR exists in the complete full scope.
- **Eligible set / required coverage:** Player eligible batting games through cutoff and their PAs, including before W; complete relevant player PA and game HR coverage plus verified PA order through the decisive suffix.
- **Window / cutoff / filters:** Inclusive cutoff and shared filters; requested game-window N does not cap the current PA drought. No separate last-N-PA window is selected.
- **Zero / null / unknown / minimum history:** Latest PA is HR → 0; `m=0` → NULL `NO_GAMES` (a nonempty player batting-game scope necessarily has PA); unresolved PA/event/order → nonnumeric; no prior HR required.
- **Multi-HR / DNP / zero-PA:** Each HR PA resets run; DNP/zero-PA supply no PAs.
- **Synthetic example / source entities:** PA outcomes `(HR, non-HR, non-HR)` → 2 PA; PA, HR event, Game, participation, coverage.

### Maximum HR Drought — PA

- **KPI ID / display / category / subjects / unit / phase:** `player.max_hr_drought_pa` / Maximum HR Drought — PA / Recurrence opportunity run / PLAYER only / PA / 0.1, secondary.
- **Definition / formula / numerator / denominator:** Maximum run of consecutive non-HR canonical PAs inside W, including leading, internal and trailing runs; numerator longest run; denominator none. If `H=0,P>0`, value `P` with `NO_HR_IN_SCOPE` annotation.
- **Eligible set / required coverage:** Ordered player PAs in `G(W)`; complete player PA and game HR coverage, verified within-game PA order.
- **Window / cutoff / filters:** Shared player W/cutoff/pre-window filters; no PAs outside W.
- **Zero / null / unknown / minimum history:** All PAs are HR → 0; `m=0` → NULL `NO_GAMES`; unresolved order/coverage → nonnumeric.
- **Multi-HR / DNP / zero-PA:** Each distinct HR PA breaks a PA run; DNP/zero-PA add no PAs.
- **Synthetic example / source entities:** Outcomes `(non-HR, non-HR, HR, non-HR)` → max 2 PA; PA, HR event, Game, participation, coverage.

### Current HR Streak

- **KPI ID / display / category / subjects / unit / phase:** `player.current_hr_streak_games`, `team.current_hr_streak_games` / Current HR Streak / Recurrence / PLAYER, TEAM / games / 0.1.
- **Definition / formula / numerator / denominator:** Length of trailing HR-game run through cutoff across the same season/subject/game type/team and home-away filters, including games before W; numerator trailing HR games; denominator none.
- **Eligible set / required coverage:** Ordered eligible games through cutoff; known membership and HR coverage from latest game backward through trailing HR run and its first preceding non-HR, or to the start of the season/filter scope. A complete latest non-HR alone proves value 0. Verify order where material.
- **Window / cutoff / filters:** Inclusive cutoff and shared filters; requested N does not cap the cutoff-state streak.
- **Zero / null / unknown / minimum history:** Latest complete non-HR game → 0 even if older HR coverage is incomplete; `m=0` → NULL `NO_GAMES`; unresolved newest/relevant observation → nonnumeric.
- **Multi-HR / DNP / zero-PA:** Multi-HR game extends streak by one; DNP/zero-PA do not break player streak.
- **Synthetic example / source entities:** `h=(0,2,1)` → current streak 2; Game, HR events, PAs, participation, coverage.

### Maximum HR Streak

- **KPI ID / display / category / subjects / unit / phase:** `player.max_hr_streak_games`, `team.max_hr_streak_games` / Maximum HR Streak / Recurrence / PLAYER, TEAM / games / 0.1.
- **Definition / formula / numerator / denominator:** Maximum length among runs of `b_i=1` inside W; numerator longest HR-game run; denominator none.
- **Eligible set / required coverage:** Ordered `G_s(W)`; complete HR/membership coverage, verified order where material.
- **Window / cutoff / filters:** Shared W, inclusive cutoff and pre-window filters.
- **Zero / null / unknown / minimum history:** `m>0,B=0` → 0; `m=0` → NULL `NO_GAMES`; any unresolved selected observation → nonnumeric.
- **Multi-HR / DNP / zero-PA:** Multi-HR counts one streak game; DNP/zero-PA outside player sequence.
- **Synthetic example / source entities:** `h=(1,1,0,2)` → max streak 2; Game, HR events, PAs, participation, coverage.

## Presentation and qualification policy

Every rate displays its actual denominator: PA for HR/PA, HR for PA/HR, eligible games for HR/Game and Games With HR %. Gap summaries show HR-game count `k` and gap count `k−1`. Drought/streak views show actual game or PA opportunity count and requested N. No valid descriptive observation is hidden by an arbitrary qualification threshold. A later leaderboard qualification toggle must be separate, explicit and never alter a KPI's definition. `UNKNOWN`, `INCOMPLETE`, `ORDER_UNVERIFIED`, `INSUFFICIENT_HISTORY`, `NO_GAMES`, `ZERO_DENOMINATOR` and `NO_HOME_RUNS_IN_SCOPE` are distinct semantic reasons; exact API shape and UI tokens belong to 0.0-F/G.
