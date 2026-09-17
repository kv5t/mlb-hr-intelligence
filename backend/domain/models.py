"""Canonical identities and contest observations; provider evidence arrives in B05."""

import uuid
from datetime import timezone

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone as django_timezone


def require_utc(instance, *names):
    errors = {}
    for name in names:
        value = getattr(instance, name)
        if value is not None and (
            django_timezone.is_naive(value)
            or value.utcoffset() != timezone.utc.utcoffset(value)
        ):
            errors[name] = "A known instant must be timezone-aware UTC."
    if errors:
        raise ValidationError(errors)


class CanonicalModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_id = self.id

    def save(self, *args, **kwargs):
        if not self._state.adding and self.id != self._original_id:
            raise ValidationError({"id": "Canonical identity cannot change."})
        return super().save(*args, **kwargs)


class Season(CanonicalModel):
    year = models.PositiveSmallIntegerField(unique=True)
    label = models.CharField(max_length=100, null=True, blank=True)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=40, null=True, blank=True)


class Team(CanonicalModel):
    mlb_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    display_name = models.CharField(max_length=200, null=True, blank=True)
    abbreviation = models.CharField(max_length=20, null=True, blank=True)
    league = models.CharField(max_length=80, null=True, blank=True)
    division = models.CharField(max_length=80, null=True, blank=True)
    active_from_on = models.DateField(null=True, blank=True)
    active_to_on = models.DateField(null=True, blank=True)


class Player(CanonicalModel):
    class Bats(models.TextChoices):
        LEFT = "L"
        RIGHT = "R"
        SWITCH = "S"
        UNKNOWN = "UNKNOWN"

    class Throws(models.TextChoices):
        LEFT = "L"
        RIGHT = "R"
        UNKNOWN = "UNKNOWN"

    mlb_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    display_name = models.CharField(max_length=200, null=True, blank=True)
    given_name = models.CharField(max_length=100, null=True, blank=True)
    family_name = models.CharField(max_length=100, null=True, blank=True)
    bats = models.CharField(max_length=7, choices=Bats, default=Bats.UNKNOWN)
    throws = models.CharField(max_length=7, choices=Throws, default=Throws.UNKNOWN)
    primary_position = models.CharField(max_length=30, null=True, blank=True)


class Venue(CanonicalModel):
    mlb_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    location = models.CharField(max_length=200, null=True, blank=True)
    timezone_id = models.CharField(max_length=100, null=True, blank=True)


class PlayerTeamAffiliation(CanonicalModel):
    class BoundaryPrecision(models.TextChoices):
        DATE = "DATE"
        UNKNOWN = "UNKNOWN"

    player = models.ForeignKey(Player, on_delete=models.PROTECT)
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    season = models.ForeignKey(Season, on_delete=models.PROTECT, null=True, blank=True)
    effective_from_date = models.DateField(null=True, blank=True)
    effective_to_date_exclusive = models.DateField(null=True, blank=True)
    boundary_precision = models.CharField(
        max_length=7, choices=BoundaryPrecision, default=BoundaryPrecision.UNKNOWN
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(effective_from_date__isnull=True)
                    | Q(effective_to_date_exclusive__isnull=True)
                    | Q(effective_from_date__lt=models.F("effective_to_date_exclusive"))
                ),
                name="affiliation_valid_known_interval",
            )
        ]
        indexes = [
            models.Index(fields=["player", "effective_from_date"]),
            models.Index(fields=["team", "effective_from_date"]),
        ]


class Game(CanonicalModel):
    class Type(models.TextChoices):
        REGULAR = "REGULAR"
        POSTSEASON = "POSTSEASON"
        SPRING = "SPRING"
        ALL_STAR = "ALL_STAR"
        OTHER = "OTHER"
        UNKNOWN = "UNKNOWN"

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED"
        POSTPONED = "POSTPONED"
        RESCHEDULED = "RESCHEDULED"
        IN_PROGRESS = "IN_PROGRESS"
        SUSPENDED = "SUSPENDED"
        COMPLETED = "COMPLETED"
        CANCELLED = "CANCELLED"
        OTHER = "OTHER"
        UNKNOWN = "UNKNOWN"

    class Finality(models.TextChoices):
        FINAL = "FINAL"
        NOT_FINAL = "NOT_FINAL"
        UNKNOWN = "UNKNOWN"

    season = models.ForeignKey(Season, on_delete=models.PROTECT)
    home_team = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="home_games"
    )
    away_team = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="away_games"
    )
    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, null=True, blank=True)
    mlb_game_pk = models.PositiveIntegerField(unique=True, null=True, blank=True)
    game_type = models.CharField(max_length=10, choices=Type, default=Type.UNKNOWN)
    official_date = models.DateField(null=True, blank=True)
    scheduled_start_at_utc = models.DateTimeField(null=True, blank=True)
    actual_start_at_utc = models.DateTimeField(null=True, blank=True)
    completed_at_utc = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status, default=Status.UNKNOWN)
    finality = models.CharField(
        max_length=9, choices=Finality, default=Finality.UNKNOWN
    )
    scheduled_game_number = models.PositiveSmallIntegerField(null=True, blank=True)
    home_score = models.PositiveSmallIntegerField(null=True, blank=True)
    away_score = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(home_team=models.F("away_team")),
                name="game_distinct_teams",
            )
        ]
        indexes = [
            models.Index(fields=["season", "official_date", "game_type"]),
            models.Index(fields=["home_team", "official_date"]),
            models.Index(fields=["away_team", "official_date"]),
        ]

    def clean(self):
        require_utc(
            self, "scheduled_start_at_utc", "actual_start_at_utc", "completed_at_utc"
        )


