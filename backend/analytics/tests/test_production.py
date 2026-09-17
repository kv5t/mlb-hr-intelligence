"""B09 production/frequency KPI contracts over deterministic canonical data."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from analytics.production import (
    compute_player_production_metrics,
    compute_team_production_metrics,
)
from analytics.values import MetricState
from analytics.windows import (
    MembershipState,
    OrderState,
    select_player_window,
    select_team_window,
)
from domain.fixtures import (
    SequenceStep,
    build_batting_sequence,
    complete_step,
    fixture_uuid,
    load_synthetic_fixtures,
)
from domain.models import (
    Game,
    GameDataCoverage,
    HomeRunEvent,
    PlateAppearance,
    Player,
    PlayerGameParticipation,
    Season,
    Team,
    Venue,
)


class ProductionMetricTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = load_synthetic_fixtures()
        cls.a = Team.objects.get(pk=cls.fixture.team_ids["a"])
        cls.b = Team.objects.get(pk=cls.fixture.team_ids["b"])
        cls.c = Team.objects.get(pk=cls.fixture.team_ids["c"])
        cls.slugger = Player.objects.get(pk=cls.fixture.player_ids["slugger"])
        cls.regular = Player.objects.get(pk=cls.fixture.player_ids["regular"])
        cls.venue = Venue.objects.get(name="Synthetic Park")

    def season(self):
        season = Season(id=fixture_uuid("b09:season"), year=2098, label="B09 SYNTHETIC")
        season.full_clean()
        season.save()
        return season

    def sequence(self, season, key, steps, *, team=None, opponent=None, start=None):
        return build_batting_sequence(
            key=f"b09:{key}",
            season=season,
            player=self.slugger,
            batting_team=team or self.a,
            opponent=opponent or self.b,
            venue=self.venue,
            start_date=start or date(2098, 4, 1),
            steps=tuple(steps),
        )

    def metrics(self, season, subject="PLAYER", **kwargs):
        if subject == "PLAYER":
            selection = select_player_window(
                season=season, player=self.slugger, **kwargs
            )
            return selection, compute_player_production_metrics(selection)
        selection = select_team_window(season=season, team=self.a, **kwargs)
        return selection, compute_team_production_metrics(selection)

    def assert_value(self, metrics, key, value, numerator=None, denominator=None):
        result = metrics[key]
        self.assertEqual(result.state, MetricState.VALUE)
        self.assertEqual(result.value, value)
        self.assertEqual(result.numerator, numerator)
        self.assertEqual(result.denominator, denominator)

    def test_multi_hr_four_pa_exact_counts_rates_for_player_and_team(self):
        season = self.season()
        self.sequence(season, "two-hr", (complete_step(2, 4),))
        for subject in ("PLAYER", "TEAM"):
            selection, metrics = self.metrics(season, subject)
            prefix = subject.lower()
            self.assertEqual(selection.actual_game_count, 1)
            self.assertEqual(
                set(metrics),
                {
                    f"{prefix}.{name}"
                    for name in (
                        "hr",
                        "pa",
                        "hr_per_pa",
                        "pa_per_hr",
                        "hr_per_game",
                        "hr_games",
                        "hr_game_pct",
                        "multi_hr_games",
                    )
                },
            )
            self.assert_value(metrics, f"{prefix}.hr", 2, 2)
            self.assert_value(metrics, f"{prefix}.pa", 4, 4)
            self.assert_value(metrics, f"{prefix}.hr_per_game", Decimal(2), 2, 1)
            self.assert_value(metrics, f"{prefix}.hr_per_pa", Decimal("0.5"), 2, 4)
            self.assert_value(metrics, f"{prefix}.pa_per_hr", Decimal(2), 4, 2)
            self.assert_value(metrics, f"{prefix}.hr_games", 1, 1)
            self.assert_value(metrics, f"{prefix}.hr_game_pct", Decimal(100), 1, 1)
            self.assert_value(metrics, f"{prefix}.multi_hr_games", 1, 1)
            self.assertEqual(metrics[f"{prefix}.hr_game_pct"].unit, "PERCENT")

    def test_walk_only_and_no_hr_are_numeric_zeros(self):
        season = self.season()
        self.sequence(season, "walk", (complete_step(0, 1),))
        for subject in ("PLAYER", "TEAM"):
            _, metrics = self.metrics(season, subject)
            prefix = subject.lower()
            self.assert_value(metrics, f"{prefix}.pa", 1, 1)
            self.assert_value(metrics, f"{prefix}.hr", 0, 0)
            self.assert_value(metrics, f"{prefix}.hr_per_game", Decimal(0), 0, 1)
            self.assert_value(metrics, f"{prefix}.hr_per_pa", Decimal(0), 0, 1)
            self.assert_value(metrics, f"{prefix}.hr_games", 0, 0)
            self.assert_value(metrics, f"{prefix}.hr_game_pct", Decimal(0), 0, 1)
            self.assert_value(metrics, f"{prefix}.multi_hr_games", 0, 0)
            ratio = metrics[f"{prefix}.pa_per_hr"]
            self.assertEqual(
                (ratio.state, ratio.reason),
                (MetricState.NOT_APPLICABLE, "NO_HOME_RUNS_IN_SCOPE"),
            )

    def test_three_zero_hr_games_and_five_pa_zero_rate(self):
        season = self.season()
        self.sequence(season, "three-zero", (complete_step(0),) * 3)
        _, metrics = self.metrics(season)
        self.assert_value(metrics, "player.hr", 0, 0)
        self.assert_value(metrics, "player.hr_games", 0, 0)
        self.assertEqual(metrics["player.pa_per_hr"].reason, "NO_HOME_RUNS_IN_SCOPE")
        more = self.sequence(
            season, "five-pa", (complete_step(0, 5),), start=date(2098, 4, 4)
        )
        _, metrics = self.metrics(season, cutoff=more[0])
        self.assert_value(metrics, "player.hr_per_pa", Decimal(0), 0, 8)

    def test_partial_hr_inside_window_blocks_hr_metrics_but_not_pa(self):
        season = self.season()
        partial = SequenceStep(
            participation=PlayerGameParticipation.State.APPEARED,
            player_pa_coverage=PlayerGameParticipation.Coverage.COMPLETE,
            participation_coverage=GameDataCoverage.State.COMPLETE,
            game_pa_coverage=GameDataCoverage.State.COMPLETE,
            game_hr_coverage=GameDataCoverage.State.PARTIAL,
            pa_count=1,
            hr_count=0,
        )
        self.sequence(
            season, "partial-hr", (complete_step(1), partial, complete_step(1))
        )
        for subject in ("PLAYER", "TEAM"):
            selection, metrics = self.metrics(season, subject)
            self.assertEqual(selection.actual_game_count, 3)
            prefix = subject.lower()
            self.assert_value(metrics, f"{prefix}.pa", 3, 3)
            for key, metric in metrics.items():
                if key != f"{prefix}.pa":
                    self.assertEqual(metric.state, MetricState.INCOMPLETE, key)
                    self.assertIsNone(metric.value)

    def test_partial_player_pa_membership_precedes_empty_formula(self):
        season = self.season()
        partial = SequenceStep(
            participation=PlayerGameParticipation.State.APPEARED,
            player_pa_coverage=PlayerGameParticipation.Coverage.PARTIAL,
            participation_coverage=GameDataCoverage.State.PARTIAL,
            game_pa_coverage=GameDataCoverage.State.PARTIAL,
            game_hr_coverage=GameDataCoverage.State.PARTIAL,
            pa_count=0,
            hr_count=0,
        )
        self.sequence(season, "partial-membership", (complete_step(1), partial))
        selection, metrics = self.metrics(season)
        self.assertEqual(selection.membership_state, MembershipState.INCOMPLETE)
        for metric in metrics.values():
            self.assertEqual(metric.state, MetricState.INCOMPLETE)
            self.assertIsNone(metric.value)

    def test_unknown_player_membership_precedes_empty_formula(self):
        season = self.season()
        unknown = SequenceStep(
            participation=PlayerGameParticipation.State.UNKNOWN,
            player_pa_coverage=PlayerGameParticipation.Coverage.UNKNOWN,
            participation_coverage=GameDataCoverage.State.UNKNOWN,
            game_pa_coverage=GameDataCoverage.State.UNKNOWN,
            game_hr_coverage=GameDataCoverage.State.UNKNOWN,
            pa_count=0,
            hr_count=0,
        )
        self.sequence(season, "unknown-membership", (unknown,))
        selection, metrics = self.metrics(season)
        self.assertEqual(selection.membership_state, MembershipState.UNKNOWN)
        self.assertTrue(
            all(metric.state == MetricState.UNKNOWN for metric in metrics.values())
        )

    def test_unknown_hr_coverage_precedes_no_hr_mathematical_reason(self):
        season = self.season()
        (game_id,) = self.sequence(season, "unknown-hr", (complete_step(0),))
        coverage = GameDataCoverage.objects.get(
            game_id=game_id, domain=GameDataCoverage.Domain.HR_EVENTS
        )
        coverage.state = GameDataCoverage.State.UNKNOWN
        coverage.full_clean()
        coverage.save()
        for subject in ("PLAYER", "TEAM"):
            _, metrics = self.metrics(season, subject)
            self.assert_value(metrics, f"{subject.lower()}.pa", 1, 1)
            self.assertEqual(
                metrics[f"{subject.lower()}.pa_per_hr"].state, MetricState.UNKNOWN
            )
            self.assertIsNone(metrics[f"{subject.lower()}.pa_per_hr"].value)

    def test_doubleheader_counts_two_games_and_one_hr_game(self):
        season = self.season()
        first, second = self.sequence(
            season, "doubleheader", (complete_step(1), complete_step(0))
        )
        for number, game_id in enumerate((first, second), start=1):
            game = Game.objects.get(pk=game_id)
            game.official_date = date(2098, 4, 1)
            game.scheduled_game_number = number
            game.full_clean()
            game.save()
        for subject in ("PLAYER", "TEAM"):
            selection, metrics = self.metrics(season, subject)
            prefix = subject.lower()
            self.assertEqual(selection.actual_game_count, 2)
            self.assert_value(metrics, f"{prefix}.hr", 1, 1)
            self.assert_value(metrics, f"{prefix}.hr_games", 1, 1)
            self.assert_value(metrics, f"{prefix}.hr_per_game", Decimal("0.5"), 1, 2)
            self.assert_value(metrics, f"{prefix}.hr_game_pct", Decimal(50), 1, 2)

    def test_trade_and_represented_team_filter_preserve_pa_scope(self):
        season = self.season()
        self.sequence(
            season, "trade-a", (complete_step(1),), team=self.a, opponent=self.c
        )
        self.sequence(
            season,
            "trade-b",
            (complete_step(0), complete_step(2, 2)),
            team=self.b,
            opponent=self.c,
            start=date(2098, 4, 2),
        )
        selection, overall = self.metrics(season)
        self.assertEqual(selection.actual_game_count, 3)
        self.assert_value(overall, "player.hr", 3, 3)
        self.assert_value(overall, "player.hr_games", 2, 2)
        _, a_metrics = self.metrics(season, represented_team=self.a)
        self.assert_value(a_metrics, "player.hr", 1, 1)
        b_selection, b_metrics = self.metrics(season, represented_team=self.b)
        self.assertEqual(b_selection.actual_game_count, 2)
        self.assert_value(b_metrics, "player.hr", 2, 2)
        self.assert_value(b_metrics, "player.hr_games", 1, 1)
        self.assert_value(b_metrics, "player.pa", 3, 3)

    def test_same_player_two_teams_in_one_contest_is_scoped_exactly(self):
        season = self.season()
        (game_id,) = self.sequence(season, "both-team", (complete_step(1),))
        game = Game.objects.get(pk=game_id)
        row = PlayerGameParticipation(
            id=fixture_uuid("b09:both:b:participation"),
            game=game,
            player=self.slugger,
            team=self.b,
            participation_state=PlayerGameParticipation.State.APPEARED,
            pa_coverage=PlayerGameParticipation.Coverage.COMPLETE,
            reported_pa_count=1,
        )
        row.full_clean()
        row.save()
        pa = PlateAppearance(
            id=fixture_uuid("b09:both:b:pa"),
            game=game,
            batter=self.slugger,
            batting_team=self.b,
            fielding_team=self.a,
            game_pa_ordinal=2,
            outcome_category=PlateAppearance.Outcome.HOME_RUN,
        )
        pa.full_clean()
        pa.save()
        event = HomeRunEvent(id=fixture_uuid("b09:both:b:hr"), plate_appearance=pa)
        event.full_clean()
        event.save()
        overall_selection, overall = self.metrics(season)
        self.assertEqual(overall_selection.actual_game_count, 1)
        self.assert_value(overall, "player.hr", 2, 2)
        self.assert_value(overall, "player.hr_games", 1, 1)
        for team in (self.a, self.b):
            filtered_selection, metrics = self.metrics(season, represented_team=team)
            self.assertEqual(filtered_selection.actual_game_count, 1)
            self.assert_value(metrics, "player.hr", 1, 1)
            self.assert_value(metrics, "player.pa", 1, 1)

    def test_fewer_than_30_games_and_home_away_filter_before_window(self):
        season = self.season()
        self.sequence(
            season,
            "home-away",
            (
                complete_step(0, home=False),
                complete_step(1, home=True),
                complete_step(1, home=False),
                complete_step(2, 2, home=True),
            ),
        )
        selection, all_metrics = self.metrics(season, "TEAM", window="30G")
        self.assertEqual((selection.requested_n, selection.actual_game_count), (30, 4))
        self.assert_value(all_metrics, "team.hr_per_game", Decimal(1), 4, 4)
        away_selection, away = self.metrics(
            season, "TEAM", window="30G", home_away="AWAY"
        )
        self.assertEqual(away_selection.actual_game_count, 2)
        self.assert_value(away, "team.hr", 1, 1)
        self.assert_value(away, "team.hr_game_pct", Decimal(50), 1, 2)

    def test_historical_game_cutoff_excludes_later_hr(self):
        season = self.season()
        ids = self.sequence(
            season,
            "historical",
            (complete_step(1), complete_step(0), complete_step(2, 2)),
        )
        for subject in ("PLAYER", "TEAM"):
            selection, metrics = self.metrics(season, subject, cutoff=ids[1])
            self.assertEqual(selection.actual_game_count, 2)
            self.assert_value(metrics, f"{subject.lower()}.hr", 1, 1)

    def test_unknown_pitcher_does_not_block_batter_hr(self):
        season = self.season()
        self.sequence(season, "unknown-pitcher", (complete_step(1),))
        self.assertFalse(PlateAppearance.objects.filter(pitcher__isnull=False).exists())
        _, metrics = self.metrics(season)
        self.assert_value(metrics, "player.hr", 1, 1)

    def test_complete_zero_hr_five_pa_and_empty_scope_semantics(self):
        season = self.season()
        self.sequence(season, "five-zero", (complete_step(0, 5),))
        _, metrics = self.metrics(season)
        self.assert_value(metrics, "player.hr_per_pa", Decimal(0), 0, 5)
        self.assertEqual(metrics["player.pa_per_hr"].reason, "NO_HOME_RUNS_IN_SCOPE")
        empty_team_selection, empty_team = self.metrics(
            season, "TEAM", home_away="AWAY"
        )
        self.assertEqual(empty_team_selection.actual_game_count, 0)
        for suffix in ("hr", "pa", "hr_games", "multi_hr_games"):
            self.assert_value(empty_team, f"team.{suffix}", 0, 0)
        for suffix in ("hr_per_game", "hr_game_pct"):
            self.assertEqual(
                (
                    empty_team[f"team.{suffix}"].state,
                    empty_team[f"team.{suffix}"].reason,
                ),
                (MetricState.NOT_APPLICABLE, "NO_GAMES"),
            )
        self.assertEqual(empty_team["team.hr_per_pa"].reason, "ZERO_DENOMINATOR")
        self.assertEqual(empty_team["team.pa_per_hr"].reason, "NO_HOME_RUNS_IN_SCOPE")

        # Explicit DNP gives a resolved empty player batting-game scope.
        game = Game.objects.get(season=season)
        dnp = PlayerGameParticipation(
            id=fixture_uuid("b09:empty-player-dnp"),
            game=game,
            player=self.regular,
            team=self.a,
            participation_state=PlayerGameParticipation.State.DID_NOT_APPEAR,
            pa_coverage=PlayerGameParticipation.Coverage.NOT_APPLICABLE,
        )
        dnp.full_clean()
        dnp.save()
        player_selection = select_player_window(season=season, player=self.regular)
        empty_player = compute_player_production_metrics(player_selection)
        self.assertEqual(player_selection.actual_game_count, 0)
        for suffix in ("hr", "pa", "hr_games", "multi_hr_games"):
            self.assert_value(empty_player, f"player.{suffix}", 0, 0)
        self.assertEqual(empty_player["player.hr_per_game"].reason, "NO_GAMES")
        self.assertEqual(empty_player["player.hr_game_pct"].reason, "NO_GAMES")
        self.assertEqual(empty_player["player.hr_per_pa"].reason, "ZERO_DENOMINATOR")
        self.assertEqual(
            empty_player["player.pa_per_hr"].reason,
            "NO_HOME_RUNS_IN_SCOPE",
        )

    def test_fixed_internal_tie_numeric_but_boundary_membership_nonnumeric(self):
        season = self.season()
        first, second = self.sequence(
            season, "tie", (complete_step(1), complete_step(0))
        )
        second_game = Game.objects.get(pk=second)
        second_game.official_date = date(2098, 4, 1)
        second_game.full_clean()
        second_game.save()
        self.sequence(
            season,
            "after-tie",
            (complete_step(0),) * 6,
            start=date(2098, 4, 3),
        )
        for subject in ("PLAYER", "TEAM"):
            fixed, fixed_metrics = self.metrics(season, subject, window="SEASON")
            self.assertEqual(fixed.membership_state, MembershipState.RESOLVED)
            self.assertEqual(fixed.order_state, OrderState.UNVERIFIED)
            self.assert_value(fixed_metrics, f"{subject.lower()}.hr", 1, 1)
            boundary, metrics = self.metrics(season, subject, window="7G")
            self.assertEqual(
                boundary.membership_state, MembershipState.ORDER_UNVERIFIED
            )
            self.assertTrue(
                all(
                    metric.state == MetricState.ORDER_UNVERIFIED
                    and metric.value is None
                    for metric in metrics.values()
                )
            )
        self.assertNotEqual(first, second)

    def test_complete_coverage_with_hr_identity_mismatch_blocks_hr_only(self):
        season = self.season()
        (game_id,) = self.sequence(season, "integrity", (complete_step(0),))
        pa = PlateAppearance.objects.get(game_id=game_id, batter=self.slugger)
        pa.outcome_category = PlateAppearance.Outcome.HOME_RUN
        pa.full_clean()
        pa.save()
        for subject in ("PLAYER", "TEAM"):
            _, metrics = self.metrics(season, subject)
            prefix = subject.lower()
            self.assert_value(metrics, f"{prefix}.pa", 1, 1)
            for name, result in metrics.items():
                if name != f"{prefix}.pa":
                    self.assertEqual(result.state, MetricState.INCOMPLETE, name)
                    self.assertEqual(result.reason, "BOX_SCORE_HR_MISMATCH")

    def test_player_pa_remains_numeric_if_game_pa_projection_is_partial(self):
        season = self.season()
        (game_id,) = self.sequence(season, "player-pa", (complete_step(0, 2),))
        row = GameDataCoverage.objects.get(
            game_id=game_id, domain=GameDataCoverage.Domain.PLATE_APPEARANCES
        )
        row.state = GameDataCoverage.State.PARTIAL
        row.full_clean()
        row.save()
        player_selection, player = self.metrics(season)
        self.assertEqual(player_selection.membership_state, MembershipState.RESOLVED)
        self.assert_value(player, "player.pa", 2, 2)
        self.assertEqual(player["player.hr"].state, MetricState.INCOMPLETE)
        _, team = self.metrics(season, "TEAM")
        self.assertEqual(team["team.pa"].state, MetricState.INCOMPLETE)

    def test_subject_mismatch_is_rejected(self):
        season = self.season()
        self.sequence(season, "subject", (complete_step(0),))
        team_selection = select_team_window(season=season, team=self.a)
        player_selection = select_player_window(season=season, player=self.slugger)
        with self.assertRaises(ValueError):
            compute_player_production_metrics(team_selection)
        with self.assertRaises(ValueError):
            compute_team_production_metrics(player_selection)

    def test_reported_player_pa_count_reconciles_without_replacing_rows(self):
        season = self.season()
        (game_id,) = self.sequence(season, "reported-pa", (complete_step(1, 3),))
        row = PlayerGameParticipation.objects.get(game_id=game_id, player=self.slugger)
        for reported, expected in (
            (3, MetricState.VALUE),
            (4, MetricState.INCOMPLETE),
            (2, MetricState.INCOMPLETE),
            (None, MetricState.VALUE),
        ):
            with self.subTest(reported=reported):
                row.reported_pa_count = reported
                row.full_clean()
                row.save()
                _, player = self.metrics(season)
                for name in ("pa", "hr_per_pa", "pa_per_hr", "hr", "hr_games"):
                    self.assertEqual(player[f"player.{name}"].state, expected)
                    if expected == MetricState.INCOMPLETE:
                        self.assertEqual(
                            player[f"player.{name}"].reason, "BOX_SCORE_PA_MISMATCH"
                        )
                _, team = self.metrics(season, "TEAM")
                self.assert_value(team, "team.pa", 3, 3)
                self.assert_value(team, "team.hr", 1, 1)
