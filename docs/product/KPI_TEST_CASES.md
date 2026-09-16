# MLB HR Intelligence — Synthetic KPI acceptance cases (0.0-C)

All names and numbers here are **synthetic toy data, not MLB facts**. These are expected results for later implementation tests; no executable tests or provider calls are part of 0.0-C. Unless a row says otherwise, games are final regular-season contests in one selected season, official order shown left to right, participant/PA/HR coverage is complete, each listed batting game has ≥1 PA, and cutoff is after the last listed game. `h=(...)` lists HR count per eligible game. `NULL(reason)` is nonnumeric. `B` means HR Games, `m` actual eligible games. Team versions use team games; player versions use batting games.

| # | Synthetic input | Exact expected result |
| --- | --- | --- |
| 1 | Player A `h=(1,1)` | HR=2, B=2, gaps `(0)`, average=median=0, current/max streak=2, current/max game drought=0. |
| 2 | Player A `h=(1,0,1)` | Gaps `(1)`; average=median=1; current drought=0, maximum drought=1; current streak=1. |
| 3 | Player A `h=(2)`, 4 PAs | HR=2, B=1, multi-HR games=1, HR/Game=2, Games With HR %=100%, HR/PA=0.5; gap summaries `NULL(INSUFFICIENT_HISTORY)`. |
| 4 | Team A games show Player A `1, DNP, 1` | Matrix cells `1,DNP,1`; Player A batting `h=(1,1)`, m=2, gap=0, current streak=2. DNP adds no drought game. |
| 5 | Team A games show Player A `1, APPEARED/0 PA, 1` | Matrix cells `1,0 PA,1`; player batting m=2, gap=0, current streak=2. Zero-PA game is visible but not a batting game. |
| 6 | Player A pinch-hits and walks: one PA, no AB, no HR | Batting m=1, PA=1, HR=0, HR/Game=0, Games With HR %=0%, current game drought=1; AB never controls eligibility. |
| 7 | Player A `h=(0,0,0)`, 3 PAs | HR=0, B=0, current/max game drought=3 annotated `NO_HR_IN_SCOPE`, current/max streak=0, PA/HR=`NULL(NO_HOME_RUNS_IN_SCOPE)`, gap summaries `NULL(INSUFFICIENT_HISTORY)`. |
| 8 | Player A `h=(0,1,0)` | Exactly one HR game: HR=1, B=1, current drought=1, maximum drought=1, both gap summaries `NULL(INSUFFICIENT_HISTORY)`. |
| 9 | Player A `h=(1,0,1)` | Two HR games establish first and only gap=1; median=average=1. No leading/trailing game is inserted into the gap. |
| 10 | Player A candidate games `1, HR_EVENTS PARTIAL, 1` | Rolling 3G selects all three; HR, HR/Game, Games With HR %, gap and streak are `NULL(INCOMPLETE)`. Do not skip middle game or report gap=0. |
| 11 | Player A appears in middle candidate game with PA coverage PARTIAL; other known games `1,…,1` | Player last-2 batting-game membership is `NULL(INCOMPLETE)` because middle game might qualify; PA and HR/PA for that requested window are nonnumeric. No older replacement game is selected. |
| 12 | Team A same-date doubleheader, game numbers 1 and 2, `h=(1,0)` | Two distinct games/columns, ordered 1 then 2; HR=1, m=2, Games With HR %=50%, current game drought=1, current streak=0. |
| 13 | Player A HR game, postponed contest, then HR game | Postponed contest is absent from player/team completed windows; player `h=(1,1)` has gap=0 and current streak=2. It creates no DNP or zero-HR cell. |
| 14 | Game G1 official date day 1 starts/suspends, completes day 3 with HR; G2 official date day 2 has 0 HR | At data-as-of after day 3, order is G1 then G2 despite completion date, so `h=(1,0)`, current drought=1. Before G1 is final, it is excluded and cannot be a zero-HR observation. |
| 15 | Player A represents Team A in G1 `h=1`, then Team B in G2 `h=0`, G3 `h=2` | Historical player HR=3; Team A-attributed player HR=1; Team B-attributed player HR=2. Current team metadata cannot reassign G1. |
| 16 | Same trade, full-season player view | Player batting `h=(1,0,2)`, m=3, HR=3, B=2, one gap=1, current drought=0, current streak=1. |
| 17 | Same trade, Player A filtered to Team B | Filter before window: `h=(0,2)`, m=2, HR=2, B=1, current drought=0, maximum drought=1, no gap history. |
| 18 | Team A requests 30G; only two candidate games `h=(0,1)` exist | Window uses m=2 and displays `2 of 30`; HR=1, HR/Game=0.5, Games With HR %=50%. It is never labeled as 30 observed games. |
| 19 | Team A sequence Away0, Home1, Away1, Home2; request last 2 Away games | Filter first → `h=(0,1)` from games 1 and 3, m=2, HR=1, Games With HR %=50%. Taking last two overall then filtering is incorrect. |
| 20 | Player A `h=(1,0,2)`; cutoff is second game's ID | W contains `h=(1,0)` only: HR=1, current drought=1, current streak=0. Later HR cannot enter historical result. |
| 21 | Player A latest game is HR: `h=(0,2)` | Current game drought=0, current HR streak=1, HR=2, B=1. |
| 22 | Player A latest game is non-HR: `h=(1,0)` | Current game drought=1, current HR streak=0, maximum streak=1. |
| 23 | Player A latest final relevant game has HR_EVENTS coverage PARTIAL | Current drought/streak and HR-based window totals are `NULL(INCOMPLETE)`; do not use the preceding complete game as latest. |
| 24 | Player A HR PA has verified batter/game/team but unknown pitcher | Player HR=1 and HR log remains attributable; pitcher-dependent analysis is unknown/excluded, never assigned to an invented pitcher. |
| 25 | Player A has 5 complete PAs and zero HR in W | HR/PA=0, PA/HR=`NULL(NO_HOME_RUNS_IN_SCOPE)` rather than infinity; game drought depends on the number of eligible games, not five PAs. |