class GameLifecycleEvent(CanonicalModel):
    class Kind(models.TextChoices):
        SCHEDULED = "SCHEDULED"
        POSTPONED = "POSTPONED"
        RESCHEDULED = "RESCHEDULED"
        STARTED = "STARTED"
        SUSPENDED = "SUSPENDED"
        RESUMED = "RESUMED"
        COMPLETED = "COMPLETED"
        CANCELLED = "CANCELLED"
        OTHER = "OTHER"

    game = models.ForeignKey(Game, on_delete=models.PROTECT)
    event_kind = models.CharField(max_length=12, choices=Kind)
    effective_at_utc = models.DateTimeField(null=True, blank=True)
    recorded_at_utc = models.DateTimeField()
    scheduled_start_at_utc = models.DateTimeField(null=True, blank=True)

    def clean(self):
        require_utc(
            self, "effective_at_utc", "recorded_at_utc", "scheduled_start_at_utc"
        )


class PlayerGameParticipation(CanonicalModel):
    class State(models.TextChoices):
        APPEARED = "APPEARED"
        DID_NOT_APPEAR = "DID_NOT_APPEAR"
        UNKNOWN = "UNKNOWN"

    class Coverage(models.TextChoices):
        COMPLETE = "COMPLETE"
        PARTIAL = "PARTIAL"
        UNKNOWN = "UNKNOWN"
        NOT_APPLICABLE = "NOT_APPLICABLE"

    game = models.ForeignKey(Game, on_delete=models.PROTECT)
    player = models.ForeignKey(Player, on_delete=models.PROTECT)
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    participation_state = models.CharField(
        max_length=14, choices=State, default=State.UNKNOWN
    )
    started = models.BooleanField(null=True, blank=True)
    reported_pa_count = models.PositiveSmallIntegerField(null=True, blank=True)
    pa_coverage = models.CharField(
        max_length=14, choices=Coverage, default=Coverage.UNKNOWN
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game", "player", "team"], name="unique_game_player_team"
            )
        ]
        indexes = [
            models.Index(fields=["player", "game"]),
            models.Index(fields=["team", "game"]),
        ]

    def clean(self):
        if self.game_id and self.team_id:
            game = self.game
            if self.team_id not in (game.home_team_id, game.away_team_id):
                raise ValidationError({"team": "Team must participate in the game."})
        if (
            self.participation_state == self.State.DID_NOT_APPEAR
            and self.game_id
            and self.player_id
            and self.team_id
            and PlateAppearance.objects.filter(
                game_id=self.game_id,
                batter_id=self.player_id,
                batting_team_id=self.team_id,
            ).exists()
        ):
            raise ValidationError(
                {"participation_state": "A batter PA exists for this team."}
            )


