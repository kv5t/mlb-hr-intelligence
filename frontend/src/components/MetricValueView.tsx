import type { MetricValue } from '@/api'

const stateText = {
  NOT_APPLICABLE: '—',
  UNKNOWN: 'Unknown',
  INCOMPLETE: 'Partial data',
  ORDER_UNVERIFIED: 'Order unverified',
  INSUFFICIENT_HISTORY: 'Not enough history',
} as const

const reasonText: Record<string, string> = {
  NO_HR_IN_SCOPE: 'No home runs in scope',
  NO_GAMES: 'No eligible games',
  ZERO_DENOMINATOR: 'No eligible denominator',
}

export function MetricValueView({ metric, label }: { metric: MetricValue; label: string }) {
  const display = metric.state === 'VALUE' ? String(metric.value) : stateText[metric.state]
  const reason = metric.reason ? (reasonText[metric.reason] ?? metric.reason.replaceAll('_', ' ').toLowerCase()) : null
  const accessible = `${label}: ${display}${metric.unit ? ` ${metric.unit}` : ''}${reason ? `. ${reason}` : ''}`
  return (
    <span aria-label={accessible} className="inline-flex items-center gap-2">
      <span>{display}</span>
      {metric.unit && metric.state === 'VALUE' ? <span className="text-xs text-muted-foreground">{metric.unit}</span> : null}
      {reason ? <span aria-hidden="true" className="text-xs text-muted-foreground" title={reason}>ⓘ</span> : null}
      {reason ? <span className="sr-only">{reason}</span> : null}
    </span>
  )
}
