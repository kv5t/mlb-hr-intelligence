import { Link, type LinkProps } from 'react-router-dom'

import type { GameSummary } from '@/api'
import { formatGameStart } from '@/components/gamePresentation'
import { MetricValueView } from '@/components/MetricValueView'

function teamName(game: GameSummary, side: 'home' | 'away') {
  const team = side === 'home' ? game.home_team : game.away_team
  return team.abbreviation ?? team.display_name ?? 'Unknown team'
}

export function GameScore({ game }: { game: GameSummary }) {
  if (game.away_score === null || game.home_score === null) {
    return <span className="text-sm text-muted-foreground">Score unavailable</span>
  }
  return <span className="tabular-nums font-semibold">{game.away_score}–{game.home_score}</span>
}

export function GameTeams({ game, linked = true }: { game: GameSummary; linked?: boolean }) {
  const content = (side: 'away' | 'home') => {
    const team = side === 'away' ? game.away_team : game.home_team
    const name = teamName(game, side)
    return linked ? <Link className="underline-offset-4 hover:underline" to={`/teams/${team.id}`}>{name}</Link> : name
  }
  return <span className="font-medium">{content('away')} <span aria-label="at" className="text-muted-foreground">@</span> {content('home')}</span>
}

export function GameSummaryCard({ game, from }: { game: GameSummary; from: string }) {
  const linkState: LinkProps['state'] = { from }
  return (
    <article className="rounded-xl border bg-card p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <GameTeams game={game} />
          <p className="mt-1 text-sm text-muted-foreground">{game.status.replaceAll('_', ' ')} · {formatGameStart(game)}</p>
        </div>
        <GameScore game={game} />
      </div>
      <div className="mt-4 flex items-center justify-between border-t pt-3">
        <span className="text-sm text-muted-foreground">Home runs</span>
        <MetricValueView label="Game home runs" metric={game.hr_count} />
      </div>
      <Link className="mt-4 inline-flex min-h-11 items-center rounded-md bg-secondary px-4 text-sm font-medium hover:bg-accent" state={linkState} to={`/games/${game.id}`}>
        Open game
      </Link>
    </article>
  )
}
