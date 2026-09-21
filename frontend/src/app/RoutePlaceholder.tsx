import { Link } from 'react-router-dom'

import { UrlStateBoundary } from '@/routing/UrlStateBoundary'

export function RoutePlaceholder({ title }: { title: string }) {
  return (
    <UrlStateBoundary>
      <section aria-labelledby="page-title">
        <p className="text-sm font-medium text-muted-foreground">MVP 0.1</p>
        <h1 className="mt-1 text-2xl font-semibold" id="page-title">{title}</h1>
        <p className="mt-3 max-w-prose text-muted-foreground">This route is ready for its scheduled vertical slice.</p>
      </section>
    </UrlStateBoundary>
  )
}

export function NotFound() {
  return (
    <section>
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="mt-2 text-muted-foreground">The requested page is not part of MLB HR Intelligence.</p>
      <Link className="mt-4 inline-block underline" to="/today">Go to Today</Link>
    </section>
  )
}
