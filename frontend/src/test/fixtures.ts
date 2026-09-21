export const UUIDS = {
  season: '11111111-1111-4111-8111-111111111111',
  teamA: '22222222-2222-4222-8222-222222222222',
  teamB: '33333333-3333-4333-8333-333333333333',
  player: '44444444-4444-4444-8444-444444444444',
  game: '55555555-5555-4555-8555-555555555555',
  venue: '66666666-6666-4666-8666-666666666666',
}

export const meta = { dataset_revision: '7', data_as_of: '2099-05-01T12:00:00Z' }

export const team = (id = UUIDS.teamA) => ({
  id,
  mlb_id: null,
  display_name: 'Synthetic Team',
  abbreviation: 'SYN',
  league: null,
  division: null,
})

export const player = {
  id: UUIDS.player,
  mlb_id: null,
  display_name: 'Fixture Slugger',
  given_name: 'Fixture',
  family_name: 'Slugger',
  bats: 'R',
  throws: 'R',
  primary_position: '1B',
  represented_team: null,
}

export const valueMetric = {
  state: 'VALUE',
  value: 0,
  unit: 'HR',
  numerator: 0,
  denominator: null,
  reason: null,
}

export const game = {
  id: UUIDS.game,
  mlb_game_pk: null,
  season: 2099,
  game_type: 'REGULAR',
  official_date: '2099-04-03',
  scheduled_start_at_utc: '2099-04-03T20:00:00Z',
  status: 'COMPLETED',
  finality: 'FINAL',
  home_team: team(UUIDS.teamA),
  away_team: team(UUIDS.teamB),
  home_score: 1,
  away_score: 0,
  scheduled_game_number: 1,
  venue: { id: UUIDS.venue, name: 'Synthetic Park', timezone_id: 'UTC' },
  hr_count: valueMetric,
}
