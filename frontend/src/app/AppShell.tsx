import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'

const core = [
  ['Today', '/today'],
  ['League', '/league'],
  ['Teams', '/teams'],
  ['Players', '/players'],
  ['Games', '/games'],
] as const

function CoreLink({ label, to }: { label: string; to: string }) {
  return (
    <NavLink
      className={({ isActive }) =>
        `rounded-md px-3 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 ${
          isActive ? 'bg-primary text-primary-foreground underline decoration-2 underline-offset-4' : 'hover:bg-muted'
        }`
      }
      to={to}
    >
      {({ isActive }) => <>{label}{isActive ? <span className="sr-only">, current page</span> : null}</>}
    </NavLink>
  )
}

function FutureDestination({ children, compactHidden = false }: { children: string; compactHidden?: boolean }) {
  return <span aria-disabled="true" className={`${compactHidden ? 'hidden lg:inline-flex' : ''} cursor-not-allowed px-3 py-2 text-sm text-muted-foreground`}>{children} <span className="sr-only">unavailable</span></span>
}

export function AppShell() {
  const [moreOpen, setMoreOpen] = useState(false)
  return (
    <div className="min-h-svh bg-background text-foreground">
      <a className="sr-only z-50 rounded bg-background p-3 focus:not-sr-only focus:fixed focus:left-3 focus:top-3" href="#main-content">Skip to content</a>
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link className="font-semibold tracking-tight focus-visible:outline-2 focus-visible:outline-offset-2" to="/today">MLB HR Intelligence</Link>
          <nav aria-label="Primary" className="hidden items-center gap-1 md:flex">
            {core.map(([label, to]) => <CoreLink key={to} label={label} to={to} />)}
            <FutureDestination compactHidden>Matchup</FutureDestination>
            <FutureDestination compactHidden>Explore</FutureDestination>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8 pb-24 sm:px-6 md:pb-8" id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
      <nav aria-label="Mobile primary" className="fixed inset-x-0 bottom-0 z-40 border-t bg-background p-2 md:hidden">
        <div className="mx-auto grid max-w-lg grid-cols-5 gap-1">
          {core.slice(0, 4).map(([label, to]) => <CoreLink key={to} label={label} to={to} />)}
          <div className="relative">
            <button
              aria-expanded={moreOpen}
              aria-label="More navigation"
              className="w-full rounded-md px-3 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2"
              onClick={() => setMoreOpen((open) => !open)}
              type="button"
            >More</button>
            {moreOpen ? (
              <div className="absolute bottom-full right-0 mb-3 min-w-44 rounded-lg border bg-card p-2 shadow-lg">
                <CoreLink label="Games" to="/games" />
                <div className="mt-1 flex flex-col border-t pt-1">
                  <FutureDestination>Matchup</FutureDestination>
                  <FutureDestination>Explore</FutureDestination>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </nav>
    </div>
  )
}
