"""B10 recurrence acceptance cases over deterministic B06 builders."""

from datetime import date, datetime, timezone
from decimal import Decimal

from django.test import TestCase

from analytics.production import (
    compute_player_production_metrics,
    compute_team_production_metrics,
)
from analytics.recurrence import compute_player_recurrence, compute_team_recurrence
from analytics.values import MetricState
from analytics.windows import MembershipState, select_player_window, select_team_window
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
    GameLifecycleEvent,
    HomeRunEvent,
    PlateAppearance,
    Player,
    PlayerGameParticipation,
    Season,
    Team,
    Venue,
)


class RecurrenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        fixture = load_synthetic_fixtures()
        cls.a = Team.objects.get(pk=fixture.team_ids["a"])
        cls.b = Team.objects.get(pk=fixture.team_ids["b"])
        cls.c = Team.objects.get(pk=fixture.team_ids["c"])
        cls.player = Player.objects.get(pk=fixture.player_ids["slugger"])
        cls.venue = Venue.objects.get(name="Synthetic Park")

    def season(self, key="season", year=2097):
        row = Season(
            id=fixture_uuid(f"b10:{key}"), year=year, label=f"B10 SYNTHETIC {key}"
        )
        row.full_clean()
        row.save()
        return row

    def sequence(
        self,
        season,
        key,
        counts,
        *,
        team=None,
        opponent=None,
        start=None,
        pa_counts=None,
    ):
        pa_counts = pa_counts or [max(1, count) for count in counts]
        return build_batting_sequence(
            key=f"b10:{key}",
            season=season,
            player=self.player,
            batting_team=team or self.a,
            opponent=opponent or self.b,
            venue=self.venue,
            start_date=start or date(2097, 4, 1),
            steps=tuple(
                complete_step(count, pa_count)
                for count, pa_count in zip(counts, pa_counts)
            ),
        )

    def result(self, season, subject="PLAYER", **kwargs):
        if subject == "PLAYER":
            selection = select_player_window(
                season=season, player=self.player, **kwargs
            )
            return selection, compute_player_recurrence(selection)
        selection = select_team_window(season=season, team=self.a, **kwargs)
        return selection, compute_team_recurrence(selection)

    def assert_value(self, result, key, value, reason=None):
        metric = result.metrics[key]
        self.assertEqual(
            (metric.state, metric.value, metric.reason),
            (MetricState.VALUE, value, reason),
        )

    def test_consecutive_hr_gaps_and_streak_for_both_subjects(self):
        season = self.season()
        self.sequence(season, "consecutive", (1, 1))
        for subject in ("PLAYER", "TEAM"):
            _, result = self.result(season, subject)
            prefix = subject.lower()
            self.assertEqual(
                (result.gap_series.state, result.gap_series.values),
                (MetricState.VALUE, (0,)),
            )
            self.assertEqual(
                (result.gap_series.hr_game_count, result.gap_series.gap_count), (2, 1)
            )
            for name in (
                "avg_hr_gap_games",
                "median_hr_gap_games",
                "current_hr_drought_games",
                "max_hr_drought_games",
            ):
                self.assert_value(result, f"{prefix}.{name}", 0)
            for name in ("current_hr_streak_games", "max_hr_streak_games"):
                self.assert_value(result, f"{prefix}.{name}", 2)

    def test_internal_gap_and_even_median(self):
        season = self.season()
        self.sequence(season, "gaps", (1, 0, 1, 1))
        for subject in ("PLAYER", "TEAM"):
            _, result = self.result(season, subject)
            prefix = subject.lower()
            self.assertEqual(result.gap_series.values, (1, 0))
            self.assert_value(result, f"{prefix}.avg_hr_gap_games", Decimal("0.5"))
            self.assert_value(result, f"{prefix}.median_hr_gap_games", Decimal("0.5"))
            self.assertEqual(
                result.metrics[f"{prefix}.median_hr_gap_games"].denominator, 2
            )
            self.assert_value(result, f"{prefix}.max_hr_drought_games", 1)
            self.assert_value(result, f"{prefix}.current_hr_streak_games", 2)

    def test_single_multi_hr_game_has_insufficient_gap_history(self):
        season = self.season()
        self.sequence(season, "multi", (2,), pa_counts=(2,))
        for subject in ("PLAYER", "TEAM"):
            _, result = self.result(season, subject)
            self.assertEqual(result.gap_series.state, MetricState.INSUFFICIENT_HISTORY)
            self.assertEqual(result.gap_series.values, ())
            self.assertEqual(result.gap_series.hr_game_count, 1)
            self.assertEqual(
                result.metrics[f"{subject.lower()}.avg_hr_gap_games"].state,
                MetricState.INSUFFICIENT_HISTORY,
            )
            self.assert_value(result, f"{subject.lower()}.current_hr_streak_games", 1)

    def test_dnp_and_zero_pa_do_not_interrupt_player_sequence(self):
        for label, middle in (
            (
                "dnp",
                SequenceStep(
                    PlayerGameParticipation.State.DID_NOT_APPEAR,
                    PlayerGameParticipation.Coverage.NOT_APPLICABLE,
                    GameDataCoverage.State.COMPLETE,
                    GameDataCoverage.State.COMPLETE,
                    GameDataCoverage.State.COMPLETE,
                    0,
                    0,
                ),
            ),
            ("zero-pa", complete_step(0, 0)),
        ):
            with self.subTest(label=label):
                year = 2097 if label == "dnp" else 2096
                season = self.season(label, year=year)
                build_batting_sequence(
                    key=f"b10:{label}",
                    season=season,
                    player=self.player,
                    batting_team=self.a,
                    opponent=self.b,
                    venue=self.venue,
                    start_date=date(year, 4, 1),
                    steps=(complete_step(1), middle, complete_step(1)),
                )
                selection, result = self.result(
                    season,
                    cutoff=date(year, 4, 3),
                    window="7G",
                )
                self.assertEqual(
                    sum(
                        item.known_non_opportunity
                        for item in selection.full_scope_observations
                    ),
                    1,
                )
                self.assertEqual(result.gap_series.values[-1], 0)
                self.assert_value(result, "player.current_hr_streak_games", 2)

    def test_walk_and_no_hr_annotations(self):
        season = self.season()
        self.sequence(season, "walk", (0, 0, 0))
        for subject in ("PLAYER", "TEAM"):
            _, result = self.result(season, subject)
            prefix = subject.lower()
            self.assertEqual(result.gap_series.state, MetricState.INSUFFICIENT_HISTORY)
            self.assert_value(
                result, f"{prefix}.current_hr_drought_games", 3, "NO_HR_IN_SCOPE"
            )
            self.assert_value(
                result, f"{prefix}.max_hr_drought_games", 3, "NO_HR_IN_SCOPE"
            )
            self.assert_value(result, f"{prefix}.current_hr_streak_games", 0)
            self.assert_value(result, f"{prefix}.max_hr_streak_games", 0)

    def test_partial_middle_is_barrier_and_decisive_suffix_works(self):
        season = self.season()
        ids = self.sequence(season, "partial", (1, 0, 1))
        row = GameDataCoverage.objects.get(
            game_id=ids[1], domain=GameDataCoverage.Domain.HR_EVENTS
        )
        row.state = GameDataCoverage.State.PARTIAL
        row.full_clean()
        row.save()
        for subject in ("PLAYER", "TEAM"):
            _, result = self.result(season, subject)
            prefix = subject.lower()
            self.assertEqual(result.gap_series.state, MetricState.INCOMPLETE)
            self.assertEqual(
                result.metrics[f"{prefix}.max_hr_streak_games"].state,
                MetricState.INCOMPLETE,
            )
            self.assert_value(result, f"{prefix}.current_hr_drought_games", 0)
            self.assertEqual(
                result.metrics[f"{prefix}.current_hr_streak_games"].state,
                MetricState.INCOMPLETE,
            )
        # The older partial game does not poison a decisive latest non-HR streak.
        self.sequence(season, "after-partial", (0,), start=date(2097, 4, 4))
        _, result = self.result(season)
        self.assert_value(result, "player.current_hr_streak_games", 0)
        self.assert_value(result, "player.current_hr_drought_games", 1)

    def test_current_runs_extend_before_displayed_window(self):
        season = self.season()
        self.sequence(season, "long-drought", (1,) + (0,) * 41)
        for subject in ("PLAYER", "TEAM"):
            selection, result = self.result(season, subject, window="30G")
            self.assertEqual(selection.actual_game_count, 30)
            self.assert_value(result, f"{subject.lower()}.current_hr_drought_games", 41)
            self.assert_value(
                result, f"{subject.lower()}.max_hr_drought_games", 30, "NO_HR_IN_SCOPE"
            )

    def test_current_streak_extends_before_displayed_window(self):
        season = self.season()
        self.sequence(season, "long-streak", (1,) * 10)
        for subject in ("PLAYER", "TEAM"):
            _, result = self.result(season, subject, window="7G")
            self.assert_value(result, f"{subject.lower()}.current_hr_streak_games", 10)
            self.assert_value(result, f"{subject.lower()}.max_hr_streak_games", 7)

    def test_pa_drought_uses_ordinal_and_can_extend_before_window(self):
        season = self.season()
        self.sequence(
            season, "long-pa", (1,) + (0,) * 8, pa_counts=(1,) + (4,) * 7 + (17,)
        )
        _, result = self.result(season, window="7G")
        self.assert_value(result, "player.current_hr_drought_pa", 45)
        self.assert_value(result, "player.max_hr_drought_pa", 41, "NO_HR_IN_SCOPE")

    def test_pa_sequence_respects_event_ordinal(self):
        season = self.season()
        (game_id,) = self.sequence(season, "pa-order", (1,), pa_counts=(4,))
        pas = list(
            PlateAppearance.objects.filter(game_id=game_id).order_by("game_pa_ordinal")
        )
        event = HomeRunEvent.objects.get(plate_appearance=pas[0])
        event.delete()
        pas[0].outcome_category = PlateAppearance.Outcome.NON_HR
        pas[0].full_clean()
        pas[0].save()
        pas[2].outcome_category = PlateAppearance.Outcome.HOME_RUN
        pas[2].full_clean()
        pas[2].save()
        HomeRunEvent.objects.create(
            id=fixture_uuid("b10:pa-third-hr"), plate_appearance=pas[2]
        )
        _, result = self.result(season)
        self.assert_value(result, "player.current_hr_drought_pa", 1)
        self.assert_value(result, "player.max_hr_drought_pa", 2)

    def test_hr_followed_by_two_non_hr_pas(self):
        season = self.season()
        self.sequence(season, "pa-trailing", (1,), pa_counts=(3,))
        _, result = self.result(season)
        self.assert_value(result, "player.current_hr_drought_pa", 2)
        self.assert_value(result, "player.max_hr_drought_pa", 2)

    def test_pa_drought_45_beyond_seven_game_window_of_29_pas(self):
        season = self.season()
        self.sequence(
            season, "pa-45", (1,) + (0,) * 11, pa_counts=(1,) + (4,) * 10 + (5,)
        )
        _, result = self.result(season, window="7G")
        self.assert_value(result, "player.current_hr_drought_pa", 45)
        self.assert_value(result, "player.max_hr_drought_pa", 29, "NO_HR_IN_SCOPE")

    def test_latest_partial_blocks_current_metrics(self):
        season = self.season()
        ids = self.sequence(season, "latest-partial", (1, 0))
        row = GameDataCoverage.objects.get(
            game_id=ids[1], domain=GameDataCoverage.Domain.HR_EVENTS
        )
        row.state = GameDataCoverage.State.PARTIAL
        row.full_clean()
        row.save()
        for subject in ("PLAYER", "TEAM"):
            _, result = self.result(season, subject)
            for suffix in ("current_hr_drought_games", "current_hr_streak_games"):
                self.assertEqual(
                    result.metrics[f"{subject.lower()}.{suffix}"].state,
                    MetricState.INCOMPLETE,
                )

    def test_latest_unknown_player_candidate_is_not_skipped(self):
        season = self.season()
        unknown = SequenceStep(
            PlayerGameParticipation.State.UNKNOWN,
            PlayerGameParticipation.Coverage.UNKNOWN,
            GameDataCoverage.State.UNKNOWN,
            GameDataCoverage.State.UNKNOWN,
            GameDataCoverage.State.UNKNOWN,
            0,
            0,
        )
        build_batting_sequence(
            key="b10:unknown-latest",
            season=season,
            player=self.player,
            batting_team=self.a,
            opponent=self.b,
            venue=self.venue,
            start_date=date(2097, 4, 1),
            steps=(complete_step(1), unknown),
        )
        selection, result = self.result(season)
        self.assertEqual(selection.membership_state, MembershipState.UNKNOWN)
        self.assertEqual(result.gap_series.state, MetricState.UNKNOWN)
        self.assertEqual(
            result.metrics["player.current_hr_drought_games"].state, MetricState.UNKNOWN
        )

    def test_suspended_game_uses_original_official_date(self):
        season = self.season()
        first, second = self.sequence(season, "suspended", (1, 0))
        game = Game.objects.get(pk=first)
        game.completed_at_utc = datetime(2097, 4, 4, 21, tzinfo=timezone.utc)
        game.full_clean()
        game.save()
        for kind, day in (
            (GameLifecycleEvent.Kind.SUSPENDED, 1),
            (GameLifecycleEvent.Kind.RESUMED, 4),
        ):
            event = GameLifecycleEvent(
                id=fixture_uuid(f"b10:suspended:{kind}"),
                game=game,
                event_kind=kind,
                effective_at_utc=datetime(2097, 4, day, 20, tzinfo=timezone.utc),
                recorded_at_utc=datetime(2097, 4, day, 20, tzinfo=timezone.utc),
            )
            event.full_clean()
            event.save()
        _, result = self.result(season)
        self.assert_value(result, "player.current_hr_drought_games", 1)
        self.assertEqual(result.gap_series.state, MetricState.INSUFFICIENT_HISTORY)
        self.assertNotEqual(first, second)

    def test_reported_pa_mismatch_blocks_recurrence_but_not_team(self):
        season = self.season()
        (game_id,) = self.sequence(season, "reported", (1,), pa_counts=(3,))
        row = PlayerGameParticipation.objects.get(game_id=game_id, player=self.player)
        row.reported_pa_count = 4
        row.full_clean()
        row.save()
        selection, result = self.result(season)
        self.assertEqual(
            result.metrics["player.current_hr_drought_pa"].state, MetricState.INCOMPLETE
        )
        self.assertEqual(
            result.metrics["player.max_hr_drought_pa"].reason, "BOX_SCORE_PA_MISMATCH"
        )
        self.assertEqual(
            compute_player_production_metrics(selection)["player.pa"].state,
            MetricState.INCOMPLETE,
        )
        team_selection = select_team_window(season=season, team=self.a)
        self.assertEqual(
            compute_team_production_metrics(team_selection)["team.pa"].value, 3
        )
        self.assert_value(
            compute_team_recurrence(team_selection), "team.current_hr_drought_games", 0
        )

    def test_tied_uniform_groups_are_safe_mixed_group_is_not(self):
        season = self.season()
        first, second = self.sequence(season, "tie", (1, 1))
        game = Game.objects.get(pk=second)
        game.official_date = date(2097, 4, 1)
        game.full_clean()
        game.save()
        for subject in ("PLAYER", "TEAM"):
            selection, result = self.result(season, subject)
            self.assertEqual(selection.membership_state, MembershipState.RESOLVED)
            self.assertEqual(result.gap_series.values, (0,))
            self.assert_value(result, f"{subject.lower()}.current_hr_streak_games", 2)
        event = HomeRunEvent.objects.get(plate_appearance__game_id=second)
        pa = event.plate_appearance
        event.delete()
        pa.outcome_category = PlateAppearance.Outcome.NON_HR
        pa.full_clean()
        pa.save()
        for subject in ("PLAYER", "TEAM"):
            _, result = self.result(season, subject)
            self.assertEqual(result.gap_series.state, MetricState.ORDER_UNVERIFIED)
            self.assertEqual(
                result.metrics[f"{subject.lower()}.current_hr_streak_games"].state,
                MetricState.ORDER_UNVERIFIED,
            )
        self.assertNotEqual(first, second)

    def test_tied_non_hr_games_with_unequal_pa_counts_are_still_deterministic(self):
        season = self.season()
        ids = self.sequence(season, "tie-zero", (0, 0), pa_counts=(1, 2))
        game = Game.objects.get(pk=ids[1])
        game.official_date = date(2097, 4, 1)
        game.full_clean()
        game.save()
        for subject in ("PLAYER", "TEAM"):
            _, result = self.result(season, subject)
            self.assert_value(
                result,
                f"{subject.lower()}.current_hr_drought_games",
                2,
                "NO_HR_IN_SCOPE",
            )
        _, player = self.result(season)
        self.assert_value(player, "player.current_hr_drought_pa", 3, "NO_HR_IN_SCOPE")
        self.assert_value(player, "player.max_hr_drought_pa", 3, "NO_HR_IN_SCOPE")

    def test_doubleheader_order_and_game_cutoff(self):
        season = self.season()
        first, second, third = self.sequence(season, "doubleheader", (1, 0, 1))
        for number, game_id in enumerate((first, second), start=1):
            game = Game.objects.get(pk=game_id)
            game.official_date = date(2097, 4, 1)
            game.scheduled_game_number = number
            game.full_clean()
            game.save()
        for subject in ("PLAYER", "TEAM"):
            _, result = self.result(season, subject, cutoff=second)
            self.assert_value(result, f"{subject.lower()}.current_hr_drought_games", 1)
            self.assert_value(result, f"{subject.lower()}.current_hr_streak_games", 0)
            _, full = self.result(season, subject)
            self.assertEqual(full.gap_series.values, (1,))
        self.assertNotEqual(second, third)

    def test_nonfinal_game_is_not_a_recurrence_opportunity(self):
        season = self.season()
        ids = self.sequence(season, "nonfinal", (1, 0, 1))
        game = Game.objects.get(pk=ids[1])
        game.finality = Game.Finality.NOT_FINAL
        game.status = Game.Status.POSTPONED
        game.full_clean()
        game.save()
        _, result = self.result(season)
        self.assertEqual(result.gap_series.values, (0,))
        self.assert_value(result, "player.current_hr_streak_games", 2)

    def test_trade_filter_and_home_away_precede_recurrence(self):
        season = self.season()
        self.sequence(season, "trade-a", (1,), team=self.a, opponent=self.c)
        self.sequence(
            season,
            "trade-b",
            (0, 2),
            team=self.b,
            opponent=self.c,
            start=date(2097, 4, 2),
        )
        _, overall = self.result(season)
        self.assertEqual(overall.gap_series.values, (1,))
        self.assert_value(overall, "player.current_hr_streak_games", 1)
        _, filtered = self.result(season, represented_team=self.b)
        self.assertEqual(filtered.gap_series.state, MetricState.INSUFFICIENT_HISTORY)
        self.assert_value(filtered, "player.current_hr_streak_games", 1)
        _, home = self.result(season, represented_team=self.b, home_away="HOME")
        self.assert_value(home, "player.current_hr_drought_games", 0)

    def test_single_pa_with_null_ordinal_has_unambiguous_drought(self):
        season = self.season()
        build_batting_sequence(
            key="b10:single-null",
            season=season,
            player=self.player,
            batting_team=self.a,
            opponent=self.b,
            venue=self.venue,
            start_date=date(2097, 4, 1),
            steps=(
                SequenceStep(
                    PlayerGameParticipation.State.APPEARED,
                    PlayerGameParticipation.Coverage.COMPLETE,
                    GameDataCoverage.State.COMPLETE,
                    GameDataCoverage.State.COMPLETE,
                    GameDataCoverage.State.COMPLETE,
                    1,
                    0,
                    ordinal_known=False,
                ),
            ),
        )
        _, result = self.result(season)
        self.assert_value(result, "player.current_hr_drought_pa", 1, "NO_HR_IN_SCOPE")
        self.assert_value(result, "player.max_hr_drought_pa", 1, "NO_HR_IN_SCOPE")

    def test_boundary_tie_blocks_window_local_recurrence(self):
        season = self.season()
        ids = self.sequence(season, "boundary", (1,) * 8)
        game = Game.objects.get(pk=ids[1])
        game.official_date = date(2097, 4, 1)
        game.full_clean()
        game.save()
        for subject in ("PLAYER", "TEAM"):
            selection, result = self.result(season, subject, window="7G")
            self.assertEqual(
                selection.membership_state, MembershipState.ORDER_UNVERIFIED
            )
            self.assertEqual(result.gap_series.state, MetricState.ORDER_UNVERIFIED)
            self.assertEqual(
                result.metrics[f"{subject.lower()}.max_hr_streak_games"].state,
                MetricState.ORDER_UNVERIFIED,
            )

    def test_empty_scope_is_not_applicable(self):
        season = self.season()
        self.sequence(season, "empty", (0,))
        _, result = self.result(season, "TEAM", home_away="AWAY")
        self.assertEqual(
            (
                result.gap_series.state,
                result.gap_series.values,
                result.gap_series.reason,
                result.gap_series.hr_game_count,
                result.gap_series.gap_count,
            ),
            (MetricState.INSUFFICIENT_HISTORY, (), "INSUFFICIENT_HISTORY", 0, 0),
        )
        for name, item in result.metrics.items():
            expected = (
                (MetricState.INSUFFICIENT_HISTORY, "INSUFFICIENT_HISTORY")
                if name.endswith(("avg_hr_gap_games", "median_hr_gap_games"))
                else (MetricState.NOT_APPLICABLE, "NO_GAMES")
            )
            self.assertEqual((item.state, item.reason), expected)

    def test_unresolved_pa_ordinal_is_material_only_when_hr_status_differs(self):
        season = self.season()
        (game_id,) = build_batting_sequence(
            key="b10:unknown-pa",
            season=season,
            player=self.player,
            batting_team=self.a,
            opponent=self.b,
            venue=self.venue,
            start_date=date(2097, 4, 1),
            steps=(
                SequenceStep(
                    PlayerGameParticipation.State.APPEARED,
                    PlayerGameParticipation.Coverage.COMPLETE,
                    GameDataCoverage.State.COMPLETE,
                    GameDataCoverage.State.COMPLETE,
                    GameDataCoverage.State.COMPLETE,
                    2,
                    1,
                    ordinal_known=False,
                ),
            ),
        )
        _, result = self.result(season)
        self.assertEqual(
            result.metrics["player.current_hr_drought_pa"].state,
            MetricState.ORDER_UNVERIFIED,
        )
        self.assertEqual(
            result.metrics["player.max_hr_drought_pa"].state,
            MetricState.ORDER_UNVERIFIED,
        )
        pa = PlateAppearance.objects.filter(
            game_id=game_id, outcome_category=PlateAppearance.Outcome.NON_HR
        ).first()
        pa.game_pa_ordinal = 2
        pa.full_clean()
        pa.save()
        hr_pa = PlateAppearance.objects.get(
            game_id=game_id, outcome_category=PlateAppearance.Outcome.HOME_RUN
        )
        hr_pa.game_pa_ordinal = 1
        hr_pa.full_clean()
        hr_pa.save()
        _, fixed = self.result(season)
        self.assert_value(fixed, "player.current_hr_drought_pa", 1)
