"""Auditable source and operation metadata, without network behavior."""

import re
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

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
    require_utc,
)

# Deliberate registry: aliases and fact links cannot point at auth/operational rows.
CANONICAL_TARGETS = {
    "SEASON": Season,
    "TEAM": Team,
    "PLAYER": Player,
    "VENUE": Venue,
    "PLAYER_TEAM_AFFILIATION": PlayerTeamAffiliation,
    "GAME": Game,
    "GAME_LIFECYCLE_EVENT": GameLifecycleEvent,
    "PLAYER_GAME_PARTICIPATION": PlayerGameParticipation,
    "PLATE_APPEARANCE": PlateAppearance,
    "HOME_RUN_EVENT": HomeRunEvent,
    "GAME_DATA_COVERAGE": GameDataCoverage,
}
TARGET_CHOICES = [(kind, kind.replace("_", " ").title()) for kind in CANONICAL_TARGETS]


def validate_target(kind, target_id):
    target_model = CANONICAL_TARGETS.get(kind)
    if target_model is None:
        raise ValidationError({"entity_kind": "Unsupported canonical target kind."})
    if target_id and not target_model.objects.filter(pk=target_id).exists():
        raise ValidationError(
            {"canonical_entity_id": "Canonical target does not exist."}
        )


class UUIDRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class AppendOnlyRecord(UUIDRecord):
    """Normal writes may append but cannot edit/delete evidence records."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Audit record is append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit record cannot be deleted.")


class Provider(UUIDRecord):
    code = models.CharField(
        max_length=60,
        unique=True,
        validators=[RegexValidator(r"^[A-Z][A-Z0-9_]*$")],
    )
    display_name = models.CharField(max_length=150)
    enabled = models.BooleanField(default=False)


class ProviderAccessDecision(AppendOnlyRecord):
    class State(models.TextChoices):
        RESEARCH_ONLY = "RESEARCH_ONLY"
        APPROVED_FOR_AUTOMATED_USE = "APPROVED_FOR_AUTOMATED_USE"
        BLOCKED = "BLOCKED"
        UNKNOWN = "UNKNOWN"

    provider = models.ForeignKey(Provider, on_delete=models.PROTECT)
    state = models.CharField(max_length=26, choices=State, default=State.UNKNOWN)
    decision_reference = models.CharField(max_length=200, null=True, blank=True)
    allowed_operation = models.CharField(max_length=100, null=True, blank=True)
    safe_note = models.TextField(blank=True)
    recorded_at_utc = models.DateTimeField(default=timezone.now)
    expires_at_utc = models.DateTimeField(null=True, blank=True)

    def clean(self):
        require_utc(self, "recorded_at_utc", "expires_at_utc")
        if self.state == self.State.APPROVED_FOR_AUTOMATED_USE and not (
            self.decision_reference and self.allowed_operation
        ):
            raise ValidationError(
                "Approval requires an external reference and operation scope."
            )

    def permits(self, operation, at=None):
        at = at or timezone.now()
        return bool(
            self.state == self.State.APPROVED_FOR_AUTOMATED_USE
            and self.decision_reference
            and self.allowed_operation == operation
            and self.recorded_at_utc <= at
            and (self.expires_at_utc is None or at < self.expires_at_utc)
            and self.provider.enabled
        )


def provider_allows_automation(provider, operation, at=None):
    """Latest recorded decision wins; absent/unknown decisions deny by default."""
    at = at or timezone.now()
    decision = (
        ProviderAccessDecision.objects.filter(
            Q(allowed_operation=operation) | Q(allowed_operation__isnull=True),
            provider=provider,
            recorded_at_utc__lte=at,
        )
        .order_by("-recorded_at_utc", "-id")
        .first()
    )
    return decision.permits(operation, at) if decision else False


class ExternalIdentifier(UUIDRecord):
    class Resolution(models.TextChoices):
        ACTIVE = "ACTIVE"
        SUPERSEDED = "SUPERSEDED"
        AMBIGUOUS = "AMBIGUOUS"

    provider = models.ForeignKey(Provider, on_delete=models.PROTECT)
    entity_kind = models.CharField(max_length=30, choices=TARGET_CHOICES)
    external_value = models.CharField(max_length=200)
    canonical_entity_id = models.UUIDField()
    resolution_state = models.CharField(
        max_length=10, choices=Resolution, default=Resolution.ACTIVE
    )
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "entity_kind", "external_value"],
                condition=Q(resolution_state="ACTIVE"),
                name="unique_active_external_identifier",
            )
        ]
        indexes = [models.Index(fields=["entity_kind", "canonical_entity_id"])]

    def clean(self):
        validate_target(self.entity_kind, self.canonical_entity_id)
        if self.valid_from and self.valid_to and self.valid_from >= self.valid_to:
            raise ValidationError({"valid_to": "End must follow start."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            old = type(self).objects.get(pk=self.pk)
            fixed = (
                "provider_id",
                "entity_kind",
                "external_value",
                "canonical_entity_id",
            )
            if any(getattr(self, field) != getattr(old, field) for field in fixed):
                raise ValidationError("External mapping identity is immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("External mapping history cannot be deleted.")


class DataSyncRun(UUIDRecord):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        RUNNING = "RUNNING"
        SUCCEEDED = "SUCCEEDED"
        PARTIAL = "PARTIAL"
        FAILED = "FAILED"
        BLOCKED = "BLOCKED"

    provider = models.ForeignKey(Provider, on_delete=models.PROTECT)
    job_type = models.CharField(max_length=60)
    parameter_fingerprint = models.CharField(
        max_length=64, validators=[RegexValidator(r"^[0-9a-f]{64}$")]
    )
    scope_key = models.CharField(max_length=200)
    code_version = models.CharField(max_length=100, blank=True)
    config_version = models.CharField(max_length=100, blank=True)
    access_decision = models.ForeignKey(
        ProviderAccessDecision, on_delete=models.PROTECT, null=True, blank=True
    )
    started_at_utc = models.DateTimeField(default=timezone.now)
    finished_at_utc = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    attempted_count = models.PositiveIntegerField(default=0)
    succeeded_count = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=80, blank=True)

    def clean(self):
        require_utc(self, "started_at_utc", "finished_at_utc")
        if (
            self.access_decision_id
            and self.access_decision.provider_id != self.provider_id
        ):
            raise ValidationError(
                {"access_decision": "Decision provider must match run provider."}
            )


class RawSourceSnapshot(UUIDRecord):
    class ParseStatus(models.TextChoices):
        UNPARSED = "UNPARSED"
        PARSED = "PARSED"
        FAILED = "FAILED"

    provider = models.ForeignKey(Provider, on_delete=models.PROTECT)
    resource_kind = models.CharField(max_length=80)
    external_target = models.CharField(max_length=200)
    request_fingerprint = models.CharField(
        max_length=64, validators=[RegexValidator(r"^[0-9a-f]{64}$")]
    )
    retrieved_at_utc = models.DateTimeField(default=timezone.now)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    content_type = models.CharField(max_length=100, null=True, blank=True)
    checksum_sha256 = models.CharField(
        max_length=64, validators=[RegexValidator(r"^[0-9a-f]{64}$")]
    )
    storage_key = models.CharField(max_length=240)
    provider_reported_at_utc = models.DateTimeField(null=True, blank=True)
    parse_status = models.CharField(
        max_length=8, choices=ParseStatus, default=ParseStatus.UNPARSED
    )

    IMMUTABLE_FIELDS = (
        "id",
        "provider_id",
        "resource_kind",
        "external_target",
        "request_fingerprint",
        "retrieved_at_utc",
        "http_status",
        "content_type",
        "checksum_sha256",
        "storage_key",
        "provider_reported_at_utc",
    )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            stored = type(self).objects.get(pk=self.pk)
            if any(
                getattr(self, name) != getattr(stored, name)
                for name in self.IMMUTABLE_FIELDS
            ):
                raise ValidationError("Snapshot retrieval metadata is immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Snapshot evidence cannot be deleted.")

    def clean(self):
        require_utc(self, "retrieved_at_utc", "provider_reported_at_utc")
        if (
            not self.external_target
            or self.external_target.startswith("/")
            or any(
                part in self.external_target
                for part in ("://", "?", "&", "=", "\\", "..")
            )
        ):
            raise ValidationError({"external_target": "Use an opaque safe target key."})
        # An opaque relative content-addressed key, never an arbitrary path or URL.
        pattern = r"raw/([a-z0-9_-]+)/([0-9a-f]{2})/([0-9a-f]{64})\.json\.gz"
        match = re.fullmatch(pattern, self.storage_key or "")
        if not match or (
            match.group(1) != self.provider.code.lower()
            or match.group(2) != self.checksum_sha256[:2]
            or match.group(3) != self.checksum_sha256
        ):
            raise ValidationError(
                {"storage_key": "Expected a content-addressed raw storage key."}
            )


class DataSyncItem(UUIDRecord):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        RUNNING = "RUNNING"
        SUCCEEDED = "SUCCEEDED"
        PARTIAL = "PARTIAL"
        FAILED = "FAILED"
        BLOCKED = "BLOCKED"

    run = models.ForeignKey(DataSyncRun, on_delete=models.PROTECT)
    target_kind = models.CharField(max_length=80)
    target_key = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    checkpoint = models.CharField(max_length=80, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    last_error_code = models.CharField(max_length=80, blank=True)
    snapshot = models.ForeignKey(
        RawSourceSnapshot, on_delete=models.PROTECT, null=True, blank=True
    )
    canonical_revision = models.ForeignKey(
        "DatasetRevision", on_delete=models.PROTECT, null=True, blank=True
    )
    updated_at_utc = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "target_kind", "target_key"], name="unique_run_target"
            )
        ]

    def clean(self):
        require_utc(self, "updated_at_utc")
        if self.snapshot_id and self.snapshot.provider_id != self.run.provider_id:
            raise ValidationError(
                {"snapshot": "Snapshot provider must match run provider."}
            )


class SourceRecordReference(AppendOnlyRecord):
    provider = models.ForeignKey(Provider, on_delete=models.PROTECT)
    snapshot = models.ForeignKey(RawSourceSnapshot, on_delete=models.PROTECT)
    resource_kind = models.CharField(max_length=80)
    source_record_key = models.CharField(max_length=200, null=True, blank=True)
    record_path = models.CharField(max_length=200, blank=True)
    retrieved_at_utc = models.DateTimeField()
    provider_reported_at_utc = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "resource_kind", "source_record_key"],
                condition=Q(source_record_key__isnull=False) & ~Q(source_record_key=""),
                name="unique_snapshot_source_key",
            )
        ]

    def clean(self):
        require_utc(self, "retrieved_at_utc", "provider_reported_at_utc")
        if self.snapshot_id and self.provider_id != self.snapshot.provider_id:
            raise ValidationError({"provider": "Provider must match snapshot."})
        if self.snapshot_id and self.retrieved_at_utc != self.snapshot.retrieved_at_utc:
            raise ValidationError(
                {"retrieved_at_utc": "Use the snapshot retrieval instant."}
            )


class FactSourceLink(AppendOnlyRecord):
    class Relation(models.TextChoices):
        SUPPORTS = "SUPPORTS"
        CONFLICTS = "CONFLICTS"
        WITHDRAWN = "WITHDRAWN"
        UNRESOLVED = "UNRESOLVED"

    source_record = models.ForeignKey(SourceRecordReference, on_delete=models.PROTECT)
    entity_kind = models.CharField(max_length=30, choices=TARGET_CHOICES)
    canonical_entity_id = models.UUIDField()
    field_or_claim = models.CharField(max_length=100, blank=True)
    relation = models.CharField(max_length=10, choices=Relation)

    class Meta:
        indexes = [models.Index(fields=["entity_kind", "canonical_entity_id"])]

    def clean(self):
        validate_target(self.entity_kind, self.canonical_entity_id)


class DataQualityIssue(UUIDRecord):
    class Severity(models.TextChoices):
        INFO = "INFO"
        WARNING = "WARNING"
        ERROR = "ERROR"
        BLOCKING = "BLOCKING"

    class Status(models.TextChoices):
        OPEN = "OPEN"
        RESOLVED = "RESOLVED"

    provider = models.ForeignKey(
        Provider, on_delete=models.PROTECT, null=True, blank=True
    )
    code = models.CharField(
        max_length=80, validators=[RegexValidator(r"^[A-Z][A-Z0-9_]*$")]
    )
    severity = models.CharField(max_length=8, choices=Severity)
    status = models.CharField(max_length=8, choices=Status, default=Status.OPEN)
    target_kind = models.CharField(max_length=80, blank=True)
    target_key = models.CharField(max_length=200, blank=True)
    domain = models.CharField(max_length=40, blank=True)
    fingerprint = models.CharField(max_length=64, unique=True, null=True, blank=True)
    opened_at_utc = models.DateTimeField(default=timezone.now)
    last_seen_at_utc = models.DateTimeField(default=timezone.now)
    resolved_at_utc = models.DateTimeField(null=True, blank=True)
    blocks_publication = models.BooleanField(default=False)
    safe_detail = models.TextField(blank=True)
    source_record = models.ForeignKey(
        SourceRecordReference, on_delete=models.PROTECT, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(severity="BLOCKING") | Q(blocks_publication=True),
                name="blocking_issue_blocks_publication",
            )
        ]

    def clean(self):
        require_utc(self, "opened_at_utc", "last_seen_at_utc", "resolved_at_utc")


class QuarantineRecord(UUIDRecord):
    class Resolution(models.TextChoices):
        OPEN = "OPEN"
        RESOLVED = "RESOLVED"

    provider = models.ForeignKey(Provider, on_delete=models.PROTECT)
    source_record = models.ForeignKey(SourceRecordReference, on_delete=models.PROTECT)
    reason_code = models.CharField(
        max_length=80, validators=[RegexValidator(r"^[A-Z][A-Z0-9_]*$")]
    )
    candidate_kind = models.CharField(max_length=80, blank=True)
    candidate_key = models.CharField(max_length=200, blank=True)
    created_at_utc = models.DateTimeField(default=timezone.now)
    last_seen_at_utc = models.DateTimeField(default=timezone.now)
    resolution_state = models.CharField(
        max_length=8, choices=Resolution, default=Resolution.OPEN
    )
    resolved_at_utc = models.DateTimeField(null=True, blank=True)

    def clean(self):
        require_utc(self, "created_at_utc", "last_seen_at_utc", "resolved_at_utc")
        if self.source_record_id and self.provider_id != self.source_record.provider_id:
            raise ValidationError({"provider": "Provider must match source record."})


class DatasetRevision(models.Model):
    """Monotonic publication token, not a historical readable snapshot."""

    id = models.BigAutoField(primary_key=True)
    committed_at_utc = models.DateTimeField(default=timezone.now)
    sync_run = models.ForeignKey(
        DataSyncRun, on_delete=models.PROTECT, null=True, blank=True
    )
    sync_item = models.ForeignKey(
        DataSyncItem, on_delete=models.PROTECT, null=True, blank=True
    )
    changed_game_ids = models.JSONField(default=list, blank=True)
    invalidation_scopes = models.JSONField(default=list, blank=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Published revisions are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Published revisions cannot be deleted.")

    def clean(self):
        require_utc(self, "committed_at_utc")
        if self.sync_item_id and self.sync_run_id != self.sync_item.run_id:
            raise ValidationError({"sync_item": "Item must belong to revision run."})


class CoverageAssessmentHistory(AppendOnlyRecord):
    game = models.ForeignKey(Game, on_delete=models.PROTECT)
    domain = models.CharField(max_length=17, choices=GameDataCoverage.Domain)
    state = models.CharField(max_length=11, choices=GameDataCoverage.State)
    reason_code = models.CharField(
        max_length=40, choices=CoverageReason, null=True, blank=True
    )
    assessed_at_utc = models.DateTimeField()
    source_record = models.ForeignKey(
        SourceRecordReference, on_delete=models.PROTECT, null=True, blank=True
    )
    sync_item = models.ForeignKey(
        DataSyncItem, on_delete=models.PROTECT, null=True, blank=True
    )
    revision = models.ForeignKey(
        DatasetRevision, on_delete=models.PROTECT, null=True, blank=True
    )

    class Meta:
        indexes = [models.Index(fields=["game", "domain", "assessed_at_utc"])]

    def clean(self):
        require_utc(self, "assessed_at_utc")


class TargetLease(UUIDRecord):
    """Persistence only; B22 implements acquisition and stale-owner rules."""

    provider = models.ForeignKey(Provider, on_delete=models.PROTECT)
    resource_kind = models.CharField(max_length=80)
    external_target = models.CharField(max_length=200)
    owner_run = models.ForeignKey(DataSyncRun, on_delete=models.PROTECT)
    expires_at_utc = models.DateTimeField()
    renewed_at_utc = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "resource_kind", "external_target"],
                name="unique_target_lease",
            )
        ]

    def clean(self):
        require_utc(self, "expires_at_utc", "renewed_at_utc")


class AnalyticsInvalidationIntent(UUIDRecord):
    """Durable publication intent; B25 implements processing."""

    class Status(models.TextChoices):
        PENDING = "PENDING"
        PROCESSED = "PROCESSED"

    revision = models.OneToOneField(DatasetRevision, on_delete=models.PROTECT)
    scopes = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=9, choices=Status, default=Status.PENDING)
    created_at_utc = models.DateTimeField(default=timezone.now)
    processed_at_utc = models.DateTimeField(null=True, blank=True)

    def clean(self):
        require_utc(self, "created_at_utc", "processed_at_utc")
