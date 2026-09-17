"""Conservative audit views; approval and fact mutations require later workflows."""

from django.contrib import admin

from .models import (
    AnalyticsInvalidationIntent,
    CoverageAssessmentHistory,
    DataQualityIssue,
    DatasetRevision,
    DataSyncItem,
    DataSyncRun,
    ExternalIdentifier,
    FactSourceLink,
    Provider,
    ProviderAccessDecision,
    QuarantineRecord,
    RawSourceSnapshot,
    SourceRecordReference,
    TargetLease,
)


class AuditInspectAdmin(admin.ModelAdmin):
    actions = None

    def get_readonly_fields(self, request, obj=None):
        hidden = set(self.get_exclude(request, obj) or ())
        return tuple(
            field.name for field in self.model._meta.fields if field.name not in hidden
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


ADMIN_VIEWS = (
    (
        Provider,
        ("code", "display_name", "enabled"),
        ("code", "display_name"),
        ("enabled",),
    ),
    (
        ProviderAccessDecision,
        ("provider", "state", "allowed_operation", "recorded_at_utc", "expires_at_utc"),
        ("provider__code", "decision_reference"),
        ("state",),
    ),
    (
        ExternalIdentifier,
        (
            "provider",
            "entity_kind",
            "external_value",
            "canonical_entity_id",
            "resolution_state",
        ),
        ("external_value", "canonical_entity_id"),
        ("entity_kind", "resolution_state"),
    ),
    (
        RawSourceSnapshot,
        (
            "id",
            "provider",
            "resource_kind",
            "retrieved_at_utc",
            "checksum_sha256",
            "parse_status",
        ),
        ("checksum_sha256",),
        ("parse_status",),
    ),
    (
        SourceRecordReference,
        ("id", "provider", "resource_kind", "source_record_key", "retrieved_at_utc"),
        ("source_record_key",),
        ("resource_kind",),
    ),
    (
        FactSourceLink,
        ("source_record", "entity_kind", "canonical_entity_id", "relation"),
        ("canonical_entity_id",),
        ("entity_kind", "relation"),
    ),
    (
        DataSyncRun,
        ("provider", "job_type", "status", "started_at_utc", "finished_at_utc"),
        ("provider__code", "job_type"),
        ("status",),
    ),
    (
        DataSyncItem,
        ("run", "target_kind", "target_key", "status", "checkpoint"),
        ("target_key",),
        ("status",),
    ),
    (
        DataQualityIssue,
        ("code", "severity", "status", "blocks_publication", "opened_at_utc"),
        ("code", "target_key"),
        ("severity", "status"),
    ),
    (
        QuarantineRecord,
        (
            "reason_code",
            "provider",
            "candidate_kind",
            "resolution_state",
            "created_at_utc",
        ),
        ("reason_code", "candidate_key"),
        ("resolution_state",),
    ),
    (
        CoverageAssessmentHistory,
        ("game", "domain", "state", "reason_code", "assessed_at_utc"),
        ("game__mlb_game_pk",),
        ("domain", "state"),
    ),
    (DatasetRevision, ("id", "committed_at_utc", "sync_run", "sync_item"), (), ()),
    (
        TargetLease,
        ("provider", "resource_kind", "external_target", "expires_at_utc"),
        ("external_target",),
        (),
    ),
    (
        AnalyticsInvalidationIntent,
        ("revision", "status", "created_at_utc", "processed_at_utc"),
        (),
        ("status",),
    ),
)

for model, display, search, filters in ADMIN_VIEWS:
    admin.site.register(
        model,
        type(
            f"{model.__name__}InspectAdmin",
            (AuditInspectAdmin,),
            {
                "list_display": display,
                "search_fields": search,
                "list_filter": filters,
                "exclude": ("storage_key",) if model is RawSourceSnapshot else (),
            },
        ),
    )
