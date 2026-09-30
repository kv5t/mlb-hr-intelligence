import { lazy, Suspense } from 'react'
import { InitialLoading } from '@/components/PageStates'
import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/app/AppShell'
import { NotFound } from '@/app/RoutePlaceholder'
import { GameDetailPage } from '@/screens/GameDetailPage'
import { GamesPage } from '@/screens/GamesPage'
import { LeaguePage } from '@/screens/LeaguePage'
import { PlayersPage } from '@/screens/PlayersPage'
import { TodayPage } from '@/screens/TodayPage'
import { TeamsPage } from '@/screens/TeamsPage'
import { TeamDetailPage } from '@/screens/TeamDetailPage'
const TeamRecurrencePage = lazy(() => import('@/screens/TeamRecurrencePage').then((module) => ({ default: module.TeamRecurrencePage })))
const PlayerDetailPage = lazy(() => import('@/screens/PlayerDetailPage').then((module) => ({ default: module.PlayerDetailPage })))
const PlayerRecurrencePage = lazy(() => import('@/screens/PlayerRecurrencePage').then((module) => ({ default: module.PlayerRecurrencePage })))
const PlayerHomeRunsPage = lazy(() => import('@/screens/PlayerHomeRunsPage').then((module) => ({ default: module.PlayerHomeRunsPage })))

export default function App() {
  return (
    <Suspense fallback={<InitialLoading label="Loading page" />}><Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate replace to="/today" />} />
        <Route path="today" element={<TodayPage />} />
        <Route path="league" element={<LeaguePage />} />
        <Route path="teams" element={<TeamsPage />} />
        <Route path="teams/:teamId" element={<TeamDetailPage />} />
        <Route path="teams/:teamId/recurrence" element={<TeamRecurrencePage />} />
        <Route path="players" element={<PlayersPage />} />
        <Route path="players/:playerId" element={<PlayerDetailPage />} />
        <Route path="players/:playerId/recurrence" element={<PlayerRecurrencePage />} />
        <Route path="players/:playerId/home-runs" element={<PlayerHomeRunsPage />} />
        <Route path="games" element={<GamesPage />} />
        <Route path="games/:gameId" element={<GameDetailPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes></Suspense>
  )
}