class PlateAppearance(CanonicalModel):
    class Half(models.TextChoices):
        TOP = "TOP"
        BOTTOM = "BOTTOM"

    class Outcome(models.TextChoices):
        HOME_RUN = "HOME_RUN"
        NON_HR = "NON_HR"
        UNKNOWN = "UNKNOWN"

    game = models.ForeignKey(Game, on_delete=models.PROTECT)
    batter = models.ForeignKey(
        Player, on_delete=models.PROTECT, related_name="batting_pas"
    )
    batting_team = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="batting_pas"
    )
    fielding_team = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="fielding_pas"
    )
    pitcher = models.ForeignKey(
        Player,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pitching_pas",
    )
    inning = models.PositiveSmallIntegerField(null=True, blank=True)
    half_inning = models.CharField(max_length=6, choices=Half, null=True, blank=True)
    game_pa_ordinal = models.PositiveIntegerField(null=True, blank=True)
    outcome_category = models.CharField(
        max_length=8, choices=Outcome, default=Outcome.UNKNOWN
    )
    batter_side_used = models.CharField(
        max_length=1, choices=[("L", "L"), ("R", "R")], null=True, blank=True
    )
    pitcher_hand_used = models.CharField(
        max_length=1, choices=[("L", "L"), ("R", "R")], null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game", "game_pa_ordinal"], name="unique_known_game_pa_ordinal"
            ),
            models.CheckConstraint(
                condition=~Q(batting_team=models.F("fielding_team")),
                name="pa_distinct_teams",
            ),
            models.CheckConstraint(
                condition=Q(game_pa_ordinal__isnull=True) | Q(game_pa_ordinal__gt=0),
                name="pa_positive_known_ordinal",
            ),
        ]
        indexes = [
            models.Index(fields=["batter", "game"]),
            models.Index(fields=["pitcher", "game"]),
        ]

    def clean(self):
        if self.game_id and self.batting_team_id and self.fielding_team_id:
            teams = {self.game.home_team_id, self.game.away_team_id}
            if {self.batting_team_id, self.fielding_team_id} != teams:
                raise ValidationError(
                    "Batting and fielding teams must be the game's two teams."
                )
        if self.game_id and self.batter_id and self.batting_team_id:
            if PlayerGameParticipation.objects.filter(
                game_id=self.game_id,
                player_id=self.batter_id,
                team_id=self.batting_team_id,
                participation_state=PlayerGameParticipation.State.DID_NOT_APPEAR,
            ).exists():
                raise ValidationError(
                    "A batter PA conflicts with an affirmative DNP observation."
                )
        if (
            self.pk
            and self.outcome_category != self.Outcome.HOME_RUN
            and HomeRunEvent.objects.filter(plate_appearance_id=self.pk).exists()
        ):
            raise ValidationError(
                {"outcome_category": "An HR event already references this PA."}
            )


class HomeRunEvent(CanonicalModel):
    plate_appearance = models.OneToOneField(
        PlateAppearance, on_delete=models.PROTECT, related_name="home_run_event"
    )

    def clean(self):
        if (
            self.plate_appearance_id
            and self.plate_appearance.outcome_category
            != PlateAppearance.Outcome.HOME_RUN
        ):
            raise ValidationError(
                {"plate_appearance": "An HR event requires an HR PA."}
            )


class CoverageReason(models.TextChoices):
    SOURCE_REQUEST_FAILED = "SOURCE_REQUEST_FAILED"
    SOURCE_TRUNCATED = "SOURCE_TRUNCATED"
    PARSE_FAILED = "PARSE_FAILED"
    SCHEMA_DRIFT = "SCHEMA_DRIFT"
    FINALITY_UNKNOWN = "FINALITY_UNKNOWN"
    UNSUPPORTED_STATUS = "UNSUPPORTED_STATUS"
    STATUS_CONFLICT = "STATUS_CONFLICT"
    UNRESOLVED_PLAY = "UNRESOLVED_PLAY"
    NON_PA_PLAY_CLASSIFIED = "NON_PA_PLAY_CLASSIFIED"
    MISSING_BATTER = "MISSING_BATTER"
    DUPLICATE_ATBAT_INDEX = "DUPLICATE_ATBAT_INDEX"
    BOX_SCORE_PA_MISMATCH = "BOX_SCORE_PA_MISMATCH"
    BOX_SCORE_HR_MISMATCH = "BOX_SCORE_HR_MISMATCH"
    HR_WITHOUT_PA = "HR_WITHOUT_PA"
    TEAM_ATTRIBUTION_CONFLICT = "TEAM_ATTRIBUTION_CONFLICT"
    ORDER_UNRESOLVED = "ORDER_UNRESOLVED"
    PARTICIPATION_POPULATION_UNVERIFIED = "PARTICIPATION_POPULATION_UNVERIFIED"
    ACCESS_NOT_APPROVED = "ACCESS_NOT_APPROVED"


class GameDataCoverage(CanonicalModel):
    class Domain(models.TextChoices):
        SCHEDULE = "SCHEDULE"
        PARTICIPATION = "PARTICIPATION"
        PLATE_APPEARANCES = "PLATE_APPEARANCES"
        HR_EVENTS = "HR_EVENTS"

    class State(models.TextChoices):
        COMPLETE = "COMPLETE"
        PARTIAL = "PARTIAL"
        UNKNOWN = "UNKNOWN"
        UNAVAILABLE = "UNAVAILABLE"

    game = models.ForeignKey(Game, on_delete=models.PROTECT)
    domain = models.CharField(max_length=17, choices=Domain)
    state = models.CharField(max_length=11, choices=State, default=State.UNKNOWN)
    reason_code = models.CharField(
        max_length=40, choices=CoverageReason, null=True, blank=True
    )
    assessed_at_utc = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game", "domain"], name="unique_current_game_domain_coverage"
            )
        ]

    def clean(self):
        require_utc(self, "assessed_at_utc")
