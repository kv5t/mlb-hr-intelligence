import { useRef, useState } from 'react'
import { downloadExport, type ExportTarget, type ExportFormat } from '@/api/exports'
import { ErrorState } from './PageStates'

export function ExportActions({ target }: { target: ExportTarget }) {
  const active = useRef(new Set<ExportFormat>())
  const [pending, setPending] = useState<Partial<Record<ExportFormat, boolean>>>({})
  const [errors, setErrors] = useState<Partial<Record<ExportFormat, unknown>>>({})
  const [success, setSuccess] = useState<string | null>(null)
  const download = async (format: ExportFormat) => {
    if (active.current.has(format)) return
    active.current.add(format); setPending((state) => ({ ...state, [format]: true })); setErrors((state) => ({ ...state, [format]: null })); setSuccess(null)
    try { const result = await downloadExport(target, format); setSuccess(`Downloaded ${result.filename}${result.revision ? ` · dataset revision ${result.revision}` : ''}`) }
    catch (error) { setErrors((state) => ({ ...state, [format]: error })) }
    finally { active.current.delete(format); setPending((state) => ({ ...state, [format]: false })) }
  }
  return <section aria-label="Export selected view" className="space-y-2"><div className="flex flex-wrap gap-2">{(['csv', 'pdf'] as const).map((format) => <button className="min-h-11 rounded-md border px-4 text-sm disabled:opacity-50" disabled={pending[format]} key={format} onClick={() => void download(format)} type="button">{pending[format] ? `Preparing ${format.toUpperCase()}…` : `Export ${format.toUpperCase()}`}</button>)}</div>{Object.entries(errors).map(([format, error]) => error ? <ErrorState error={error} key={format} onRetry={() => void download(format as ExportFormat)} /> : null)}{success ? <p className="text-sm" role="status">{success}</p> : null}</section>
}
