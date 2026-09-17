"""B08 semantic values, current coverage gates and matrix evidence."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone
from decimal import Decimal

from django.test import TestCase

from analytics.coverage import (
    MatrixCellEvidence,
    MatrixCellState,
    assess_game_hr_zero,
    assess_hr_zero,
    evaluate_game_coverage,
    evaluate_selection_coverage,
    resolve_matrix_cell,
)
from analytics.values import MetricState, MetricValue
from analytics.windows import select_player_window, select_team_window
from domain.fixtures import fixture_uuid, load_synthetic_fixtures
from domain.models import (
    Game,
    GameDataCoverage,
    PlateAppearance,
    Player,
    PlayerGameParticipation,
    Season,
    Team,
)


class MetricValueTests(TestCase):
    def test_numeric_zero_and_nonzero_are_values(self):
        zero = MetricValue(MetricState.VALUE, 0, "HR", 0, 3)
        nonzero = MetricValue(MetricState.VALUE, Decimal("1.5"), "HR/PA", 3, 2)
        self.assertEqual(zero.value, 0)
        self.assertEqual(nonzero.value, Decimal("1.5"))
        self.assertNotEqual(zero.state, MetricState.UNKNOWN)
        with self.assertRaises(FrozenInstanceError):
            zero.value = None

    def test_all_nonnumeric_states_keep_no_numeric_value(self):
        for state in (
            MetricState.NOT_APPLICABLE,
            MetricState.UNKNOWN,
            MetricState.INCOMPLETE,
            MetricState.ORDER_UNVERIFIED,
            MetricState.INSUFFICIENT_HISTORY,
        ):
            result = MetricValue(state, numerator=2, denominator=3, reason="NO_GAMES")
            self.assertIsNone(result.value)
            self.assertEqual(result.numerator, 2)
            self.assertEqual(result.denominator, 3)

    def test_invalid_combinations_raise(self):
        invalid = (
            {"state": MetricState.VALUE},
            {"state": MetricState.VALUE, "value": True},
            {"state": MetricState.VALUE, "value": float("nan")},
            {"state": MetricState.VALUE, "value": 2, "denominator": 0},
            {"state": MetricState.VALUE, "value": 0, "reason": "NO_GAMES"},
            {"state": MetricState.UNKNOWN, "value": 0},
            {"state": MetricState.UNKNOWN, "reason": "not machine readable"},
            {"state": MetricState.INCOMPLETE, "denominator": -1},
            {"state": "UNKNOWN"},
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                MetricValue(**kwargs)


class CoverageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = load_synthetic_fixtures()
        cls.a = Team.objects.get(pk=cls.fixture.team_ids["a"])
        cls.b = Team.objects.get(pk=cls.fixture.team_ids["b"])
        cls.c = Team.objects.get(pk=cls.fixture.team_ids["c"])
        cls.slugger = Player.objects.get(pk=cls.fixture.player_ids["slugger"])
        cls.runner = Player.objects.get(pk=cls.fixture.player_ids["runner"])

    def game(self, name):
        return Game.objects.get(pk=self.fixture.game_ids[name])

    def current(self, game, domain):
        return GameDataCoverage.objects.get(game=game, domain=domain)

    def change_coverage(self, game, domain, state, reason=None):
        row = self.current(game, domain)
        row.state = state
        row.reason_code = reason
        row.full_clean()
        row.save()

    def create_game(
        self,
        key,
        day,
        home=None,
        away=None,
        finality=Game.Finality.FINAL,
        season=None,
    ):
        game = Game(
            id=fixture_uuid(f"b08:game:{key}"),
            season=season or self.game("known_zero").season,
            home_team=home or self.a,
            away_team=away or self.b,
            official_date=day,
            game_type=Game.Type.REGULAR,
            finality=finality,
            status=Game.Status.COMPLETED
            if finality == Game.Finality.FINAL
            else Game.Status.SCHEDULED,
        )
        game.full_clean()
        game.save()
        return game

    def create_coverage(self, key, game, domain, state):
        row = GameDataCoverage(
            id=fixture_uuid(f"b08:coverage:{key}:{domain}"),
            game=game,
            domain=domain,
            state=state,
            assessed_at_utc=datetime(2099, 4, 1, tzinfo=timezone.utc),
        )
        row.full_clean()
        row.save()
        return row

    def test_four_domains_and_four_states_are_independent(self):
        game = self.game("known_zero")
        domains = GameDataCoverage.Domain
        self.create_coverage(
            "schedule", game, domains.SCHEDULE, GameDataCoverage.State.COMPLETE
        )
        for domain in domains.values:
            gate = evaluate_game_coverage(game, (domain,))
            self.assertEqual(gate.state, MetricState.VALUE)
            self.assertIn(domain, {item.domain for item in gate.evidence})
        for domain in domains.values:
            row = self.current(game, domain)
            for state, expected in (
                (GameDataCoverage.State.PARTIAL, MetricState.INCOMPLETE),
                (GameDataCoverage.State.UNKNOWN, MetricState.UNKNOWN),
                (GameDataCoverage.State.UNAVAILABLE, MetricState.UNKNOWN),
                (GameDataCoverage.State.COMPLETE, MetricState.VALUE),
            ):
                row.state = state
                row.full_clean()
                row.save()
                gate = evaluate_game_coverage(game, (domain,))
                self.assertEqual(gate.state, expected)
                self.assertEqual(
                    next(item.state for item in gate.evidence if item.domain == domain),
                    state,
                )
        schedule = self.current(game, domains.SCHEDULE)
        schedule.state = GameDataCoverage.State.UNAVAILABLE
        schedule.reason_code = "ACCESS_NOT_APPROVED"
        schedule.full_clean()
        schedule.save()
        self.assertEqual(
            evaluate_game_coverage(game, (domains.SCHEDULE,)).reason,
            "ACCESS_NOT_APPROVED",
        )

    def test_schedule_complete_and_finality_do_not_prove_hr_coverage(self):
        game = self.game("unassessed")
        self.create_coverage(
            "schedule-unassessed",
            game,
            GameDataCoverage.Domain.SCHEDULE,
            GameDataCoverage.State.COMPLETE,
        )
        self.assertEqual(game.finality, Game.Finality.FINAL)
        self.assertEqual(
            evaluate_game_coverage(game, (GameDataCoverage.Domain.SCHEDULE,)).state,
            MetricState.VALUE,
        )
        for domain in (
            GameDataCoverage.Domain.PARTICIPATION,
            GameDataCoverage.Domain.PLATE_APPEARANCES,
            GameDataCoverage.Domain.HR_EVENTS,
        ):
            self.assertEqual(
                evaluate_game_coverage(game, (domain,)).state, MetricState.UNKNOWN
            )
        missing = self.create_game("final-no-coverage", date(2099, 4, 26))
        self.assertEqual(
            evaluate_game_coverage(missing, (GameDataCoverage.Domain.HR_EVENTS,)).state,
            MetricState.UNKNOWN,
        )

    def test_nonfinal_cannot_claim_complete_pa_or_hr(self):
        game = self.create_game(
            "nonfinal-claimed-complete",
            date(2099, 4, 27),
            finality=Game.Finality.NOT_FINAL,
        )
        for domain in (
            GameDataCoverage.Domain.PLATE_APPEARANCES,
            GameDataCoverage.Domain.HR_EVENTS,
        ):
            self.create_coverage(
                "nonfinal", game, domain, GameDataCoverage.State.COMPLETE
            )
        gate = evaluate_game_coverage(game, (GameDataCoverage.Domain.HR_EVENTS,))
        self.assertEqual(gate.state, MetricState.UNKNOWN)
        self.assertEqual(gate.reason, "FINALITY_UNKNOWN")

    def test_unknown_dominates_partial_and_reasons_survive(self):
        game = self.game("known_zero")
        self.change_coverage(
            game,
            GameDataCoverage.Domain.PLATE_APPEARANCES,
            GameDataCoverage.State.PARTIAL,
            "SOURCE_TRUNCATED",
        )
        self.change_coverage(
            game,
            GameDataCoverage.Domain.HR_EVENTS,
            GameDataCoverage.State.UNKNOWN,
            "SOURCE_REQUEST_FAILED",
        )
        gate = evaluate_game_coverage(
            game,
            (
                GameDataCoverage.Domain.PLATE_APPEARANCES,
                GameDataCoverage.Domain.HR_EVENTS,
            ),
        )
        self.assertEqual(gate.state, MetricState.UNKNOWN)
        self.assertEqual(gate.reason, "SOURCE_REQUEST_FAILED")
        self.assertEqual({e.state for e in gate.evidence}, {"PARTIAL", "UNKNOWN"})

    def test_hr_complete_requires_current_pa_complete(self):
        game = self.game("known_zero")
        self.change_coverage(
            game,
            GameDataCoverage.Domain.PLATE_APPEARANCES,
            GameDataCoverage.State.UNKNOWN,
        )
        gate = evaluate_game_coverage(game, (GameDataCoverage.Domain.HR_EVENTS,))
        self.assertEqual(gate.state, MetricState.UNKNOWN)
        self.assertEqual(
            tuple(item.domain for item in gate.evidence),
            (
                GameDataCoverage.Domain.PLATE_APPEARANCES,
                GameDataCoverage.Domain.HR_EVENTS,
            ),
        )
        self.assertIsNone(assess_game_hr_zero(game).is_zero)
        self.assertEqual(
            resolve_matrix_cell(game, self.slugger, self.a).state,
            MatrixCellState.UNKNOWN,
        )

    def test_selected_scope_gate_uses_membership_then_current_coverage(self):
        resolved = select_team_window(season=2099, team=self.a, cutoff=date(2099, 4, 2))
        self.assertEqual(
            evaluate_selection_coverage(
                resolved, (GameDataCoverage.Domain.HR_EVENTS,)
            ).state,
            MetricState.VALUE,
        )
        self.change_coverage(
            self.game("known_zero"),
            GameDataCoverage.Domain.HR_EVENTS,
            GameDataCoverage.State.PARTIAL,
            "SOURCE_TRUNCATED",
        )
        gate = evaluate_selection_coverage(
            resolved, (GameDataCoverage.Domain.HR_EVENTS,)
        )
        self.assertEqual(gate.state, MetricState.INCOMPLETE)
        self.assertEqual(gate.reason, "SOURCE_TRUNCATED")
        uncertain = select_player_window(
            season=2099, player=self.slugger, cutoff=date(2099, 4, 8)
        )
        self.assertEqual(
            evaluate_selection_coverage(
                uncertain, (GameDataCoverage.Domain.HR_EVENTS,)
            ).state,
            MetricState.UNKNOWN,
        )
        tied = select_team_window(
            season=2099, team=self.a, cutoff=self.game("same_day_unordered_1").id
        )
        self.assertEqual(
            evaluate_selection_coverage(
                tied, (GameDataCoverage.Domain.HR_EVENTS,)
            ).state,
            MetricState.ORDER_UNVERIFIED,
        )

    def test_order_gate_only_applies_when_metric_needs_order(self):
        season = Season(
            id=fixture_uuid("b08:season:order"),
            year=2098,
            label="B08 SYNTHETIC ORDER",
        )
        season.full_clean()
        season.save()
        for number in (1, 2):
            game = self.create_game(f"order:{number}", date(2098, 4, 1), season=season)
            for domain in (
                GameDataCoverage.Domain.PLATE_APPEARANCES,
                GameDataCoverage.Domain.HR_EVENTS,
            ):
                self.create_coverage(
                    f"order:{number}", game, domain, GameDataCoverage.State.COMPLETE
                )
        selection = select_team_window(season=season, team=self.a)
        normal = evaluate_selection_coverage(
            selection, (GameDataCoverage.Domain.HR_EVENTS,)
        )
        ordered = evaluate_selection_coverage(
            selection, (GameDataCoverage.Domain.HR_EVENTS,), order_sensitive=True
        )
        self.assertEqual(normal.state, MetricState.VALUE)
        self.assertEqual(ordered.state, MetricState.ORDER_UNVERIFIED)

    def test_verified_zero_requires_current_complete_proof_and_downgrades(self):
        game = self.game("known_zero")
        self.assertEqual(assess_game_hr_zero(game).is_zero, True)
        for state, expected in (
            (GameDataCoverage.State.PARTIAL, MetricState.INCOMPLETE),
            (GameDataCoverage.State.UNKNOWN, MetricState.UNKNOWN),
        ):
            self.change_coverage(game, GameDataCoverage.Domain.HR_EVENTS, state)
            result = assess_game_hr_zero(game)
            self.assertEqual(result.state, expected)
            self.assertIsNone(result.is_zero)

    def test_empty_events_without_complete_proof_are_not_zero(self):
        for name, expected in (
            ("unknown_hr", MetricState.UNKNOWN),
            ("partial_pa", MetricState.UNKNOWN),
        ):
            result = assess_game_hr_zero(self.game(name))
            self.assertEqual(result.state, expected)
            self.assertIsNone(result.is_zero)
        game = self.game("known_zero")
        self.change_coverage(
            game, GameDataCoverage.Domain.HR_EVENTS, GameDataCoverage.State.PARTIAL
        )
        result = assess_game_hr_zero(game)
        self.assertEqual(result.state, MetricState.INCOMPLETE)
        self.assertIsNone(result.is_zero)

    def test_game_team_player_zero_scopes_are_distinct(self):
        game = self.game("both_teams")
        self.assertEqual(assess_game_hr_zero(game).is_zero, False)
        self.assertEqual(assess_hr_zero(game, team=self.a).is_zero, False)
        self.assertEqual(assess_hr_zero(game, team=self.b).is_zero, True)
        self.assertEqual(
            assess_hr_zero(game, team=self.b, player=self.slugger).is_zero, True
        )
        self.assertEqual(
            assess_hr_zero(game, team=self.a, player=self.slugger).is_zero, False
        )

    def test_matrix_hr_counts_zero_dnp_zero_pa_and_both_teams(self):
        cases = (
            ("trade_a", self.slugger, self.a, MatrixCellState.HR_COUNT, 1),
            ("multi_hr", self.slugger, self.a, MatrixCellState.HR_COUNT, 2),
            ("known_zero", self.slugger, self.a, MatrixCellState.KNOWN_ZERO, 0),
            ("dnp", self.slugger, self.a, MatrixCellState.DNP, None),
            ("zero_pa", self.runner, self.a, MatrixCellState.ZERO_PA_APPEARANCE, None),
            ("both_teams", self.slugger, self.a, MatrixCellState.HR_COUNT, 1),
            ("both_teams", self.slugger, self.b, MatrixCellState.KNOWN_ZERO, 0),
        )
        for name, player, team, state, count in cases:
            with self.subTest(name=name, team=team.id):
                result = resolve_matrix_cell(self.game(name), player, team)
                self.assertEqual((result.state, result.hr_count), (state, count))
                if state == MatrixCellState.HR_COUNT:
                    self.assertEqual(len(result.hr_event_ids), count)

    def test_missing_row_and_partial_evidence_never_become_dnp_or_zero(self):
        missing = resolve_matrix_cell(self.game("unassessed"), self.slugger, self.a)
        partial = resolve_matrix_cell(self.game("partial_pa"), self.slugger, self.a)
        unknown = resolve_matrix_cell(
            self.game("unknown_participation"), self.slugger, self.a
        )
        self.assertEqual(missing.state, MatrixCellState.UNKNOWN)
        self.assertEqual(partial.state, MatrixCellState.UNKNOWN)
        self.assertEqual(unknown.state, MatrixCellState.UNKNOWN)
        self.assertTrue(
            all(cell.hr_count is None for cell in (missing, partial, unknown))
        )

    def test_partial_player_pa_with_complete_hr_is_incomplete(self):
        game = self.game("partial_pa")
        self.change_coverage(
            game,
            GameDataCoverage.Domain.HR_EVENTS,
            GameDataCoverage.State.COMPLETE,
        )
        # The game's PA projection remains PARTIAL, so the cell is incomplete.
        cell = resolve_matrix_cell(game, self.slugger, self.a)
        self.assertEqual(cell.state, MatrixCellState.INCOMPLETE)
        self.assertIsNone(cell.hr_count)

    def test_unknown_participation_with_positive_pa_is_conflicting(self):
        game = self.game("known_zero")
        row = PlayerGameParticipation.objects.get(
            game=game, player=self.slugger, team=self.a
        )
        row.participation_state = PlayerGameParticipation.State.UNKNOWN
        row.full_clean()
        row.save()
        cell = resolve_matrix_cell(game, self.slugger, self.a)
        self.assertEqual(cell.state, MatrixCellState.INCOMPLETE)
        self.assertIsNone(cell.hr_count)

    def test_positive_hr_under_partial_or_unknown_coverage_keeps_event_id_only(self):
        game = self.game("trade_a")
        original = resolve_matrix_cell(game, self.slugger, self.a)
        self.assertEqual(original.state, MatrixCellState.HR_COUNT)
        for state, cell_state in (
            (GameDataCoverage.State.PARTIAL, MatrixCellState.INCOMPLETE),
            (GameDataCoverage.State.UNKNOWN, MatrixCellState.UNKNOWN),
        ):
            self.change_coverage(game, GameDataCoverage.Domain.HR_EVENTS, state)
            result = resolve_matrix_cell(game, self.slugger, self.a)
            self.assertEqual(result.state, cell_state)
            self.assertIsNone(result.hr_count)
            self.assertEqual(result.hr_event_ids, original.hr_event_ids)

    def test_not_with_team_requires_temporal_departure_and_other_affiliation(self):
        game = self.create_game("a-during-b", date(2099, 4, 12), self.a, self.c)
        not_with = resolve_matrix_cell(game, self.slugger, self.a)
        self.assertEqual(not_with.state, MatrixCellState.NOT_WITH_TEAM)
        # Later A return means the same inference cannot persist indefinitely.
        after_return = self.create_game(
            "a-after-return", date(2099, 4, 16), self.a, self.c
        )
        self.assertEqual(
            resolve_matrix_cell(after_return, self.slugger, self.a).state,
            MatrixCellState.UNKNOWN,
        )
        # A positive B observation in a both-team contest overrides the ended
        # B interval; one representation never proves non-affiliation elsewhere.
        self.assertEqual(
            resolve_matrix_cell(self.game("both_teams"), self.slugger, self.b).state,
            MatrixCellState.KNOWN_ZERO,
        )

    def test_other_team_appearance_or_absent_affiliation_is_not_proof(self):
        walker = Player.objects.get(pk=self.fixture.player_ids["walker"])
        game = self.create_game("walker-b-only", date(2099, 4, 26))
        row = PlayerGameParticipation(
            id=fixture_uuid("b08:walker-b-participation"),
            game=game,
            player=walker,
            team=self.b,
            participation_state=PlayerGameParticipation.State.APPEARED,
            pa_coverage=PlayerGameParticipation.Coverage.COMPLETE,
        )
        row.full_clean()
        row.save()
        pa = PlateAppearance(
            id=fixture_uuid("b08:walker-b-pa"),
            game=game,
            batter=walker,
            batting_team=self.b,
            fielding_team=self.a,
            outcome_category=PlateAppearance.Outcome.NON_HR,
        )
        pa.full_clean()
        pa.save()
        result = resolve_matrix_cell(game, walker, self.a)
        self.assertEqual(result.state, MatrixCellState.UNKNOWN)
        self.assertIsNone(result.hr_count)

    def test_complete_projection_with_unmatched_hr_pa_is_incomplete(self):
        game = self.create_game("unmatched-hr", date(2099, 4, 26))
        row = PlayerGameParticipation(
            id=fixture_uuid("b08:unmatched-participation"),
            game=game,
            player=self.slugger,
            team=self.a,
            participation_state=PlayerGameParticipation.State.APPEARED,
            pa_coverage=PlayerGameParticipation.Coverage.COMPLETE,
            reported_pa_count=1,
        )
        row.full_clean()
        row.save()
        pa = PlateAppearance(
            id=fixture_uuid("b08:unmatched-pa"),
            game=game,
            batter=self.slugger,
            batting_team=self.a,
            fielding_team=self.b,
            game_pa_ordinal=1,
            outcome_category=PlateAppearance.Outcome.HOME_RUN,
        )
        pa.full_clean()
        pa.save()
        for domain in (
            GameDataCoverage.Domain.PLATE_APPEARANCES,
            GameDataCoverage.Domain.HR_EVENTS,
        ):
            self.create_coverage(
                "unmatched-hr", game, domain, GameDataCoverage.State.COMPLETE
            )
        result = resolve_matrix_cell(game, self.slugger, self.a)
        self.assertEqual(result.state, MatrixCellState.INCOMPLETE)
        self.assertEqual(assess_game_hr_zero(game).state, MetricState.INCOMPLETE)

    def test_invalid_matrix_value_combinations_raise(self):
        for value in (
            MatrixCellEvidence(MatrixCellState.KNOWN_ZERO, 0),
            MatrixCellEvidence(MatrixCellState.UNKNOWN),
        ):
            self.assertIsInstance(value, MatrixCellEvidence)
        for state, count in (
            (MatrixCellState.HR_COUNT, 0),
            (MatrixCellState.HR_COUNT, True),
            (MatrixCellState.HR_COUNT, 1),
            (MatrixCellState.KNOWN_ZERO, None),
            (MatrixCellState.DNP, 0),
        ):
            with self.assertRaises(ValueError):
                MatrixCellEvidence(state, count)
