"""Deterministic synthetic observations; never real MLB evidence or G06 proof."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from types import MappingProxyType
from typing import Mapping
from uuid import UUID, uuid5

from django.db import models, transaction

from domain.models import (
    CoverageReason,
    Game,
    GameDataCoverage,
    GameLifecycleEvent,
    HomeRunEvent,
    PlateAppearance,
    Player,
    PlayerGameParticipation,
    PlayerTeamAffiliation,
    Season,
    Team,
    Venue,
)
from ingestion.models import (
    CANONICAL_TARGETS,
    FactSourceLink,
    Provider,
    RawSourceSnapshot,
    SourceRecordReference,
)

FIXTURE_NAMESPACE = UUID("8fa0fa60-7e30-4b2d-b028-d119b0627400")
FIXTURE_YEAR = 2099
FIXTURE_INSTANT = datetime(2099, 5, 1, 12, tzinfo=timezone.utc)
FIXTURE_HASH = sha256(b"MLB HR Intelligence B06 SYNTHETIC assertions v1").hexdigest()


def fixture_uuid(key: str) -> UUID:
    """Stable identity derived from a semantic key, never insertion order."""
    return uuid5(FIXTURE_NAMESPACE, f"b06:{key}")


@dataclass(frozen=True)
class SequenceStep:
    """One synthetic candidate game; coverage is always explicit."""

    participation: str | None
    player_pa_coverage: str | None
    participation_coverage: str
    game_pa_coverage: str
    game_hr_coverage: str
    pa_count: int
    hr_count: int
    home: bool = True
    ordinal_known: bool = True
    reason_code: str | None = None

    def __post_init__(self):
        if self.pa_count < 0 or not 0 <= self.hr_count <= self.pa_count:
            raise ValueError("HR count must be between zero and PA count.")
        if (
            self.participation != PlayerGameParticipation.State.APPEARED
            and self.pa_count
        ):
            raise ValueError("Only an APPEARED player may have fixture PAs.")
        if self.participation is None and self.player_pa_coverage is not None:
            raise ValueError("An unassessed player has no player PA coverage row.")
        if self.participation is not None and self.player_pa_coverage is None:
            raise ValueError("An assessed player needs an explicit PA coverage state.")


def complete_step(
    hr_count: int, pa_count: int = 1, *, home: bool = True
) -> SequenceStep:
    """Explicit known-complete observation for compact KPI test sequences."""
    return SequenceStep(
        participation=PlayerGameParticipation.State.APPEARED,
        player_pa_coverage=PlayerGameParticipation.Coverage.COMPLETE,
        participation_coverage=GameDataCoverage.State.COMPLETE,
        game_pa_coverage=GameDataCoverage.State.COMPLETE,
        game_hr_coverage=GameDataCoverage.State.COMPLETE,
        pa_count=pa_count,
        hr_count=hr_count,
        home=home,
    )


@dataclass(frozen=True)
class FixtureManifest:
    season_id: UUID
    team_ids: Mapping[str, UUID]
    player_ids: Mapping[str, UUID]
    game_ids: Mapping[str, UUID]
    pa_ids: Mapping[str, UUID]
    hr_event_ids: Mapping[str, UUID]
    scenarios: Mapping[str, tuple[UUID, ...]]

    def __deepcopy__(self, memo):
        # All members are immutable; Django TestCase may deepcopy setUpTestData.
        return self


class FixtureDriftError(RuntimeError):
    """A fixed fixture key already exists with different canonical content."""


class _Builder:
    def __init__(self, provider: Provider | None = None, snapshot=None):
        self.provider = provider
        self.snapshot = snapshot
        self.games: dict[str, UUID] = {}
        self.pas: dict[str, UUID] = {}
        self.hrs: dict[str, UUID] = {}

    def ensure(self, model: type[models.Model], key: str, **values):
        """Explicitly validate before every canonical/provenance insert.

        B22 publication must do the same: bulk writes and QuerySet.update bypass
        model clean() and cannot stand in for canonical validation.
        """
        candidate = model(id=fixture_uuid(key), **values)
        existing = model.objects.filter(pk=candidate.pk).first()
        if existing is not None:
            for field in model._meta.concrete_fields:
                if getattr(existing, field.attname) != getattr(
                    candidate, field.attname
                ):
                    raise FixtureDriftError(f"Fixture {key} differs at {field.name}.")
            existing.full_clean()
            return existing
        candidate.full_clean()
        candidate.save()
        return candidate

    def source(self, key: str):
        if self.provider is None:
            return None
        return self.ensure(
            SourceRecordReference,
            f"source:{key}",
            provider=self.provider,
            snapshot=self.snapshot,
            resource_kind="synthetic_assertion",
            source_record_key=key,
            retrieved_at_utc=FIXTURE_INSTANT,
        )

    def support(self, key: str, obj, source=None):
        if source is None:
            return
        kind = next(
            name for name, model in CANONICAL_TARGETS.items() if type(obj) is model
        )
        self.ensure(
            FactSourceLink,
            f"link:{key}:{kind}:{obj.pk}",
            source_record=source,
            entity_kind=kind,
            canonical_entity_id=obj.pk,
            relation=FactSourceLink.Relation.SUPPORTS,
        )

    def game(
        self,
        key: str,
        season: Season,
        home: Team,
        away: Team,
        venue: Venue,
        official_date: date,
        *,
        game_number: int | None = None,
        scheduled_start: datetime | None = None,
        completed_at: datetime | None = None,
        finality: str = Game.Finality.FINAL,
        status: str = Game.Status.COMPLETED,
    ) -> Game:
        game = self.ensure(
            Game,
            f"game:{key}",
            season=season,
            home_team=home,
            away_team=away,
            venue=venue,
            official_date=official_date,
            game_type=Game.Type.REGULAR,
            finality=finality,
            status=status,
            scheduled_game_number=game_number,
            scheduled_start_at_utc=scheduled_start,
            completed_at_utc=completed_at,
        )
        self.games[key] = game.id
        return game

    def participation(
        self,
        key: str,
        game: Game,
        player: Player,
        team: Team,
        *,
        state: str,
        pa_coverage: str,
        reported_pa_count: int | None = None,
        source=None,
    ):
        row = self.ensure(
            PlayerGameParticipation,
            f"participation:{key}:{player.id}:{team.id}",
            game=game,
            player=player,
            team=team,
            participation_state=state,
            pa_coverage=pa_coverage,
            reported_pa_count=reported_pa_count,
        )
        self.support(key, row, source)
        return row

    def pa(
        self,
        key: str,
        game: Game,
        player: Player,
        batting_team: Team,
        fielding_team: Team,
        *,
        ordinal: int | None,
        home_run: bool,
        source=None,
    ) -> PlateAppearance:
        pa = self.ensure(
            PlateAppearance,
            f"pa:{key}",
            game=game,
            batter=player,
            batting_team=batting_team,
            fielding_team=fielding_team,
            game_pa_ordinal=ordinal,
            outcome_category=(
                PlateAppearance.Outcome.HOME_RUN
                if home_run
                else PlateAppearance.Outcome.NON_HR
            ),
        )
        self.pas[key] = pa.id
        self.support(key, pa, source)
        if home_run:
            event = self.ensure(HomeRunEvent, f"hr:{key}", plate_appearance=pa)
            self.hrs[key] = event.id
            self.support(key, event, source)
        return pa

    def coverage(
        self,
        key: str,
        game: Game,
        domain: str,
        state: str,
        *,
        reason_code: str | None = None,
        source=None,
    ):
        row = self.ensure(
            GameDataCoverage,
            f"coverage:{key}:{domain}",
            game=game,
            domain=domain,
            state=state,
            reason_code=reason_code,
            assessed_at_utc=FIXTURE_INSTANT,
        )
        self.support(key, row, source)
        return row

    def observed_game(
        self,
        key: str,
        season: Season,
        player: Player,
        batting_team: Team,
        opponent: Team,
        venue: Venue,
        official_date: date,
        step: SequenceStep,
        *,
        game_number: int | None = None,
    ) -> Game:
        home, away = (batting_team, opponent) if step.home else (opponent, batting_team)
        game = self.game(
            key,
            season,
            home,
            away,
            venue,
            official_date,
            game_number=game_number,
        )
        source = self.source(key)
        if step.participation is not None:
            self.participation(
                key,
                game,
                player,
                batting_team,
                state=step.participation,
                pa_coverage=step.player_pa_coverage,
                reported_pa_count=(
                    step.pa_count
                    if step.participation == PlayerGameParticipation.State.APPEARED
                    and step.player_pa_coverage
                    == PlayerGameParticipation.Coverage.COMPLETE
                    else None
                ),
                source=source,
            )
        for index in range(step.pa_count):
            self.pa(
                f"{key}:{index + 1}",
                game,
                player,
                batting_team,
                opponent,
                ordinal=index + 1 if step.ordinal_known else None,
                home_run=index < step.hr_count,
                source=source,
            )
        for domain, state in (
            (GameDataCoverage.Domain.PARTICIPATION, step.participation_coverage),
            (GameDataCoverage.Domain.PLATE_APPEARANCES, step.game_pa_coverage),
            (GameDataCoverage.Domain.HR_EVENTS, step.game_hr_coverage),
        ):
            self.coverage(
                key,
                game,
                domain,
                state,
                reason_code=(
                    step.reason_code
                    if state != GameDataCoverage.State.COMPLETE
                    else None
                ),
                source=source,
            )
        return game


def build_batting_sequence(
    *,
    key: str,
    season: Season,
    player: Player,
    batting_team: Team,
    opponent: Team,
    venue: Venue,
    start_date: date,
    steps: tuple[SequenceStep, ...],
) -> tuple[UUID, ...]:
    """Generate compact 7/15/30G candidates without selecting a window."""
    builder = _Builder()
    with transaction.atomic():
        return tuple(
            builder.observed_game(
                f"sequence:{key}:{index + 1}",
                season,
                player,
                batting_team,
                opponent,
                venue,
                start_date + timedelta(days=index),
                step,
            ).id
            for index, step in enumerate(steps)
        )


def load_synthetic_fixtures() -> FixtureManifest:
    """Load the small B06 fixture pack without HTTP, approvals or destructive reset."""
    with transaction.atomic():
        builder = _Builder()
        season = builder.ensure(
            Season,
            "season:synthetic",
            year=FIXTURE_YEAR,
            label="SYNTHETIC FIXTURE SEASON",
        )
        teams = {
            slug: builder.ensure(
                Team, f"team:{slug}", display_name=f"Synthetic {slug.upper()}"
            )
            for slug in ("a", "b", "c")
        }
        players = {
            slug: builder.ensure(
                Player, f"player:{slug}", display_name=f"Fixture {name}"
            )
            for slug, name in (
                ("slugger", "Slugger"),
                ("regular", "Regular"),
                ("walker", "Walker"),
                ("runner", "Runner"),
            )
        }
        venue = builder.ensure(Venue, "venue:synthetic", name="Synthetic Park")
        provider = builder.ensure(
            Provider,
            "provider:synthetic",
            code="SYNTHETIC",
            display_name="Synthetic fixture assertions only",
            enabled=False,
        )
        # Metadata intentionally has no backing blob or HTTP response: B06 assertions
        # are developer-authored examples, never provider proof or replayable G06 data.
        snapshot = builder.ensure(
            RawSourceSnapshot,
            "snapshot:synthetic",
            provider=provider,
            resource_kind="synthetic_fixture_manifest",
            external_target="fixture:b06:v1",
            request_fingerprint=FIXTURE_HASH,
            retrieved_at_utc=FIXTURE_INSTANT,
            checksum_sha256=FIXTURE_HASH,
            storage_key=(f"raw/synthetic/{FIXTURE_HASH[:2]}/{FIXTURE_HASH}.json.gz"),
            content_type="application/x-synthetic-fixture",
        )
        builder.provider = provider
        builder.snapshot = snapshot

        a, b, c = teams["a"], teams["b"], teams["c"]
        slugger, regular = players["slugger"], players["regular"]
        walker, runner = players["walker"], players["runner"]

        def day(number: int) -> date:
            return date(FIXTURE_YEAR, 4, number)

        scenario_games: dict[str, tuple[UUID, ...]] = {}

        def observed(name, player, batting_team, opponent, day_number, step, **kwargs):
            game = builder.observed_game(
                name,
                season,
                player,
                batting_team,
                opponent,
                venue,
                day(day_number),
                step,
                **kwargs,
            )
            scenario_games[name] = (game.id,)
            return game

        observed("ordinary", regular, a, b, 1, complete_step(0))
        observed("known_zero", slugger, a, b, 2, complete_step(0))
        observed("multi_hr", slugger, a, b, 3, complete_step(2, 4))
        observed("walk_only", walker, a, b, 4, complete_step(0))
        zero_pa = observed("zero_pa", runner, a, b, 5, complete_step(0, 0))
        zero_source = builder.source("zero_pa")
        builder.participation(
            "zero_pa:regular",
            zero_pa,
            regular,
            a,
            state=PlayerGameParticipation.State.APPEARED,
            pa_coverage=PlayerGameParticipation.Coverage.COMPLETE,
            reported_pa_count=1,
            source=zero_source,
        )
        builder.pa(
            "zero_pa:regular:1",
            zero_pa,
            regular,
            a,
            b,
            ordinal=1,
            home_run=False,
            source=zero_source,
        )
        dnp = observed(
            "dnp",
            slugger,
            a,
            b,
            6,
            SequenceStep(
                participation=PlayerGameParticipation.State.DID_NOT_APPEAR,
                player_pa_coverage=PlayerGameParticipation.Coverage.NOT_APPLICABLE,
                participation_coverage=GameDataCoverage.State.COMPLETE,
                game_pa_coverage=GameDataCoverage.State.COMPLETE,
                game_hr_coverage=GameDataCoverage.State.COMPLETE,
                pa_count=0,
                hr_count=0,
            ),
        )
        dnp_source = builder.source("dnp")
        builder.participation(
            "dnp:regular",
            dnp,
            regular,
            a,
            state=PlayerGameParticipation.State.APPEARED,
            pa_coverage=PlayerGameParticipation.Coverage.COMPLETE,
            reported_pa_count=1,
            source=dnp_source,
        )
        builder.pa(
            "dnp:regular:1",
            dnp,
            regular,
            a,
            b,
            ordinal=1,
            home_run=False,
            source=dnp_source,
        )
        observed(
            "unknown_participation",
            slugger,
            a,
            b,
            7,
            SequenceStep(
                participation=PlayerGameParticipation.State.UNKNOWN,
                player_pa_coverage=PlayerGameParticipation.Coverage.UNKNOWN,
                participation_coverage=GameDataCoverage.State.UNKNOWN,
                game_pa_coverage=GameDataCoverage.State.UNKNOWN,
                game_hr_coverage=GameDataCoverage.State.UNKNOWN,
                pa_count=0,
                hr_count=0,
            ),
        )
        observed(
            "unassessed",
            slugger,
            a,
            b,
            8,
            SequenceStep(
                participation=None,
                player_pa_coverage=None,
                participation_coverage=GameDataCoverage.State.UNKNOWN,
                game_pa_coverage=GameDataCoverage.State.UNKNOWN,
                game_hr_coverage=GameDataCoverage.State.UNKNOWN,
                pa_count=0,
                hr_count=0,
            ),
        )
        observed(
            "partial_pa",
            slugger,
            a,
            b,
            9,
            SequenceStep(
                participation=PlayerGameParticipation.State.APPEARED,
                player_pa_coverage=PlayerGameParticipation.Coverage.PARTIAL,
                participation_coverage=GameDataCoverage.State.PARTIAL,
                game_pa_coverage=GameDataCoverage.State.PARTIAL,
                game_hr_coverage=GameDataCoverage.State.UNKNOWN,
                pa_count=1,
                hr_count=0,
                reason_code=CoverageReason.SOURCE_TRUNCATED,
            ),
        )
        observed(
            "unknown_hr",
            slugger,
            a,
            b,
            10,
            SequenceStep(
                participation=PlayerGameParticipation.State.APPEARED,
                player_pa_coverage=PlayerGameParticipation.Coverage.COMPLETE,
                participation_coverage=GameDataCoverage.State.COMPLETE,
                game_pa_coverage=GameDataCoverage.State.COMPLETE,
                game_hr_coverage=GameDataCoverage.State.UNKNOWN,
                pa_count=1,
                hr_count=0,
                reason_code=CoverageReason.SOURCE_REQUEST_FAILED,
            ),
        )

        for label, team, start, end in (
            ("a_first", a, day(1), day(12)),
            ("b", b, day(12), day(14)),
            ("a_return", a, day(14), None),
        ):
            affiliation = builder.ensure(
                PlayerTeamAffiliation,
                f"affiliation:slugger:{label}",
                player=slugger,
                team=team,
                season=season,
                effective_from_date=start,
                effective_to_date_exclusive=end,
                boundary_precision=PlayerTeamAffiliation.BoundaryPrecision.DATE,
            )
            builder.support(label, affiliation, builder.source(f"affiliation:{label}"))
        trade_ids = []
        for label, team, day_number, hr_count in (
            ("trade_a", a, 11, 1),
            ("trade_b_zero", b, 12, 0),
            ("trade_b_multi", b, 13, 2),
            ("return_a", a, 14, 1),
        ):
            trade_ids.append(
                observed(
                    label,
                    slugger,
                    team,
                    c,
                    day_number,
                    complete_step(hr_count, max(1, hr_count)),
                ).id
            )
        scenario_games["trade"] = tuple(trade_ids[:3])
        scenario_games["return_to_team"] = (trade_ids[3],)

        doubleheader_ids = []
        for number, hr_count in ((1, 1), (2, 0)):
            doubleheader_ids.append(
                observed(
                    f"doubleheader_{number}",
                    slugger,
                    a,
                    b,
                    15,
                    complete_step(hr_count),
                    game_number=number,
                ).id
            )
        scenario_games["doubleheader"] = tuple(doubleheader_ids)

        suspended = builder.game(
            "suspended",
            season,
            a,
            b,
            venue,
            day(16),
            scheduled_start=datetime(FIXTURE_YEAR, 4, 16, 18, tzinfo=timezone.utc),
            completed_at=datetime(FIXTURE_YEAR, 4, 18, 21, tzinfo=timezone.utc),
        )
        scenario_games["suspended"] = (suspended.id,)
        suspended_source = builder.source("suspended")
        for kind, instant in (
            (
                GameLifecycleEvent.Kind.SCHEDULED,
                datetime(FIXTURE_YEAR, 4, 15, 12, tzinfo=timezone.utc),
            ),
            (
                GameLifecycleEvent.Kind.STARTED,
                datetime(FIXTURE_YEAR, 4, 16, 18, tzinfo=timezone.utc),
            ),
            (
                GameLifecycleEvent.Kind.SUSPENDED,
                datetime(FIXTURE_YEAR, 4, 16, 22, tzinfo=timezone.utc),
            ),
            (
                GameLifecycleEvent.Kind.RESUMED,
                datetime(FIXTURE_YEAR, 4, 18, 18, tzinfo=timezone.utc),
            ),
            (
                GameLifecycleEvent.Kind.COMPLETED,
                datetime(FIXTURE_YEAR, 4, 18, 21, tzinfo=timezone.utc),
            ),
        ):
            lifecycle = builder.ensure(
                GameLifecycleEvent,
                f"lifecycle:suspended:{kind}",
                game=suspended,
                event_kind=kind,
                effective_at_utc=instant,
                recorded_at_utc=instant,
            )
            builder.support("suspended", lifecycle, suspended_source)
        builder.participation(
            "suspended",
            suspended,
            slugger,
            a,
            state=PlayerGameParticipation.State.APPEARED,
            pa_coverage=PlayerGameParticipation.Coverage.COMPLETE,
            reported_pa_count=1,
            source=suspended_source,
        )
        builder.pa(
            "suspended:1",
            suspended,
            slugger,
            a,
            b,
            ordinal=1,
            home_run=True,
            source=suspended_source,
        )
        for domain in (
            GameDataCoverage.Domain.PARTICIPATION,
            GameDataCoverage.Domain.PLATE_APPEARANCES,
            GameDataCoverage.Domain.HR_EVENTS,
        ):
            builder.coverage(
                "suspended",
                suspended,
                domain,
                GameDataCoverage.State.COMPLETE,
                source=suspended_source,
            )

        both = builder.game("both_teams", season, a, b, venue, day(19))
        scenario_games["both_teams"] = (both.id,)
        both_source = builder.source("both_teams")
        for team, opponent, ordinal, hr_count in ((a, b, 1, 1), (b, a, 2, 0)):
            builder.participation(
                f"both_teams:{team.id}",
                both,
                slugger,
                team,
                state=PlayerGameParticipation.State.APPEARED,
                pa_coverage=PlayerGameParticipation.Coverage.COMPLETE,
                reported_pa_count=1,
                source=both_source,
            )
            builder.pa(
                f"both_teams:{team.id}:1",
                both,
                slugger,
                team,
                opponent,
                ordinal=ordinal,
                home_run=bool(hr_count),
                source=both_source,
            )
        for domain in (
            GameDataCoverage.Domain.PARTICIPATION,
            GameDataCoverage.Domain.PLATE_APPEARANCES,
            GameDataCoverage.Domain.HR_EVENTS,
        ):
            builder.coverage(
                "both_teams",
                both,
                domain,
                GameDataCoverage.State.COMPLETE,
                source=both_source,
            )

        unordered_ids = []
        for number, hr_count in ((1, 1), (2, 0)):
            unordered_ids.append(
                observed(
                    f"same_day_unordered_{number}",
                    slugger,
                    a,
                    b,
                    20,
                    complete_step(hr_count),
                ).id
            )
        scenario_games["same_day_unordered"] = tuple(unordered_ids)

        known_sequence = []
        for index, hr_count in enumerate((1, 0, 1, 0, 1), start=1):
            known_sequence.append(
                observed(
                    f"known_sequence_{index}",
                    slugger,
                    a,
                    b,
                    20 + index,
                    complete_step(hr_count, home=index % 2 == 1),
                ).id
            )
        scenario_games["known_sequence"] = tuple(known_sequence)

        return FixtureManifest(
            season_id=season.id,
            team_ids=MappingProxyType({name: team.id for name, team in teams.items()}),
            player_ids=MappingProxyType(
                {name: player.id for name, player in players.items()}
            ),
            game_ids=MappingProxyType(builder.games.copy()),
            pa_ids=MappingProxyType(builder.pas.copy()),
            hr_event_ids=MappingProxyType(builder.hrs.copy()),
            scenarios=MappingProxyType(scenario_games.copy()),
        )
