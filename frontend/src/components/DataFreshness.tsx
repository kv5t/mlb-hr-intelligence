import type { Meta } from '@/api'

export function DataFreshness({ meta }: { meta: Meta }) {
  const instant = new Date(meta.data_as_of)
  const label = Number.isNaN(instant.valueOf())
    ? meta.data_as_of
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(instant)
  return (
    <p className="text-xs text-muted-foreground" title={`Dataset revision ${meta.dataset_revision}`}>
      Data as of {label} UTC <span className="sr-only">at dataset revision {meta.dataset_revision}</span>
    </p>
  )
}
