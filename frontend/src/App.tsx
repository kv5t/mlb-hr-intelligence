import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/app/AppShell'
import { NotFound, RoutePlaceholder } from '@/app/RoutePlaceholder'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate replace to="/today" />} />
        <Route path="today" element={<RoutePlaceholder title="Today" />} />
        <Route path="league" element={<RoutePlaceholder title="League" />} />
        <Route path="teams" element={<RoutePlaceholder title="Teams" />} />
        <Route path="teams/:teamId" element={<RoutePlaceholder title="Team detail" />} />
        <Route path="teams/:teamId/recurrence" element={<RoutePlaceholder title="Team recurrence" />} />
        <Route path="players" element={<RoutePlaceholder title="Players" />} />
        <Route path="players/:playerId" element={<RoutePlaceholder title="Player detail" />} />
        <Route path="players/:playerId/recurrence" element={<RoutePlaceholder title="Player recurrence" />} />
        <Route path="players/:playerId/home-runs" element={<RoutePlaceholder title="Player home runs" />} />
        <Route path="games" element={<RoutePlaceholder title="Games" />} />
        <Route path="games/:gameId" element={<RoutePlaceholder title="Game detail" />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
