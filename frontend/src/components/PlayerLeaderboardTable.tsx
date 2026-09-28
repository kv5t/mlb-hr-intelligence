import { createColumnHelper, tableFeatures, useTable } from '@tanstack/react-table'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { LeaderboardRow, MetricValue, PlayerLeaderboardParams } from '@/api'
import { MetricValueView } from '@/components/MetricValueView'

type Ordering = NonNullable<PlayerLeaderboardParams['ordering']>
type SortField = Ordering extends `-${infer Field}` ? Field : Ordering

const features = tableFeatures({})
const column = createColumnHelper<typeof features, LeaderboardRow>()

function MetricCell({ row, id, label }: { row: LeaderboardRow; id: string; label: string }) {
  const metric = row.metrics[id] as MetricValue
  return (
    <span className="block min-w-24">
      <MetricValueView label={label} metric={metric} />
      {metric.numerator !== null && metric.denominator !== null ? <span className="block text-xs text-muted-foreground">{metric.numerator} / {metric.denominator}</span> : null}
    </span>
  )
}

function SortHeader({ field, label, ordering, onSort }: { field: SortField; label: string; ordering?: Ordering; onSort: (field: SortField) => void }) {
  const direction = ordering === field ? 'ascending' : ordering === `-${field}` ? 'descending' : 'none'
  return (
    <button aria-label={`Sort by ${label}`} className="inline-flex min-h-11 items-center gap-1" onClick={() => onSort(field)} type="button">
      {label}
      {direction === 'ascending' ? <ArrowUp aria-hidden className="size-4" /> : direction === 'descending' ? <ArrowDown aria-hidden className="size-4" /> : <ArrowUpDown aria-hidden className="size-4" />}
    </button>
  )
}

export function PlayerLeaderboardTable({ rows, ordering, onSort, compact = false }: { rows: LeaderboardRow[]; ordering?: Ordering; onSort?: (field: SortField) => void; compact?: boolean }) {
  const metric = (id: string, label: string, field: SortField) => column.display({
    id: field,
    header: () => onSort ? <SortHeader field={field} label={label} onSort={onSort} ordering={ordering} /> : label,
    cell: ({ row }) => <MetricCell id={id} label={label} row={row.original} />,
  })
  const columns = column.columns([
    column.display({ id: 'name', header: () => onSort ? <SortHeader field="name" label="Player" onSort={onSort} ordering={ordering} /> : 'Player', cell: ({ row }) => <Link className="font-medium underline underline-offset-4" to={`/players/${row.original.player.id}`}>{row.original.player.display_name ?? 'Unknown player'}</Link> }),
    ...(rows.some((row) => row.player.represented_team) ? [column.display({ id: 'team', header: 'Represented team', cell: ({ row }) => row.original.player.represented_team?.abbreviation ?? row.original.player.represented_team?.display_name })] : []),
    metric('player.hr', 'HR', 'hr'),
    ...(compact ? [] : [metric('player.pa', 'PA', 'pa'), metric('player.hr_per_pa', 'HR / PA', 'hr_per_pa'), metric('player.pa_per_hr', 'PA / HR', 'pa_per_hr')]),
    metric('player.hr_per_game', 'HR / Game', 'hr_per_game'),
    metric('player.hr_game_pct', 'Games with HR %', 'hr_game_pct'),
    metric('player.median_hr_gap_games', 'Median HR gap', 'median_hr_gap_games'),
    metric('player.current_hr_drought_games', 'Current HR drought', 'current_hr_drought_games'),
    column.display({ id: 'sample', header: 'Actual batting-game sample', cell: ({ row }) => row.original.scope.actual_game_count === null ? `${row.original.scope.known_eligible_game_count} known; ${row.original.scope.selection_state.replaceAll('_', ' ').toLowerCase()}` : `${row.original.scope.actual_game_count} batting games available` }),
  ])
  const table = useTable({ data: rows, columns, features })
  const sortField = ordering?.replace(/^-/, '')
  const sortDirection = ordering?.startsWith('-') ? 'descending' : 'ascending'
  return (
    <div className="overflow-x-auto rounded-xl border">
      <table className="w-full min-w-max border-collapse text-left text-sm">
        <caption className="sr-only">Player analytics in server-provided order</caption>
        <thead className="bg-muted/60">
          {table.getHeaderGroups().map((group) => <tr key={group.id}>{group.headers.map((header) => <th aria-sort={header.id === sortField ? sortDirection : undefined} className="whitespace-nowrap px-4 py-2 font-medium first:sticky first:left-0 first:z-10 first:bg-muted" key={header.id} scope="col">{header.isPlaceholder ? null : <table.FlexRender header={header} />}</th>)}</tr>)}
        </thead>
        <tbody>{table.getRowModel().rows.map((row) => <tr className="border-t" key={row.original.player.id}>{row.getAllCells().map((cell) => <td className="px-4 py-3 align-top first:sticky first:left-0 first:z-10 first:bg-background" key={cell.id}><table.FlexRender cell={cell} /></td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}