## Additional deterministic boundary checks

| Synthetic input | Exact expected result |
| --- | --- |
| `h=(1,0,1,1)` | Gaps `(1,0)`; average and median both `0.5`. |
| Player PA sequence `(non-HR, non-HR, HR, non-HR)` | Current PA drought=1, maximum PA drought=2; game drought must be calculated from game sequence separately. |
| Player PA sequence `(HR, non-HR, non-HR)` | Current PA drought=2, maximum PA drought=2. |
| Complete empty scope | HR=0, PA=0, B=0, multi-HR games=0; HR/Game, Games With HR %, drought and streak=`NULL(NO_GAMES)`; HR/PA=`NULL(ZERO_DENOMINATOR)`. |
| Same-day games lack game number/start distinction; HR outcomes differ | Canonical ID provides deterministic display order, marked `ORDER_UNVERIFIED`; order-sensitive KPI is `NULL(ORDER_UNVERIFIED)` if swapping them could change it. |
| Team A matrix after Player A transfers to Team B and non-affiliation is verified | Team A later cell=`NOT_WITH_TEAM`, not `DNP`; earlier Team A HR remains on that row. |
| Player A has older HR_EVENTS `PARTIAL` but latest complete game has 0 HR | Current HR streak=0 (latest decisive non-HR); full-window HR total and maximum streak remain `NULL(INCOMPLETE)`. |
| Player A has older HR_EVENTS `PARTIAL` but latest complete game has 1 HR | Current game drought=0 (latest decisive HR); full-window HR total and maximum drought remain `NULL(INCOMPLETE)`. |

The fixture pattern for future tests should assert both the **value** and the **semantic reason/annotation**, plus requested N, actual m, cutoff, and data-as-of. Each cell/state is tested independently from the player's rolling batting-game KPI.
