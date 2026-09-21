import type { ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'

import { parseUrlState } from './urlState'

export function UrlStateBoundary({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const parsed = parseUrlState(searchParams)
  if (parsed.issues.length === 0) return children
  return (
    <section aria-labelledby="invalid-url-title" className="rounded-lg border border-amber-300 bg-amber-50 p-5 text-amber-950">
      <h2 id="invalid-url-title" className="font-semibold">Some URL filters are invalid</h2>
      <ul className="mt-2 list-disc pl-5 text-sm">
        {parsed.issues.map((issue) => <li key={`${issue.key}:${issue.value}`}>{issue.key}: {issue.message}</li>)}
      </ul>
      <button
        className="mt-4 rounded-md bg-amber-950 px-3 py-2 text-sm font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2"
        onClick={() => setSearchParams(parsed.validParams, { replace: true })}
        type="button"
      >
        Remove invalid filters
      </button>
    </section>
  )
}
