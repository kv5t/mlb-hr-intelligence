# MLB HR Intelligence — Window and eligibility semantics (0.0-C)

**Canonical for MVP 0.1 windows.** This specifies analytical selection, not provider mapping or API syntax. It uses the entities in [DATA_MODEL.md](DATA_MODEL.md). `UNKNOWN` and `INCOMPLETE` are semantic results, not numeric zero. Every result carries selected season, requested window, cutoff and data-as-of metadata. Report `actual_game_count` only when membership is resolved; otherwise report `known_eligible_game_count` as a lower bound with a nonnumeric membership state.

## 1. Scope, subject and cutoff

MVP 0.1 descriptive leaderboards, recurrence KPIs and default matrices include `Game.game_type=REGULAR` only. `POSTSEASON`, `SPRING`, `ALL_STAR`, `OTHER` and `UNKNOWN` remain storable and navigable but are excluded from these calculations. 0.0-D maps provider types. Subjects are `PLAYER` or `TEAM`; no formula may silently substitute one subject's opportunity set for the other.

An analytical request fixes **season**, subject, optional represented-team filter (player), optional `HOME`/`AWAY`, a **cutoff**, and `Season` or a rolling `N ∈ {7,15,30,60}`. The cutoff is either a canonical game ID (inclusive through that game's ordered position) or an official date (inclusive of **all** games on that date). If the UI says “latest,” it resolves to the latest official date with a final regular-season game in the selected season; for a team or team-filtered player request, use that team's latest final regular-season game date. It does **not** skip incomplete data, and the resolved date is recorded. A separate `data_as_of_utc` identifies the observation snapshot so later corrections do not masquerade as the same historical result; exact snapshot persistence is 0.0-E. No metric definition uses implicit wall-clock `now`.

## 2. Deterministic game order

Within a season, order by `(official_date ascending, game-number key, start key, canonical Game.id ascending)`. For the game-number key, known `scheduled_game_number` precedes unknown and numbers sort ascending. For the start key, prefer known `scheduled_start_at_utc`, otherwise known `actual_start_at_utc`; known instants precede unknown and sort ascending. The immutable ID is a deterministic final tie-break, never import order. **If official date is unknown, order-dependent windows/results are `UNKNOWN`** until it is resolved; such a game is not silently placed at an arbitrary date. A same-day tie resolved solely by ID is marked `ORDER_UNVERIFIED`. If an unverified tied group straddles the last-N boundary and swapping games changes membership, the entire window is `ORDER_UNVERIFIED`; all membership-dependent KPIs, including totals and rates, are nonnumeric. If membership is fixed, order-sensitive metrics remain `ORDER_UNVERIFIED` when swapping the group changes their value. For an official-date cutoff, any candidate with unknown `official_date` that could lie on either side makes selection `UNKNOWN`; date-cutoff counts are numeric only when membership is independently established. This produces identical output for two implementations without claiming an arbitrary ID order is baseball truth.

Two doubleheader contests have distinct IDs and each occupies one position/column. A completed suspended game retains its **original official-date** position; resumed/completed timestamps do not move it to a later analytical date. Rescheduled contests are ordered by their verified official date after completion. 0.0-D must verify source identity and time mapping.

## 3. Candidate games, coverage and conservative results

A **candidate game** is final, in the selected season and regular-season type, in the subject's team schedule or represented-team history, and through the cutoff. Scheduled, postponed, rescheduled but not final, suspended but not final, cancelled and unknown/non-final contests are excluded: they create no zero HR, DNP, drought increment or streak break. A final game with incomplete coverage **remains a candidate** and must not be skipped to fill a rolling N. This is essential: skipping it could manufacture continuity or a misleading “last 30 games” period.

Select the window from candidate games first; then apply each KPI's required coverage. If a selected observation needed by a KPI is `PARTIAL`, report `INCOMPLETE`; if unavailable/unknown, report `UNKNOWN`. Do not publish a numeric partial-window total as if complete. A game outside the selected window does not invalidate it. If a game's eligibility itself is uncertain within the possible last-N range, the window is `UNKNOWN`. Coverage can improve later, so snapshot/as-of metadata matters.

The reusable pipeline is: subject → season → regular game type → optional represented-team/home-away filter → finality → canonical order → cutoff → subject-specific opportunity sequence → last N (or all for Season) → KPI coverage gate → calculation. **Filters precede last N.** Coverage is checked after selection so missing events cannot be silently skipped. This is stricter than constructing a window only from complete games and is deliberate.

## 4. Team games and windows

For a team, its candidate sequence contains each final regular-season game where it is home or away. `HOME` means `team_id=Game.home_team_id`; `AWAY` means away-team ID, never venue name. A team rolling `NG` window is the last N candidate team games through cutoff; Season is all candidate team games. Each doubleheader game counts once. If fewer than N exist, use all and report `requested_N=N`, `actual_game_count=m`. If any selected game lacks coverage required by a KPI, that KPI is nonnumeric with an `UNKNOWN/INCOMPLETE` reason; its selected game count is still reported. Team HR requires complete `HR_EVENTS` coverage; team PA requires complete `PLATE_APPEARANCES` coverage. Finality alone proves neither.

## 5. Player batting games and windows

A **player batting game** is a candidate final regular game with `PlayerGameParticipation=APPEARED`, `pa_coverage=COMPLETE`, and at least one canonical PA for that batter and represented team. Its HR classification also requires complete game `HR_EVENTS` coverage. Thus a walk-only pinch-hit game qualifies; AB is irrelevant. An `APPEARED` zero-PA game, affirmative `DID_NOT_APPEAR`, and an assessed non-batting appearance do not enter the player batting sequence, increase a game drought or break a streak.

An unresolved participation or PA set can hide a batting game. If `PARTICIPATION` coverage is incomplete and the player has no definitive row, or the player's row is `UNKNOWN`/PA coverage incomplete, mark that game an **uncertain player candidate**. If one lies after the Nth known batting game (or anywhere in Season scope) and could change window membership, the player window is `UNKNOWN/INCOMPLETE`; do not replace it with an older game. Complete game participation coverage with no player row can exclude the game from the batting sequence without asserting a sourced DNP cell. Known DNP and verified zero-PA games are skipped as non-opportunities. Player rolling `NG` is the last N qualified batting games, subject to this uncertainty check; Season is all qualified batting games. Report requested N and `actual_game_count` only after membership is resolved. During uncertain membership, expose `known_eligible_game_count` only as a lower bound.

Player full-season scope spans teams. If one player represents both teams in a single contest, that contest enters the unfiltered player batting-game sequence once when at least one PA qualifies; its PAs/HR events aggregate across the two represented-team rows. A represented-team filter is applied **before** last N and uses the team on participation/PA, not current affiliation. Home/away for a player follows that represented team's home/away role in `Game`. A team-filtered player window therefore differs from an unfiltered career/season window; the same contest may enter each team-filtered view once, using only that team’s PAs/HR events.

## 6. Team matrix windows and row states

Every column in a team's matrix uses that team's **team-game** window, including final games with incomplete data; every row shares the same columns. `30G` in a team matrix is not a player's last 30 batting games. Rows are players with documented participation or affiliation to the selected team during the displayed scope. A player who has left the team is `NOT_WITH_TEAM` for later games when non-affiliation is known; this is not DNP. If affiliation cannot establish that fact, use `UNKNOWN`. A player's row `Window HR` counts their HR events while representing the matrix team **only if every selected applicable cell is resolved**; otherwise the total is `UNKNOWN/INCOMPLETE`. A player's independent season HR may include other teams and is labeled accordingly.

| Cell state | Necessary evidence | Conceptual token |
| --- | --- | --- |
| `HR_COUNT(n ≥ 1)` | `APPEARED`, matching verified HR events, complete HR coverage and sufficient PA/participation evidence | `1`, `2`, … |
| `KNOWN_ZERO` | `APPEARED`, complete PA and HR coverage, ≥1 PA, zero matching HR events | `0` |
| `DNP` | Affirmative `DID_NOT_APPEAR` for the matrix team/game | `DNP` |
| `ZERO_PA_APPEARANCE` | `APPEARED`, complete PA coverage, zero PA; HR coverage sufficient to exclude unresolved HR | `0 PA` |
| `NOT_WITH_TEAM` | Verified non-affiliation/representation for that team game | `—` with “not with team” label |
| `UNKNOWN` | Participation, identity or required coverage unavailable/unknown | `?` |
| `INCOMPLETE` | Relevant coverage known partial or facts conflict | `Partial` |

Cell HR count 2 means two events in **one** game. DNP, zero PA, not-with-team and unknown never become `KNOWN_ZERO`. Color may supplement but cannot replace the token. A positive cell drills through Game → PA → HR event → source. Exact styling and API envelope belong to 0.0-G/F.

## 7. Incomplete sequences and boundaries

For a total or rate, a selected game/opportunity lacking required coverage makes the KPI `INCOMPLETE` or `UNKNOWN`, never a numeric zero. For gaps, droughts and streaks, a possible but unresolved eligible game in the requested sequence is a **barrier**. Do not join known HR games across it. Return a nonnumeric result for any affected full-window metric, including maximum streak/drought, rather than silently calculating a possibly understated or overstated value. **Current** game drought/streak uses only its decisive suffix: a complete latest HR proves current drought 0, and a complete latest non-HR proves current streak 0 even if older HR data is incomplete. DNP and confirmed zero-PA participation are not barriers in a player batting-game sequence because their exclusion is known. A latest unresolved relevant observation makes current drought/streak nonnumeric. Fewer than requested N **known** eligible games are allowed only when no unresolved candidate could have changed membership; report the definitive actual denominator only then. Current game drought/streak and current PA drought scan their decisive suffix backward beyond W through the beginning of the same season/filter scope; incomplete or uncertain observations in that suffix remain barriers. Maximum runs remain within W.

## 8. Labels and examples (synthetic)

- `Player HR — Last 30 Batting Games` uses a player's last 30 qualified batting games, across teams unless filtered.
- `Team HR — Last 30 Team Games` uses that team's last 30 final regular games.
- `Matrix Window HR — Last 30 Team Games` counts a row player's HR in the shared team columns.
- If **synthetic** Team A has 18 final regular games through cutoff, a requested 30G team window contains 18 and reports `18 of 30`; it never says 30 games were observed.
- If **synthetic** Player A has HR games separated by a DNP and a zero-PA appearance, those two states are visible in Team A's matrix, but neither enters Player A's batting-game gap sequence.

The KPI formulas are in [KPI_SPEC.md](KPI_SPEC.md); expected results are in [KPI_TEST_CASES.md](KPI_TEST_CASES.md).
