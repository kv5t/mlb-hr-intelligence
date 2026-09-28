import { Link, useSearchParams } from 'react-router-dom'

import { useSeasons, useTeams, type TeamsParams } from '@/api'
import { DataFreshness } from '@/components/DataFreshness'
import { EmptyState, ErrorState, InitialLoading, RefreshingStatus } from '@/components/PageStates'
import { UrlStateBoundary } from '@/routing/UrlStateBoundary'
import { parseUrlState, updateUrlState, type UrlStateKey } from '@/routing/urlState'

export function TeamsPage() {
  const [searchParams] = useSearchParams()
  const parsed = parseUrlState(searchParams, 'teams')
  if (parsed.issues.length) return <UrlStateBoundary route="teams"><span /></UrlStateBoundary>
  const params: TeamsParams = {
    season: parsed.state.season ? Number(parsed.state.season) : undefined,
    league: parsed.state.league,
    division: parsed.state.division,
    search: parsed.state.search,
    ordering: parsed.state.ordering as TeamsParams['ordering'],
    page: parsed.state.page ? Number(parsed.state.page) : undefined,
    page_size: parsed.state.page_size ? Number(parsed.state.page_size) : undefined,
  }
  return <TeamsContent params={params} />
}

function TeamsContent({ params }: { params: TeamsParams }) {
  const teams = useTeams(params)
  const seasons = useSeasons({ page_size: 100 })
  const [searchParams, setSearchParams] = useSearchParams()
  const change = (key: UrlStateKey, value: string | null, resetPage = true) =>
    setSearchParams(updateUrlState(searchParams, { [key]: value, ...(resetPage ? { page: '1' } : {}) }))
  const page = params.page ?? 1
  const detailSearch = params.season ? `?season=${params.season}` : ''
  return (
    <div className="space-y-7">
      <header><h1 className="text-3xl font-semibold tracking-tight">Teams</h1><p className="mt-2 max-w-2xl text-sm text-muted-foreground">Browse canonical team identities and sourced season associations.</p></header>
      <section aria-label="Team discovery filters" className="grid gap-3 rounded-xl border bg-muted/30 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <div><label className="text-sm font-medium" htmlFor="teams-season">Season</label><select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" id="teams-season" onChange={(event) => change('season', event.target.value || null)} value={params.season ?? ''}><option value="">All seasons</option>{seasons.data?.results.map((season) => <option key={season.id} value={season.year}>{season.label ?? season.year}</option>)}</select>{seasons.isPending ? <span className="text-xs text-muted-foreground">Loading season options…</span> : null}{seasons.error ? <button className="block text-xs font-medium text-destructive underline" onClick={() => void seasons.refetch()} type="button">Season options unavailable. Retry</button> : null}</div>
        <label className="text-sm font-medium">League<input className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('league', event.target.value || null)} value={params.league ?? ''} /></label>
        <label className="text-sm font-medium">Division<input className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('division', event.target.value || null)} value={params.division ?? ''} /></label>
        <label className="text-sm font-medium">Search<input className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('search', event.target.value || null)} type="search" value={params.search ?? ''} /></label>
        <label className="text-sm font-medium">Order<select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('ordering', event.target.value)} value={params.ordering ?? 'name'}><option value="name">Name A–Z</option><option value="-name">Name Z–A</option><option value="abbreviation">Abbreviation A–Z</option><option value="-abbreviation">Abbreviation Z–A</option></select></label>
      </section>
      {teams.isPending ? <InitialLoading label="Loading teams" /> : null}
      {teams.error ? <ErrorState error={teams.error} onRetry={() => void teams.refetch()} /> : null}
      {teams.data ? <>{teams.isFetching ? <RefreshingStatus /> : null}{teams.data.results.length ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{teams.data.results.map((team) => <article className="rounded-xl border p-5" key={team.id}><h2 className="font-semibold"><Link className="underline underline-offset-4" to={`/teams/${team.id}${detailSearch}`}>{team.display_name ?? 'Unknown team'}</Link></h2><p className="mt-1 text-sm text-muted-foreground">{team.abbreviation ?? 'No abbreviation'} · {[team.league, team.division].filter(Boolean).join(' · ') || 'League/division unavailable'}</p></article>)}</div> : <EmptyState>No teams match these filters.</EmptyState>}<nav aria-label="Teams pagination" className="flex items-center justify-between gap-3"><p className="text-sm text-muted-foreground">{teams.data.count} teams</p><div className="flex gap-2"><button className="min-h-11 rounded-md border px-4 disabled:opacity-50" disabled={!teams.data.previous} onClick={() => change('page', String(page - 1), false)} type="button">Previous</button><button className="min-h-11 rounded-md border px-4 disabled:opacity-50" disabled={!teams.data.next} onClick={() => change('page', String(page + 1), false)} type="button">Next</button></div></nav><DataFreshness meta={teams.data.meta} /></> : null}
    </div>
  )
}
