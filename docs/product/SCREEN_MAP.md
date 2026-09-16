# MLB HR Intelligence — Screen map

**Status:** Product inventory aligned through 0.0-F; route names are UI concepts, with public API contracts in [API_CONTRACT.md](API_CONTRACT.md). Routes are suggested UI paths, not API contracts. A screen's introduction phase is the first phase with usable content; future sections remain hidden or explicitly unavailable until shipped. MVP KPI formulas and denominators are in [KPI_SPEC.md](KPI_SPEC.md). Every screen uses visible loading, empty, partial-data, and error messaging with retry where appropriate; missing values are never silently converted to zero.

## Shared navigation and interaction rules

Desktop primary: Today, League, Teams, Players, Games, Matchup, Explore. Social is secondary. Mobile primary: Today, League, Teams, Players, More (Games, Matchup, Explore, Social). Matchup and Explore entries appear only with their usable phase sections. Search can link directly to a player. MVP leaderboards, recurrence KPIs and matrices analyze regular-season games only; schedule navigation may show other stored game types without merging them into these KPIs. Season/window/filter context should persist during drill-down where practical. A positive recurrence cell can navigate to game and HR event detail. CSV/PDF actions appear only on supported 0.1 analytical views and use shared analytics definitions.

For each analytical screen, desktop presents dense controls and tables; tablet reduces default window/columns with horizontal access; mobile uses smaller default windows, filter sheets and touch targets without discarding underlying information. Text labels and numbers accompany color. Keyboard and screen-reader access apply to all controls, cells and drill-downs.

## Today

- **Purpose / route / phase:** Daily MLB overview; `/today`; 0.1.
- **Information / KPIs:** Today's games, teams, start time/status, recent HR leaders and recurrence indicators; observed HR and labeled derived recurrence candidates.
- **Filters / actions / links:** Date and season; open game, team or player; links to Games, League, Teams, Players.
- **Desktop / tablet / mobile:** Game grid and leader summaries / stacked cards / compact game cards with horizontal leader list.
- **Loading / empty / partial / error:** Skeleton games and leaders / no games scheduled for date / show available games and flag unavailable leader data / retain date and retry each failed section.
- **Future:** 0.2 contact summaries; 0.3 probable pitcher, handedness, park/weather and matchup context; 0.4 validated model output, distinctly labeled.

## League Leaderboard

- **Purpose / route / phase:** Compare production separately from recurrence across MLB; `/league`; 0.1.
- **Information / KPIs:** Player, team, HR, PA, HR/PA, PA/HR, Games With HR %, Player HR — Last 30 Batting Games, median HR gap, Current HR Drought — Batting Games. Production and recurrence are distinct views/column groups; never equate HR leader with recurrence leader.
- **Filters / actions / links:** Season; 7G/15G/30G/60G/Season; league, team, position, bat side, home/away where meaningful; sort, search, CSV/PDF; player/team details.
- **Desktop / tablet / mobile:** Full sortable table with sticky identity / horizontally accessible columns / compact key columns, column chooser and filter sheet; all columns remain reachable.
- **Loading / empty / partial / error:** Table skeleton / no eligible players for filters / show valid rows with missing KPI markers and sample sizes / retry data and preserve controls.
- **Future:** 0.2 observed Statcast columns; 0.4 model outputs only in a separate labeled view.

## Teams

- **Purpose / route / phase:** Discover all 30 MLB franchises; `/teams`; 0.1.
- **Information / KPIs:** Team identity and descriptive season HR, HR/Game, Games With HR % when defined.
- **Filters / actions / links:** Season, league/division and search; sort, open Team Detail; link from League/Today.
- **Desktop / tablet / mobile:** Grid or summary table / two-column cards / single-column cards.
- **Loading / empty / partial / error:** Team placeholders / no matching team / show identities while stats are unavailable / retry list or stats separately.
- **Future:** 0.2 contact quality; 0.3 park context; 0.4 separate validated intelligence.

## Team Detail

- **Purpose / route / phase:** Team overview and hub; `/teams/:teamId`; 0.1.
- **Information / KPIs:** Overview, Players, Games and HR Log sections; season HR, Team HR/Team Game, HR/PA, Games With HR %, Team HR — Last 30 Team Games, multi-HR games, current team HR streak/drought, which may extend before the displayed N-game window.
- **Filters / actions / links:** Season/window, home/away where meaningful; open Team Recurrence, player, game, HR event; export supported views.
- **Desktop / tablet / mobile:** KPI grid and tabbed tables / stacked KPIs and scrollable tabs / compact KPIs and segmented navigation.
- **Loading / empty / partial / error:** Header and panel skeleton / team has no eligible data / keep identity and valid panels with explicit missing panels / retry affected panel.
- **Future:** 0.2 Statcast team profile; 0.3 park/lineup context; 0.4 modeled content clearly separate.

