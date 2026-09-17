"""B07 selection semantics against the B06 canonical synthetic fixtures."""

from datetime import date, datetime, timezone
from uuid import UUID

from django.test import TestCase

from analytics.windows import (
    Cutoff,
    MembershipState,
    OrderState,
    SelectionError,
    select_player_window,
    select_team_window,
)
from domain.fixtures import (
    build_batting_sequence,
    complete_step,
    fixture_uuid,
    load_synthetic_fixtures,
)
from domain.models import (
    Game,
    GameDataCoverage,
    PlateAppearance,
    Player,
    PlayerGameParticipation,
    PlayerTeamAffiliation,
    Season,
    Team,
    Venue,
)


class WindowSelectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = load_synthetic_fixtures()
        cls.season = Season.objects.get(pk=cls.fixture.season_id)
        cls.a = Team.objects.get(pk=cls.fixture.team_ids["a"])
        cls.b = Team.objects.get(pk=cls.fixture.team_ids["b"])
        cls.c = Team.objects.get(pk=cls.fixture.team_ids["c"])
        cls.slugger = Player.objects.get(pk=cls.fixture.player_ids["slugger"])
        cls.walker = Player.objects.get(pk=cls.fixture.player_ids["walker"])
        cls.runner = Player.objects.get(pk=cls.fixture.player_ids["runner"])
        cls.venue = Venue.objects.get(name="Synthetic Park")

    def game(self, name):
        return Game.objects.get(pk=self.fixture.game_ids[name])

    def team_window(self, **kwargs):
        return select_team_window(season=self.season, team=self.a, **kwargs)

    def player_window(self, player=None, **kwargs):
        return select_player_window(
            season=self.season, player=player or self.slugger, **kwargs
        )

    def create_game(
        self,
        key,
        day,
        *,
        season=None,
        home=None,
        away=None,
        game_type=Game.Type.REGULAR,
        finality=Game.Finality.FINAL,
        number=None,
        scheduled_start=None,
        actual_start=None,
    ):
        game = Game(
            id=fixture_uuid(f"b07:game:{key}"),
            season=season or self.season,
            home_team=home or self.a,
            away_team=away or self.b,
            venue=self.venue,
            official_date=day,
            game_type=game_type,
            finality=finality,
            status=(
                Game.Status.COMPLETED
                if finality == Game.Finality.FINAL
                else Game.Status.SCHEDULED
            ),
            scheduled_game_number=number,
            scheduled_start_at_utc=scheduled_start,
            actual_start_at_utc=actual_start,
        )
        game.full_clean()
        game.save()
        return game

    def create_participation(
        self,
        key,
        game,
        *,
        player=None,
        team=None,
        state=PlayerGameParticipation.State.APPEARED,
        pa_coverage=PlayerGameParticipation.Coverage.COMPLETE,
        pa=False,
    ):
        player = player or self.slugger
        team = team or self.a
        row = PlayerGameParticipation(
            id=fixture_uuid(f"b07:participation:{key}"),
            game=game,
            player=player,
            team=team,
            participation_state=state,
            pa_coverage=pa_coverage,
        )
        row.full_clean()
        row.save()
        if pa:
            appearance = PlateAppearance(
                id=fixture_uuid(f"b07:pa:{key}"),
                game=game,
                batter=player,
                batting_team=team,
                fielding_team=game.away_team
                if team == game.home_team
                else game.home_team,
                game_pa_ordinal=1,
                outcome_category=PlateAppearance.Outcome.NON_HR,
            )
            appearance.full_clean()
            appearance.save()
        return row

    def create_coverage(self, key, game, state):
        row = GameDataCoverage(
            id=fixture_uuid(f"b07:coverage:{key}"),
            game=game,
            domain=GameDataCoverage.Domain.PARTICIPATION,
            state=state,
            assessed_at_utc=datetime(2099, 4, 1, tzinfo=timezone.utc),
        )
        row.full_clean()
        row.save()
        return row

    def isolated_season(self, year=2098):
        season = Season(
            id=fixture_uuid(f"b07:season:{year}"), year=year, label="B07 SYNTHETIC"
        )
        season.full_clean()
        season.save()
        return season

    def create_affiliation(
        self, key, season, team, start=None, end=None, precision="DATE"
    ):
        row = PlayerTeamAffiliation(
            id=fixture_uuid(f"b07:affiliation:{key}"),
            player=self.slugger,
            team=team,
            season=season,
            effective_from_date=start,
            effective_to_date_exclusive=end,
            boundary_precision=precision,
        )
        row.full_clean()
        row.save()
        return row

    def test_team_final_regular_and_incomplete_coverage_stay_selected(self):
        result = self.team_window(window="SEASON")
        ids = {entry.game_id for entry in result.entries}
        self.assertIn(self.game("ordinary").id, ids)
        self.assertIn(self.game("partial_pa").id, ids)
        self.assertIn(self.game("unknown_hr").id, ids)
        self.assertEqual(result.membership_state, MembershipState.RESOLVED)
        self.assertEqual(result.actual_game_count, len(ids))

    def test_team_nonregular_and_nonfinal_games_are_excluded(self):
        for kind in (Game.Type.POSTSEASON, Game.Type.SPRING, Game.Type.UNKNOWN):
            self.create_game(f"type:{kind}", date(2099, 4, 26), game_type=kind)
        self.create_game(
            "scheduled", date(2099, 4, 27), finality=Game.Finality.NOT_FINAL
        )
        result = self.team_window(window="SEASON")
        self.assertTrue(
            all(entry.official_date <= date(2099, 4, 25) for entry in result.entries)
        )

    def test_team_home_away_filters_precede_last_n(self):
        home = self.team_window(window="7G", home_away="HOME")
        away = self.team_window(window="7G", home_away="AWAY")
        self.assertTrue(
            all(
                Game.objects.get(pk=e.game_id).home_team_id == self.a.id
                for e in home.entries
            )
        )
        self.assertTrue(
            all(
                Game.objects.get(pk=e.game_id).away_team_id == self.a.id
                for e in away.entries
            )
        )
        self.assertNotEqual(
            [e.game_id for e in home.entries], [e.game_id for e in away.entries]
        )

    def test_team_all_windows_and_fewer_than_n(self):
        season = self.isolated_season()
        ids = build_batting_sequence(
            key="b07:long",
            season=season,
            player=self.slugger,
            batting_team=self.a,
            opponent=self.b,
            venue=self.venue,
            start_date=date(2098, 4, 1),
            steps=(complete_step(0),) * 62,
        )
        for window, n in (("7G", 7), ("15G", 15), ("30G", 30), ("60G", 60)):
            result = select_team_window(season=season, team=self.a, window=window)
            self.assertEqual(tuple(e.game_id for e in result.entries), ids[-n:])
            self.assertEqual(result.actual_game_count, n)
        season_result = select_team_window(season=season, team=self.a)
        self.assertEqual(season_result.actual_game_count, 62)
        few = select_team_window(
            season=season, team=self.a, window="60G", cutoff=date(2098, 4, 3)
        )
        self.assertEqual(few.actual_game_count, 3)
        self.assertEqual(few.requested_n, 60)

    def test_date_cutoff_includes_whole_doubleheader_and_game_is_inclusive(self):
        first, second = self.fixture.scenarios["doubleheader"]
        date_result = self.team_window(window="SEASON", cutoff=date(2099, 4, 15))
        self.assertTrue(
            {first, second}.issubset({e.game_id for e in date_result.entries})
        )
        self.assertLess(
            [e.game_id for e in date_result.entries].index(first),
            [e.game_id for e in date_result.entries].index(second),
        )
        game_result = self.team_window(window="SEASON", cutoff=first)
        self.assertIn(first, {e.game_id for e in game_result.entries})
        self.assertNotIn(second, {e.game_id for e in game_result.entries})

    def test_suspended_game_uses_original_official_date(self):
        result = self.team_window(window="SEASON", cutoff=date(2099, 4, 16))
        self.assertIn(self.game("suspended").id, {e.game_id for e in result.entries})
        self.assertEqual(
            self.game("suspended").completed_at_utc.date(), date(2099, 4, 18)
        )

    def test_latest_resolves_scope_specific_final_date(self):
        team = self.team_window()
        self.assertEqual(team.resolved_cutoff.official_date, date(2099, 4, 25))
        other = select_team_window(season=self.season, team=self.c)
        self.assertEqual(other.resolved_cutoff.official_date, date(2099, 4, 14))
        filtered = self.player_window(represented_team=self.c)
        self.assertEqual(filtered.resolved_cutoff.official_date, date(2099, 4, 14))

    def test_unknown_official_date_blocks_team_selection(self):
        unknown = self.create_game("undated", None)
        result = self.team_window(window="7G")
        self.assertEqual(result.membership_state, MembershipState.UNKNOWN)
        self.assertIsNone(result.actual_game_count)
        self.assertIn(unknown.id, result.uncertain_candidate_ids)
        self.assertEqual(result.known_eligible_game_count, 7)
        historical = self.team_window(window="SEASON", cutoff=date(2099, 4, 15))
        self.assertEqual(historical.membership_state, MembershipState.UNKNOWN)
        self.assertIn(unknown.id, historical.uncertain_candidate_ids)

    def test_known_number_then_start_then_uuid_presentation(self):
        day = date(2099, 4, 26)
        numbered_2 = self.create_game("number:2", day, number=2)
        numbered_1 = self.create_game("number:1", day, number=1)
        start_late = datetime(2099, 4, 26, 20, tzinfo=timezone.utc)
        start_early = datetime(2099, 4, 26, 18, tzinfo=timezone.utc)
        by_actual = self.create_game("actual", day, actual_start=start_early)
        by_scheduled = self.create_game("scheduled", day, scheduled_start=start_late)
        unknown_start_a = self.create_game("unknown-a", day)
        unknown_start_b = self.create_game("unknown-b", day)
        result = self.team_window(cutoff=day)
        same_day = [e.game_id for e in result.entries if e.official_date == day]
        self.assertEqual(
            same_day[:4], [numbered_1.id, numbered_2.id, by_actual.id, by_scheduled.id]
        )
        self.assertEqual(same_day[4:], sorted([unknown_start_a.id, unknown_start_b.id]))
        self.assertEqual(result.order_state, OrderState.UNVERIFIED)

    def test_internal_tie_has_resolved_membership_and_unverified_order(self):
        result = self.team_window(window="SEASON", cutoff=date(2099, 4, 20))
        tied = set(self.fixture.scenarios["same_day_unordered"])
        self.assertEqual(result.membership_state, MembershipState.RESOLVED)
        self.assertEqual(result.order_state, OrderState.UNVERIFIED)
        self.assertTrue(tied.issubset({e.game_id for e in result.entries}))
        self.assertIn(tuple(sorted(tied)), result.unverified_order_groups)

    def test_rolling_boundary_tie_does_not_claim_arbitrary_game(self):
        season = self.isolated_season()
        ids = build_batting_sequence(
            key="b07:boundary",
            season=season,
            player=self.slugger,
            batting_team=self.a,
            opponent=self.b,
            venue=self.venue,
            start_date=date(2098, 4, 1),
            steps=(complete_step(0),) * 6,
        )
        tied = [
            self.create_game(f"boundary-tie:{n}", date(2098, 4, 7), season=season)
            for n in (1, 2)
        ]
        build_batting_sequence(
            key="b07:boundary-later",
            season=season,
            player=self.slugger,
            batting_team=self.a,
            opponent=self.b,
            venue=self.venue,
            start_date=date(2098, 4, 8),
            steps=(complete_step(0),) * 6,
        )
        result = select_team_window(season=season, team=self.a, window="7G")
        self.assertEqual(result.membership_state, MembershipState.ORDER_UNVERIFIED)
        self.assertIsNone(result.actual_game_count)
        self.assertEqual(result.entries, ())
        self.assertEqual(set(result.ambiguous_candidate_ids), {g.id for g in tied})
        self.assertEqual(result.known_eligible_game_count, 7)
        self.assertEqual(len(ids), 6)

    def test_game_cutoff_within_tie_is_order_unverified(self):
        first, second = self.fixture.scenarios["same_day_unordered"]
        result = self.team_window(window="SEASON", cutoff=first)
        self.assertEqual(result.membership_state, MembershipState.ORDER_UNVERIFIED)
        self.assertIsNone(result.actual_game_count)
        self.assertEqual(set(result.ambiguous_candidate_ids), {first, second})
        date_result = self.team_window(window="SEASON", cutoff=date(2099, 4, 20))
        self.assertEqual(date_result.membership_state, MembershipState.RESOLVED)

    def test_player_tie_internal_then_boundary(self):
        internal = self.player_window(window="7G")
        tied = set(self.fixture.scenarios["same_day_unordered"])
        self.assertEqual(internal.membership_state, MembershipState.RESOLVED)
        self.assertEqual(internal.order_state, OrderState.UNVERIFIED)
        self.assertTrue(tied.issubset({e.game_id for e in internal.entries}))
        late = self.create_game("player-boundary-late", date(2099, 4, 26))
        self.create_participation("player-boundary-late", late, pa=True)
        self.create_coverage(
            "player-boundary-late", late, GameDataCoverage.State.COMPLETE
        )
        boundary = self.player_window(window="7G")
        self.assertEqual(boundary.membership_state, MembershipState.ORDER_UNVERIFIED)
        self.assertEqual(set(boundary.ambiguous_candidate_ids), tied)
        self.assertIsNone(boundary.actual_game_count)

    def test_player_walk_dnp_zero_pa_and_unknown_states(self):
        walk = self.player_window(player=self.walker, cutoff=date(2099, 4, 4))
        self.assertIn(self.game("walk_only").id, {e.game_id for e in walk.entries})
        zero = self.player_window(player=self.runner, cutoff=date(2099, 4, 5))
        self.assertNotIn(self.game("zero_pa").id, {e.game_id for e in zero.entries})
        dnp = self.player_window(cutoff=date(2099, 4, 6))
        self.assertNotIn(self.game("dnp").id, {e.game_id for e in dnp.entries})

    def test_unknown_and_partial_player_candidate_not_backfilled(self):
        unknown = self.player_window(window="7G", cutoff=date(2099, 4, 8))
        self.assertEqual(unknown.membership_state, MembershipState.UNKNOWN)
        self.assertIn(
            self.game("unknown_participation").id, unknown.uncertain_candidate_ids
        )
        self.assertIn(self.game("unassessed").id, unknown.uncertain_candidate_ids)
        partial = self.player_window(window="7G", cutoff=date(2099, 4, 9))
        self.assertEqual(partial.membership_state, MembershipState.UNKNOWN)
        self.assertIn(self.game("partial_pa").id, partial.uncertain_candidate_ids)
        self.assertEqual(partial.entries, ())
        self.assertIsNone(partial.actual_game_count)

    def test_partial_player_pa_alone_is_incomplete(self):
        season = self.isolated_season()
        game = self.create_game("player-partial-only", date(2098, 4, 1), season=season)
        self.create_participation(
            "player-partial-only",
            game,
            pa_coverage=PlayerGameParticipation.Coverage.PARTIAL,
        )
        result = select_player_window(season=season, player=self.slugger)
        self.assertEqual(result.membership_state, MembershipState.INCOMPLETE)
        self.assertIn(game.id, result.uncertain_candidate_ids)

    def test_complete_participation_without_row_is_not_dnp(self):
        season = self.isolated_season()
        game = self.create_game("no-player-row", date(2098, 4, 1), season=season)
        self.create_coverage("no-player-row", game, GameDataCoverage.State.COMPLETE)
        result = select_player_window(season=season, player=self.slugger)
        self.assertEqual(result.membership_state, MembershipState.RESOLVED)
        self.assertEqual(result.actual_game_count, 0)
        self.assertFalse(
            PlayerGameParticipation.objects.filter(
                game=game, player=self.slugger
            ).exists()
        )

    def test_player_trade_team_filter_and_both_team_game(self):
        # Late B appearances put the B06 unknown April 7-9 evidence
        # outside the seven-game B window without changing the fixture pack.
        self.add_late_b_appearances()
        a = self.player_window(
            represented_team=self.a, window="7G", cutoff=date(2099, 4, 19)
        )
        b = self.player_window(
            represented_team=self.b, window="7G", cutoff=date(2099, 4, 19)
        )
        both = self.game("both_teams").id
        self.assertIn(both, {e.game_id for e in a.entries})
        self.assertIn(both, {e.game_id for e in b.entries})
        self.assertEqual(
            next(e for e in a.entries if e.game_id == both).represented_team_ids,
            (self.a.id,),
        )
        self.assertEqual(
            next(e for e in b.entries if e.game_id == both).represented_team_ids,
            (self.b.id,),
        )
        unfiltered = self.player_window(window="7G", cutoff=date(2099, 4, 19))
        both_entries = [e for e in unfiltered.entries if e.game_id == both]
        self.assertEqual(len(both_entries), 1)
        self.assertEqual(
            set(both_entries[0].represented_team_ids), {self.a.id, self.b.id}
        )
        self.assertEqual(len(both_entries[0].plate_appearance_ids), 2)

    def test_player_home_away_follows_represented_team(self):
        self.add_late_b_appearances()
        home = self.player_window(
            represented_team=self.a,
            home_away="HOME",
            window="7G",
            cutoff=date(2099, 4, 19),
        )
        away = self.player_window(
            represented_team=self.b,
            home_away="AWAY",
            window="7G",
            cutoff=date(2099, 4, 19),
        )
        both = self.game("both_teams").id
        self.assertIn(both, {e.game_id for e in home.entries})
        self.assertIn(both, {e.game_id for e in away.entries})
        self.assertTrue(
            all(
                Game.objects.get(pk=e.game_id).home_team_id == self.a.id
                for e in home.entries
            )
        )
        self.assertTrue(
            all(
                Game.objects.get(pk=e.game_id).away_team_id == self.b.id
                for e in away.entries
            )
        )

    def add_late_b_appearances(self):
        for number in range(1, 7):
            game = self.create_game(
                f"late-b:{number}", date(2099, 4, 17), number=number
            )
            self.create_participation(f"late-b:{number}", game, team=self.b, pa=True)
            self.create_coverage(
                f"late-b:{number}", game, GameDataCoverage.State.COMPLETE
            )

    def test_fewer_than_n_player_games_reports_actual_count(self):
        season = self.isolated_season()
        ids = build_batting_sequence(
            key="b07:player-short",
            season=season,
            player=self.slugger,
            batting_team=self.a,
            opponent=self.b,
            venue=self.venue,
            start_date=date(2098, 4, 1),
            steps=(complete_step(0),) * 3,
        )
        result = select_player_window(season=season, player=self.slugger, window="7G")
        self.assertEqual(result.membership_state, MembershipState.RESOLVED)
        self.assertEqual(result.actual_game_count, 3)
        self.assertEqual(tuple(e.game_id for e in result.entries), ids)

    def test_player_long_windows_select_batting_suffix_after_team_filter(self):
        season = self.isolated_season()
        a_ids = build_batting_sequence(
            key="b07:player-a-long",
            season=season,
            player=self.slugger,
            batting_team=self.a,
            opponent=self.c,
            venue=self.venue,
            start_date=date(2098, 4, 1),
            steps=(complete_step(0),) * 61,
        )
        b_ids = build_batting_sequence(
            key="b07:player-b-long",
            season=season,
            player=self.slugger,
            batting_team=self.b,
            opponent=self.c,
            venue=self.venue,
            start_date=date(2098, 6, 1),
            steps=(complete_step(0),) * 2,
        )
        for window, n in (("7G", 7), ("15G", 15), ("30G", 30), ("60G", 60)):
            a = select_player_window(
                season=season,
                player=self.slugger,
                represented_team=self.a,
                window=window,
            )
            self.assertEqual(tuple(e.game_id for e in a.entries), a_ids[-n:])
            all_teams = select_player_window(
                season=season,
                player=self.slugger,
                window=window,
            )
            self.assertEqual(
                tuple(e.game_id for e in all_teams.entries),
                (a_ids + b_ids)[-n:],
            )
        whole = select_player_window(season=season, player=self.slugger)
        self.assertEqual(whole.actual_game_count, 63)

    def test_unknown_date_player_opportunity_blocks_membership(self):
        season = self.isolated_season()
        dated = self.create_game("player-dated", date(2098, 4, 1), season=season)
        unknown = self.create_game("player-undated", None, season=season)
        self.create_participation("player-dated", dated, pa=True)
        self.create_participation("player-undated", unknown, pa=True)
        result = select_player_window(
            season=season, player=self.slugger, cutoff=date(2098, 4, 1)
        )
        self.assertEqual(result.membership_state, MembershipState.UNKNOWN)
        self.assertEqual(result.known_eligible_game_count, 1)
        self.assertIn(unknown.id, result.uncertain_candidate_ids)

    def test_unrelated_team_unknown_coverage_does_not_poison_player(self):
        season = self.isolated_season()
        known = self.create_game("relevant-a", date(2098, 4, 1), season=season)
        self.create_participation("relevant-a", known, pa=True)
        d = Team(id=fixture_uuid("b08:team:d"), display_name="Synthetic D")
        d.full_clean()
        d.save()
        unrelated = self.create_game(
            "unrelated-c-d",
            date(2098, 4, 2),
            season=season,
            home=self.c,
            away=d,
        )
        self.create_coverage("unrelated-c-d", unrelated, GameDataCoverage.State.UNKNOWN)
        result = select_player_window(season=season, player=self.slugger)
        self.assertEqual(result.membership_state, MembershipState.RESOLVED)
        self.assertEqual(tuple(entry.game_id for entry in result.entries), (known.id,))
        self.assertNotIn(unrelated.id, result.uncertain_candidate_ids)

    def test_positive_new_team_evidence_without_affiliation_is_included(self):
        season = self.isolated_season()
        game = self.create_game(
            "new-team-c",
            date(2098, 4, 1),
            season=season,
            home=self.c,
            away=self.a,
        )
        self.create_participation("new-team-c", game, team=self.c, pa=True)
        result = select_player_window(season=season, player=self.slugger)
        self.assertEqual(result.membership_state, MembershipState.RESOLVED)
        self.assertEqual(result.entries[0].represented_team_ids, (self.c.id,))
        self.assertEqual(result.actual_game_count, 1)

    def test_precisely_ended_affiliation_excludes_later_unevidenced_game(self):
        season = self.isolated_season()
        self.create_affiliation(
            "ended-a", season, self.a, date(2098, 4, 1), date(2098, 4, 5)
        )
        known = self.create_game("during-affiliation", date(2098, 4, 3), season=season)
        self.create_participation("during-affiliation", known, pa=True)
        later = self.create_game("after-affiliation", date(2098, 4, 7), season=season)
        self.create_coverage("after-affiliation", later, GameDataCoverage.State.UNKNOWN)
        result = select_player_window(season=season, player=self.slugger)
        self.assertEqual(result.membership_state, MembershipState.RESOLVED)
        self.assertEqual(tuple(entry.game_id for entry in result.entries), (known.id,))

    def test_team_filtered_precise_departure_excludes_later_unknown_game(self):
        season = self.isolated_season()
        self.create_affiliation(
            "filtered-ended-a",
            season,
            self.a,
            date(2098, 4, 1),
            date(2098, 4, 5),
        )
        known = self.create_game("filtered-a-known", date(2098, 4, 3), season=season)
        self.create_participation("filtered-a-known", known, pa=True)
        later = self.create_game("filtered-a-later", date(2098, 4, 7), season=season)
        self.create_coverage("filtered-a-later", later, GameDataCoverage.State.UNKNOWN)
        result = select_player_window(
            season=season, player=self.slugger, represented_team=self.a
        )
        self.assertEqual(result.membership_state, MembershipState.RESOLVED)
        self.assertEqual(tuple(entry.game_id for entry in result.entries), (known.id,))
        self.assertNotIn(later.id, result.uncertain_candidate_ids)

    def test_team_filtered_positive_evidence_overrides_precise_end(self):
        season = self.isolated_season()
        self.create_affiliation(
            "filtered-positive-a",
            season,
            self.a,
            date(2098, 4, 1),
            date(2098, 4, 5),
        )
        later = self.create_game(
            "filtered-positive-later", date(2098, 4, 7), season=season
        )
        self.create_participation("filtered-positive-later", later, pa=True)
        result = select_player_window(
            season=season, player=self.slugger, represented_team=self.a
        )
        self.assertEqual(result.membership_state, MembershipState.RESOLVED)
        self.assertEqual(tuple(entry.game_id for entry in result.entries), (later.id,))

    def test_team_filtered_unknown_precision_keeps_uncertain_game(self):
        season = self.isolated_season()
        self.create_affiliation(
            "filtered-imprecise-a",
            season,
            self.a,
            date(2098, 4, 1),
            date(2098, 4, 5),
            precision="UNKNOWN",
        )
        later = self.create_game(
            "filtered-imprecise-later", date(2098, 4, 7), season=season
        )
        self.create_coverage(
            "filtered-imprecise-later", later, GameDataCoverage.State.UNKNOWN
        )
        result = select_player_window(
            season=season, player=self.slugger, represented_team=self.a
        )
        self.assertEqual(result.membership_state, MembershipState.UNKNOWN)
        self.assertIn(later.id, result.uncertain_candidate_ids)

    def test_open_relevant_affiliation_keeps_unknown_candidate(self):
        season = self.isolated_season()
        self.create_affiliation("open-a", season, self.a, date(2098, 4, 1))
        game = self.create_game("open-a-unknown", date(2098, 4, 5), season=season)
        self.create_coverage("open-a-unknown", game, GameDataCoverage.State.UNKNOWN)
        result = select_player_window(season=season, player=self.slugger)
        self.assertEqual(result.membership_state, MembershipState.UNKNOWN)
        self.assertIn(game.id, result.uncertain_candidate_ids)

    def test_mixed_unknown_and_partial_candidates_prioritize_unknown(self):
        season = self.isolated_season()
        self.create_affiliation("mixed-a", season, self.a, date(2098, 4, 1))
        unknown = self.create_game("mixed-unknown", date(2098, 4, 1), season=season)
        partial = self.create_game("mixed-partial", date(2098, 4, 2), season=season)
        self.create_coverage("mixed-unknown", unknown, GameDataCoverage.State.UNKNOWN)
        self.create_coverage("mixed-partial", partial, GameDataCoverage.State.PARTIAL)
        result = select_player_window(season=season, player=self.slugger)
        self.assertEqual(result.membership_state, MembershipState.UNKNOWN)
        self.assertEqual(set(result.uncertain_candidate_ids), {unknown.id, partial.id})

    def test_uncertain_player_count_is_lower_bound(self):
        result = self.player_window(window="7G", cutoff=date(2099, 4, 9))
        self.assertIsNone(result.actual_game_count)
        self.assertLessEqual(result.known_eligible_game_count, 7)
        self.assertGreater(result.known_eligible_game_count, 0)

    def test_cutoff_and_scope_validation(self):
        with self.assertRaisesMessage(SelectionError, "INVALID_WINDOW"):
            self.team_window(window="8G")
        with self.assertRaisesMessage(SelectionError, "INVALID_HOME_AWAY"):
            self.team_window(home_away="BOTH")
        with self.assertRaisesMessage(SelectionError, "INVALID_CUTOFF"):
            self.team_window(cutoff="04/20/2099")
        with self.assertRaisesMessage(SelectionError, "CUTOFF_BEFORE_SCOPE"):
            self.team_window(cutoff=date(2099, 3, 31))
        with self.assertRaisesMessage(SelectionError, "CUTOFF_AFTER_SCOPE"):
            self.team_window(cutoff=date(2099, 4, 30))
        with self.assertRaisesMessage(SelectionError, "CUTOFF_WRONG_SEASON"):
            other = self.isolated_season()
            game = self.create_game("wrong-season", date(2098, 4, 1), season=other)
            self.team_window(cutoff=game.id)
        with self.assertRaisesMessage(SelectionError, "CUTOFF_GAME_OUTSIDE_SCOPE"):
            self.team_window(cutoff=self.game("trade_b_zero").id)
        with self.assertRaisesMessage(SelectionError, "CUTOFF_GAME_OUTSIDE_SCOPE"):
            self.team_window(home_away="AWAY", cutoff=self.game("known_zero").id)
        with self.assertRaisesMessage(SelectionError, "NO_FINAL_REGULAR_GAME"):
            other = self.isolated_season(2097)
            select_team_window(season=other, team=self.a)

    def test_cutoff_date_and_uuid_forms_are_equivalent(self):
        date_result = self.team_window(cutoff="2099-04-15")
        self.assertEqual(date_result.resolved_cutoff, Cutoff.on_date(date(2099, 4, 15)))
        game_result = self.team_window(cutoff=str(self.game("doubleheader_1").id))
        self.assertEqual(game_result.resolved_cutoff.kind, "GAME")
        self.assertTrue(
            all(isinstance(entry.game_id, UUID) for entry in game_result.entries)
        )
