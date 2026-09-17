from django.apps import AppConfig
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete


def protect_typed_evidence(sender, instance, **kwargs):
    from .models import CANONICAL_TARGETS, ExternalIdentifier, FactSourceLink

    kind = next(
        (key for key, model in CANONICAL_TARGETS.items() if model is sender), None
    )
    if kind and (
        ExternalIdentifier.objects.filter(
            entity_kind=kind, canonical_entity_id=instance.pk
        ).exists()
        or FactSourceLink.objects.filter(
            entity_kind=kind, canonical_entity_id=instance.pk
        ).exists()
    ):
        raise ValidationError("Canonical target has retained provenance references.")


class IngestionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ingestion"

    def ready(self):
        from .models import CANONICAL_TARGETS

        for model in CANONICAL_TARGETS.values():
            pre_delete.connect(
                protect_typed_evidence,
                sender=model,
                dispatch_uid=f"protect_typed_evidence_{model._meta.label_lower}",
            )