## Team Recurrence

- **Purpose / route / phase:** Interactive player-by-game HR matrix; `/teams/:teamId/recurrence`; 0.1.
- **Information / KPIs:** Rows players, columns distinct team games, fixed Player/Player Season HR (all teams)/Matrix Window HR (selected team games); cells distinguish HR count, known zero, DNP, zero-PA appearance, not-with-team, unknown and incomplete. DNP and not-with-team require affirmative evidence; otherwise the cell is unknown. 0.0-B defines structural states; [WINDOW_SEMANTICS.md](WINDOW_SEMANTICS.md) defines eligibility and display.
- **Filters / actions / links:** 7G/15G/30G/60G/Season, all/home/away; sort rows, scroll games, open positive cell → game/event, open player, CSV/PDF.
- **Desktop / tablet / mobile:** Sticky player/summary columns and horizontal reach to ~30 columns / shorter initial window with horizontal navigation / smallest initial window, sticky identity and touch-friendly cells; full information via scroll/export.
- **Loading / empty / partial / error:** Matrix skeleton preserving headings / no eligible completed games / mark unknown cells and data freshness, never show unknown as 0 / retry matrix while keeping filters.
- **Future:** 0.2 tracked HR-event details; 0.3 contextual overlays only when source/provenance is clear.

## Players

- **Purpose / route / phase:** Find and compare players; `/players`; 0.1.
- **Information / KPIs:** Identity, team, position, bat side, HR, PA and selected production/recurrence columns.
- **Filters / actions / links:** Universal/player search, team, position, bat side, season/window, sort; open Player Detail and League.
- **Desktop / tablet / mobile:** Sortable table / reduced visible columns with access to rest / search-first list, filter sheet and compact stats.
- **Loading / empty / partial / error:** Search/list placeholders / no match / keep identity and flag missing stats / retry preserving query.
- **Future:** 0.2 contact/pitch filters; 0.3 contextual splits; 0.4 separately labeled model insights.

## Player Detail

- **Purpose / route / phase:** Player overview and navigation hub; `/players/:playerId`; 0.1.
- **Information / KPIs:** Name, team, position, bat/throw side; overview with season HR, HR/PA, PA/HR, Games With HR %, Player HR — Last 30 Batting Games, average/median gap, explicitly game- or PA-labeled current/maximum drought, current/maximum streak, multi-HR games. Definitions are in [KPI_SPEC.md](KPI_SPEC.md).
- **Filters / actions / links:** Season/window; open Recurrence, Home Runs, team and game. Only available tabs appear; planned tabs are Overview, Recurrence, Home Runs, Splits, Statcast, Pitch Profile, Matchups.
- **Desktop / tablet / mobile:** Header and KPI groups with tabs / stacked groups / compact identity and scrollable or segmented tabs.
- **Loading / empty / partial / error:** Identity/KPI skeleton / no eligible season data / show known identity and explain unavailable metrics / retry panel.
- **Future:** 0.2 Splits, Statcast, Pitch Profile; 0.3 Matchups; 0.4 clearly differentiated model output.

## Player Recurrence

- **Purpose / route / phase:** Show chronological HR games and gap patterns; `/players/:playerId/recurrence`; 0.1.
- **Information / KPIs:** Batting-game strip with numeric HR counts; HR-game frequency, average/median gap, game drought and streak; gap distribution counts non-HR batting games strictly between HR games.
- **Filters / actions / links:** Season, 7G/15G/30G/60G/Season, home/away where meaningful; inspect game/event, export, return to overview.
- **Desktop / tablet / mobile:** Wide timeline and distribution / shorter default timeline with scroll / compact scrollable strip and accessible detail list.
- **Loading / empty / partial / error:** Timeline skeleton / no relevant games / unknown games shown distinctly from zero HR / retry timeline, preserve window.
- **Future:** 0.2 tracked-event annotation; 0.3 contextual comparison; no 0.1 predictions.

## Player HR Log

- **Purpose / route / phase:** Event-level evidence behind counts; `/players/:playerId/home-runs`; 0.1.
- **Information / KPIs:** Date, opponent, home/away, pitcher when available, game and HR event; count of events in selected window.
- **Filters / actions / links:** Season/window and home/away; sort, open game/event, CSV, return to player. An opponent analytical filter needs an explicit future window rule before it can be offered.
- **Desktop / tablet / mobile:** Event table / horizontally accessible table / event cards with same fields in detail.
- **Loading / empty / partial / error:** Event placeholders / no HR events in selected scope / mark missing pitcher or source details / retry event list.
- **Future:** 0.2 exit velocity, launch angle, distance, pitch type/velocity if verified and matched; 0.3 context.

## Games

