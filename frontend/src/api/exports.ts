import { ApiClientError } from './errors'
import { apiErrorEnvelopeSchema } from './schemas'
import { playerLeaderboardParamsSchema, teamDetailParamsSchema, teamHomeRunsParamsSchema, playerDetailParamsSchema, playerHomeRunsParamsSchema, queryString, isCanonicalUuid } from './params'

export type ExportKind = 'leaderboard' | 'teamRecurrence' | 'playerRecurrence' | 'teamHomeRuns' | 'playerHomeRuns'
export type ExportFormat = 'csv' | 'pdf'
export type ExportTarget = { kind: ExportKind; id?: string; params: Record<string, unknown> }

export function exportRequest(target: ExportTarget, format: ExportFormat) {
  const schemas = {
    leaderboard: playerLeaderboardParamsSchema.omit({ page: true, page_size: true }),
    teamRecurrence: teamDetailParamsSchema,
    playerRecurrence: playerDetailParamsSchema,
    teamHomeRuns: teamHomeRunsParamsSchema.omit({ page: true, page_size: true }),
    playerHomeRuns: playerHomeRunsParamsSchema.omit({ page: true, page_size: true }),
  }
  const params = schemas[target.kind].parse(target.params)
  if (target.kind !== 'leaderboard' && !isCanonicalUuid(target.id ?? '')) throw new ApiClientError({ kind: 'api', code: 'INVALID_FILTER', status: 400, message: 'A canonical export subject ID is required.' })
  const paths = {
    leaderboard: 'leaderboards/players/', teamRecurrence: `teams/${target.id}/recurrence/`, playerRecurrence: `players/${target.id}/recurrence/`, teamHomeRuns: `teams/${target.id}/home-runs/`, playerHomeRuns: `players/${target.id}/home-runs/`,
  }
  return { url: `/api/v1/exports/${paths[target.kind]}?${queryString({ ...params, format })}`, mime: format === 'csv' ? 'text/csv' : 'application/pdf' }
}

export async function downloadExport(target: ExportTarget, format: ExportFormat, signal?: AbortSignal) {
  const { url, mime } = exportRequest(target, format)
  let response: Response
  try { response = await fetch(url, { method: 'GET', headers: { Accept: mime }, signal }) }
  catch (cause) { throw new ApiClientError({ kind: 'network', code: 'NETWORK_ERROR', message: 'The export service could not be reached.', cause }) }
  if (!response.ok) {
    let payload: unknown
    try { payload = JSON.parse(await response.text()) } catch { payload = null }
    const parsed = apiErrorEnvelopeSchema.safeParse(payload)
    throw new ApiClientError({ kind: 'api', status: response.status, code: parsed.success ? parsed.data.error.code : 'INVALID_ERROR_RESPONSE', message: parsed.success ? parsed.data.error.message : 'The export failed with an invalid error response.', details: parsed.success ? parsed.data.error.details : {}, meta: parsed.success && parsed.data.meta.dataset_revision && parsed.data.meta.data_as_of ? { dataset_revision: parsed.data.meta.dataset_revision, data_as_of: parsed.data.meta.data_as_of } : null })
  }
  if (response.headers.get('Content-Type')?.split(';')[0].trim() !== mime) throw new ApiClientError({ kind: 'schema', code: 'INVALID_EXPORT_CONTENT', message: 'The export service returned an unexpected file type.' })
  let blob: Blob
  try { blob = await response.blob() } catch (cause) { throw new ApiClientError({ kind: 'network', code: 'DOWNLOAD_FAILED', message: 'The export download was interrupted.', cause }) }
  // Check PDF signature as well as MIME; never download JSON disguised as PDF.
  if (blob.size === 0 || (format === 'pdf' && await blob.slice(0, 5).text() !== '%PDF-')) throw new ApiClientError({ kind: 'schema', code: 'INVALID_EXPORT_CONTENT', message: 'The export service returned an invalid file.' })
  const supplied = response.headers.get('Content-Disposition')?.match(/filename="?([A-Za-z0-9._-]+)"?(?:;|$)/i)?.[1]
  const filename = supplied?.endsWith(`.${format}`) ? supplied : `mlb-${target.kind}.${format}`
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  try { link.href = objectUrl; link.download = filename; document.body.append(link); link.click() }
  finally { link.remove(); URL.revokeObjectURL(objectUrl) }
  return { filename, revision: response.headers.get('X-Dataset-Revision'), dataAsOf: response.headers.get('X-Data-As-Of') }
}
