import type { SeasonSummary, TeamSummary } from '@/api'
import { HOME_AWAY, WINDOWS } from '@/api'
import type { UrlState, UrlStateKey } from '@/routing/urlState'

function DiscoveryIssue({
  label,
  error,
  retry,
}: {
  label: string
  error: unknown
  retry: () => void
}) {
  if (!error) return null
  return (
    <span className="mt-1 flex items-center gap-2 text-xs text-destructive" role="alert">
      {label} options unavailable.
      <button className="font-medium underline underline-offset-2" onClick={retry} type="button">
        Retry
      </button>
    </span>
  )
}

export function PlayerAnalyticsFilters({
  state,
  seasons,
  teams,
  seasonsPending,
  teamsPending,
  seasonsError,
  teamsError,
  retrySeasons,
  retryTeams,
  change,
}: {
  state: UrlState
  seasons: SeasonSummary[]
  teams: TeamSummary[]
  seasonsPending: boolean
  teamsPending: boolean
  seasonsError: unknown
  teamsError: unknown
  retrySeasons: () => void
  retryTeams: () => void
  change: (key: UrlStateKey, value: string | null, resetPage?: boolean) => void
}) {
  const selectedTeamKnown = teams.some((team) => team.id === state.team)
  return (
    <section aria-label="Player analytics filters" className="grid gap-3 rounded-xl border bg-muted/30 p-4 sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <label className="text-sm font-medium" htmlFor="player-season">Season</label>
        <select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" id="player-season" onChange={(event) => change('season', event.target.value)} value={state.season ?? ''}>
          <option disabled value="">{seasonsPending ? 'Loading seasons…' : seasonsError ? 'Season options unavailable' : 'Choose season'}</option>
          {seasons.map((season) => <option key={season.id} value={season.year}>{season.label ?? season.year}</option>)}
        </select>
        <DiscoveryIssue error={seasonsError} label="Season" retry={retrySeasons} />
      </div>
      <label className="text-sm font-medium">Window
        <select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('window', event.target.value)} value={state.window ?? 'SEASON'}>
          {WINDOWS.map((window) => <option key={window} value={window}>{window === 'SEASON' ? 'Season' : window}</option>)}
        </select>
      </label>
      <div>
        <label className="text-sm font-medium" htmlFor="player-team">Team</label>
        <select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" id="player-team" onChange={(event) => change('team', event.target.value || null)} value={state.team ?? ''}>
          <option value="">{teamsPending ? 'Loading teams…' : teamsError ? 'Team options unavailable' : 'All teams'}</option>
          {state.team && !selectedTeamKnown ? <option value={state.team}>Selected team</option> : null}
          {teams.map((team) => <option key={team.id} value={team.id}>{team.display_name ?? team.abbreviation ?? 'Unknown team'}</option>)}
        </select>
        <DiscoveryIssue error={teamsError} label="Team" retry={retryTeams} />
      </div>
      <label className="text-sm font-medium">Home / away
        <select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('home_away', event.target.value)} value={state.home_away ?? 'ALL'}>
          {HOME_AWAY.map((value) => <option key={value} value={value}>{value === 'ALL' ? 'All' : value === 'HOME' ? 'Home' : 'Away'}</option>)}
        </select>
      </label>
      <label className="text-sm font-medium">Search
        <input className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('search', event.target.value || null)} placeholder="Player name" type="search" value={state.search ?? ''} />
      </label>
      <label className="text-sm font-medium">Position
        <input className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('position', event.target.value || null)} placeholder="Position" value={state.position ?? ''} />
      </label>
      <label className="text-sm font-medium">Bat side
        <select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('bats', event.target.value || null)} value={state.bats ?? ''}>
          <option value="">All</option>
          <option value="L">Left</option><option value="R">Right</option><option value="S">Switch</option><option value="UNKNOWN">Unknown</option>
        </select>
      </label>
      <label className="text-sm font-medium">Cutoff date
        <input className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('cutoff', event.target.value || null)} type="date" value={state.cutoff ?? ''} />
      </label>
    </section>
  )
}