- **Purpose / route / phase:** Navigate Today, Schedule, and Completed games; `/games`; 0.1.
- **Information / KPIs:** Date, teams, start/status, final score where available, HR count for completed games.
- **Filters / actions / links:** Date range, team, status; open Game Detail, Today, team.
- **Desktop / tablet / mobile:** Date-grouped list/table / condensed list / game cards.
- **Loading / empty / partial / error:** Schedule placeholders / no games matching date/filter / show schedule while scores or HR data lag / retry affected date.
- **Future:** 0.2 tracked events; 0.3 probable pitcher, park/weather; 0.4 model content in separate labeled section.

## Game Detail

- **Purpose / route / phase:** Explain the game behind HR counts and matrix cells; `/games/:gameId`; 0.1.
- **Information / KPIs:** Teams, score, status, participants, batters and pitchers where available, and HR events with game context. A completed game's HR count requires complete HR-event coverage; incomplete data must be labeled.
- **Filters / actions / links:** Event view/filter by team; open player, team, HR event/source detail when available; return to Games or matrix.
- **Desktop / tablet / mobile:** Score header and parallel team/event panels / stacked panels / compact score and chronological events.
- **Loading / empty / partial / error:** Game header skeleton / no HR events or no eligible game / show known score/status and flag unavailable participant/batter/pitcher/event sections / retry affected section.
- **Future:** Starting-lineup detail if verified; 0.2 Statcast pitch and batted-ball details; 0.3 contextual matchup/weather; 0.4 labeled validated estimates.

## Matchup Lab

- **Purpose / route / phase:** Evidence-based batter versus pitcher investigation; `/matchup`; 0.3. Planned navigation location may be documented earlier without a working 0.1 screen.
- **Information / KPIs:** Batter/pitcher profiles, handedness, direct history, arsenal and usage, pitch-type/velocity-specific observed performance, pitcher HR allowed and contact allowed, park, weather, roof, sample sizes.
- **Filters / actions / links:** Select batter and pitcher; season/window, pitch type, hand, velocity band where valid; open player/game and source evidence.
- **Desktop / tablet / mobile:** Side-by-side profiles and evidence panels / stacked comparison / guided selections and collapsible evidence with all facts reachable.
- **Loading / empty / partial / error:** Profile/evidence skeleton / choose both participants or no matched events / show independently available factors and missing-data labels / retry affected provider-backed panels.
- **Future:** 0.4 separate explainable, calibrated ratings/probabilities; no arbitrary score in 0.3.

## Explore

- **Purpose / route / phase:** Cross-player analytical exploration; `/explore`; 0.2 initial observed Statcast sections, expanded in 0.3. Planned location may exist in the map before launch.
- **Information / KPIs:** 0.2 pitch types, handedness splits and contact trends; 0.3 parks and contextual splits. Use observed and derived labels with sample sizes.
- **Filters / actions / links:** Season/window, player/team, hand, pitch type and relevant velocity band; sort, inspect player/game/source.
- **Desktop / tablet / mobile:** Faceted tables/charts / stacked charts and filter drawer / single-column charts, filter sheet and accessible data table.
- **Loading / empty / partial / error:** Chart/table placeholders / no qualified records / flag partial coverage and denominators / retry affected exploration panel.
- **Future:** 0.4 model exploration only in a distinct validated section.

## Social

- **Purpose / route / phase:** Optional public X-source viewing; `/social`; post-0.1 auxiliary release, scheduled no earlier than 0.3 and independent of analytics milestones.
- **Information / KPIs:** Admin-configured public sources and official embedded timelines; no MLB KPI is computed from social content.
- **Filters / actions / links:** Select source; open external source; secondary navigation only.
- **Desktop / tablet / mobile:** Multi-source layout / stacked embeds / one source at a time with touch-friendly selector.
- **Loading / empty / partial / error:** Isolated embed loading / no sources configured / show available sources if one embed fails / local fallback and retry; failures cannot block core screens or APIs.
- **Future:** Additional sources only after product/legal review; no paid X API is required for the initial concept.

## Django Administration

- **Purpose / route / phase:** Staff inspection and configuration; `/admin/`; 0.1 initial data inspection, extended with each relevant phase. Not part of consumer primary navigation.
- **Information / KPIs:** Seasons, teams, players, games, venues, provider records, sync runs/errors/raw imports; later X sources, settings and feature flags. Provider records are imported, generally read-only source records; data authority by category is determined during 0.0-D.
- **Filters / actions / links:** Staff search/filter and permitted configuration; inspect provenance and sync status; link to relevant public entity where appropriate.
- **Desktop / tablet / mobile:** Standard admin tables/forms / responsive admin layouts / essential inspection and configuration, with horizontal access for dense tables.
- **Loading / empty / partial / error:** Admin loading feedback / no records yet / show available records and import errors / explicit failure and retry for read actions.
- **Future:** 0.2 Statcast provider/coverage, 0.3 weather/park and X sources, 0.4 model governance; exact admin data model belongs to 0.0-B and later phases.
