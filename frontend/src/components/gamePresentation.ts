import type { GameSummary } from '@/api'

export function formatGameStart(game: GameSummary): string {
  if (!game.scheduled_start_at_utc) return 'Start time unknown'
  const instant = new Date(game.scheduled_start_at_utc)
  if (Number.isNaN(instant.valueOf())) return 'Start time unknown'
  const requestedZone = game.venue?.timezone_id
  if (requestedZone) {
    try {
      const formatted = new Intl.DateTimeFormat(undefined, {
        hour: 'numeric', minute: '2-digit', timeZone: requestedZone, timeZoneName: 'short',
      }).format(instant)
      return `${formatted} · venue time`
    } catch {
      // Invalid provider timezone falls back to an explicitly labelled UTC time.
    }
  }
  return `${new Intl.DateTimeFormat(undefined, {
    hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC',
  }).format(instant)} UTC`
}
