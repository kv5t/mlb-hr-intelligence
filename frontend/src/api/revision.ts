import type { Meta } from './types'

export function shareDatasetRevision(...values: Array<{ meta: Meta } | Meta>): boolean {
  if (values.length < 2) return true
  const revisions = values.map((value) => ('meta' in value ? value.meta : value).dataset_revision)
  return revisions.every((revision) => revision === revisions[0])
}
