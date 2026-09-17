"""Offline persistence and audit-safety checks for B05."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase

from domain.models import Game, GameDataCoverage, Player, Season, Team
from ingestion.models import (
    CANONICAL_TARGETS,
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
    provider_allows_automation,
)


class ProvenanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.now = datetime(2025, 4, 12, 20, tzinfo=timezone.utc)
        cls.provider = Provider.objects.create(
            code="MLB", display_name="MLB", enabled=True
        )
        cls.other_provider = Provider.objects.create(code="OTHER", display_name="Other")
        cls.season = Season.objects.create(year=2025)
        cls.home = Team.objects.create(display_name="Home")
        cls.away = Team.objects.create(display_name="Away")
        cls.player = Player.objects.create(display_name="Batter")
        cls.game = Game.objects.create(
            season=cls.season, home_team=cls.home, away_team=cls.away
        )
        cls.snapshot = RawSourceSnapshot.objects.create(
            provider=cls.provider,
            resource_kind="game_feed",
            external_target="game:42",
            request_fingerprint="b" * 64,
            retrieved_at_utc=cls.now,
            http_status=200,
            content_type="application/json",
            checksum_sha256="a" * 64,
            storage_key=f"raw/mlb/aa/{'a' * 64}.json.gz",
            provider_reported_at_utc=cls.now - timedelta(minutes=2),
        )
        cls.source = SourceRecordReference.objects.create(
            provider=cls.provider,
            snapshot=cls.snapshot,
            resource_kind="play",
            source_record_key="atBatIndex:1",
            retrieved_at_utc=cls.now,
        )

    def test_provider_key_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Provider.objects.create(code="MLB", display_name="Duplicate")

    def test_access_denied_without_current_explicit_approval(self):
        self.assertFalse(
            provider_allows_automation(self.provider, "schedule", self.now)
        )
        unknown = ProviderAccessDecision.objects.create(
            provider=self.provider,
            recorded_at_utc=self.now - timedelta(hours=2),
        )
        self.assertEqual(unknown.state, "UNKNOWN")
        self.assertFalse(
            provider_allows_automation(self.provider, "schedule", self.now)
        )
        with self.assertRaises(ValidationError):
            ProviderAccessDecision.objects.create(
                provider=self.provider,
                state=ProviderAccessDecision.State.APPROVED_FOR_AUTOMATED_USE,
                recorded_at_utc=self.now - timedelta(hours=1),
            )
        ProviderAccessDecision.objects.create(
            provider=self.provider,
            state=ProviderAccessDecision.State.APPROVED_FOR_AUTOMATED_USE,
            decision_reference="external-approval-1",
            allowed_operation="schedule",
            recorded_at_utc=self.now - timedelta(hours=1),
        )
        self.assertTrue(provider_allows_automation(self.provider, "schedule", self.now))
        self.assertFalse(
            provider_allows_automation(self.provider, "game_feed", self.now)
        )
        ProviderAccessDecision.objects.create(
            provider=self.provider,
            state=ProviderAccessDecision.State.APPROVED_FOR_AUTOMATED_USE,
            decision_reference="external-approval-expired",
            allowed_operation="game_feed",
            recorded_at_utc=self.now - timedelta(hours=1),
            expires_at_utc=self.now - timedelta(minutes=1),
        )
        self.assertFalse(
            provider_allows_automation(self.provider, "game_feed", self.now)
        )
        ProviderAccessDecision.objects.create(
            provider=self.provider,
            state=ProviderAccessDecision.State.BLOCKED,
            recorded_at_utc=self.now,
        )
        self.assertFalse(
            provider_allows_automation(self.provider, "schedule", self.now)
        )

    def test_typed_alias_namespace_history_and_invalid_targets(self):
        first = ExternalIdentifier.objects.create(
            provider=self.provider,
            entity_kind="PLAYER",
            external_value="42",
            canonical_entity_id=self.player.id,
        )
        ExternalIdentifier.objects.create(
            provider=self.provider,
            entity_kind="GAME",
            external_value="42",
            canonical_entity_id=self.game.id,
        )
        ExternalIdentifier.objects.create(
            provider=self.other_provider,
            entity_kind="PLAYER",
            external_value="42",
            canonical_entity_id=self.player.id,
        )
        with self.assertRaises(ValidationError):
            ExternalIdentifier.objects.create(
                provider=self.provider,
                entity_kind="PLAYER",
                external_value="42",
                canonical_entity_id=self.player.id,
            )
        first.resolution_state = ExternalIdentifier.Resolution.SUPERSEDED
        first.save()
        first.canonical_entity_id = self.game.id
        with self.assertRaises(ValidationError):
            first.save()
        first.canonical_entity_id = self.player.id
        ExternalIdentifier.objects.create(
            provider=self.provider,
            entity_kind="PLAYER",
            external_value="42",
            canonical_entity_id=self.player.id,
        )
        self.assertEqual(
            ExternalIdentifier.objects.filter(
                provider=self.provider, entity_kind="PLAYER", external_value="42"
            ).count(),
            2,
        )
        with self.assertRaises(ValidationError), transaction.atomic():
            Player.objects.filter(pk=self.player.pk).delete()
        for kind, target in [
            ("AUTH_USER", self.player.id),
            ("PLAYER", uuid4()),
            ("GAME", self.player.id),
        ]:
            with self.assertRaises(ValidationError):
                ExternalIdentifier.objects.create(
                    provider=self.provider,
                    entity_kind=kind,
                    external_value=str(uuid4()),
                    canonical_entity_id=target,
                )

    def test_source_links_allow_multiple_claims_and_reject_bad_targets(self):
        second = SourceRecordReference.objects.create(
            provider=self.provider,
            snapshot=self.snapshot,
            resource_kind="play",
            source_record_key="atBatIndex:2",
            retrieved_at_utc=self.now,
        )
        for source, relation in [
            (self.source, FactSourceLink.Relation.SUPPORTS),
            (second, FactSourceLink.Relation.CONFLICTS),
        ]:
            FactSourceLink.objects.create(
                source_record=source,
                entity_kind="GAME",
                canonical_entity_id=self.game.id,
                relation=relation,
            )
        self.assertEqual(
            FactSourceLink.objects.filter(canonical_entity_id=self.game.id).count(), 2
        )
        with self.assertRaises(ValidationError):
            FactSourceLink.objects.create(
                source_record=self.source,
                entity_kind="PROVIDER",
                canonical_entity_id=self.provider.id,
                relation=FactSourceLink.Relation.SUPPORTS,
            )
        with self.assertRaises(ValidationError):
            FactSourceLink.objects.create(
                source_record=self.source,
                entity_kind="GAME",
                canonical_entity_id=uuid4(),
                relation=FactSourceLink.Relation.SUPPORTS,
            )
        with self.assertRaises(ValidationError):
            SourceRecordReference.objects.create(
                provider=self.provider,
                snapshot=self.snapshot,
                resource_kind="play",
                source_record_key="atBatIndex:1",
                retrieved_at_utc=self.now,
            )

    def test_snapshot_is_metadata_only_and_retrieval_time_is_distinct(self):
        self.assertNotEqual(
            self.snapshot.retrieved_at_utc, self.snapshot.provider_reported_at_utc
        )
        self.assertFalse(
            any(field.name == "payload" for field in RawSourceSnapshot._meta.fields)
        )
        self.assertEqual(self.snapshot.checksum_sha256, "a" * 64)
        self.snapshot.parse_status = RawSourceSnapshot.ParseStatus.PARSED
        self.snapshot.save()
        self.snapshot.storage_key = "/private/raw.json"
        with self.assertRaises(ValidationError):
            self.snapshot.save()
        with self.assertRaises(ValidationError):
            self.snapshot.delete()
        with self.assertRaises(ValidationError):
            RawSourceSnapshot.objects.create(
                provider=self.provider,
                resource_kind="game_feed",
                external_target="game:43",
                request_fingerprint="b" * 64,
                retrieved_at_utc=self.now,
                checksum_sha256="a" * 64,
                storage_key="../private/raw.json",
            )
        with self.assertRaises(ValidationError):
            RawSourceSnapshot.objects.create(
                provider=self.provider,
                resource_kind="game_feed",
                external_target="https://host/game?token=secret",
                request_fingerprint="b" * 64,
                retrieved_at_utc=self.now,
                checksum_sha256="a" * 64,
                storage_key=f"raw/mlb/aa/{'a' * 64}.json.gz",
            )

    def test_sync_run_item_and_revision_are_auditable(self):
        run = DataSyncRun.objects.create(
            provider=self.provider,
            job_type="fixture_parse",
            parameter_fingerprint="c" * 64,
            scope_key="game:42",
            started_at_utc=self.now,
        )
        item = DataSyncItem.objects.create(
            run=run, target_kind="GAME", target_key="42", snapshot=self.snapshot
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            DataSyncItem.objects.create(run=run, target_kind="GAME", target_key="42")
        revisions = [
            DatasetRevision.objects.create(
                sync_run=run,
                sync_item=item,
                committed_at_utc=self.now + timedelta(minutes=offset),
                changed_game_ids=[str(self.game.id)],
            )
            for offset in (1, 2)
        ]
        self.assertLess(revisions[0].id, revisions[1].id)
        self.assertFalse(hasattr(revisions[0], "historical_snapshot"))
        revisions[0].changed_game_ids = []
        with self.assertRaises(ValidationError):
            revisions[0].save()

    def test_issue_quarantine_and_coverage_history_are_distinct(self):
        issue = DataQualityIssue.objects.create(
            provider=self.provider,
            code="HR_WITHOUT_PA",
            severity=DataQualityIssue.Severity.BLOCKING,
            blocks_publication=True,
            source_record=self.source,
            opened_at_utc=self.now,
            last_seen_at_utc=self.now,
        )
        quarantine = QuarantineRecord.objects.create(
            provider=self.provider,
            source_record=self.source,
            reason_code="HR_WITHOUT_PA",
            candidate_kind="HOME_RUN_EVENT",
            candidate_key="game:42:play:1",
            created_at_utc=self.now,
            last_seen_at_utc=self.now,
        )
        self.assertTrue(issue.blocks_publication)
        self.assertEqual(issue.status, "OPEN")
        self.assertEqual(quarantine.resolution_state, "OPEN")
        with self.assertRaises(IntegrityError), transaction.atomic():
            DataQualityIssue.objects.create(
                code="UNMATCHED_PA",
                severity=DataQualityIssue.Severity.BLOCKING,
                blocks_publication=False,
            )
        for state in (GameDataCoverage.State.UNKNOWN, GameDataCoverage.State.PARTIAL):
            CoverageAssessmentHistory.objects.create(
                game=self.game,
                domain=GameDataCoverage.Domain.HR_EVENTS,
                state=state,
                reason_code="HR_WITHOUT_PA",
                assessed_at_utc=self.now,
                source_record=self.source,
            )
        self.assertEqual(
            CoverageAssessmentHistory.objects.filter(game=self.game).count(), 2
        )
        self.assertFalse(GameDataCoverage.objects.filter(game=self.game).exists())
        current = GameDataCoverage.objects.create(
            game=self.game,
            domain=GameDataCoverage.Domain.HR_EVENTS,
            state=GameDataCoverage.State.PARTIAL,
            assessed_at_utc=self.now,
        )
        self.assertEqual(current.state, "PARTIAL")

    def test_admin_is_inspection_only_and_hides_snapshot_storage_key(self):
        user = get_user_model().objects.create_superuser(
            username="audit", email="audit@example.test", password="test-password"
        )
        request = RequestFactory().get("/admin/")
        request.user = user
        for model in (
            *CANONICAL_TARGETS.values(),
            Provider,
            ProviderAccessDecision,
            ExternalIdentifier,
            RawSourceSnapshot,
            FactSourceLink,
            CoverageAssessmentHistory,
            DatasetRevision,
        ):
            model_admin = admin.site._registry[model]
            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_change_permission(request))
            self.assertFalse(model_admin.has_delete_permission(request))
            self.assertFalse(model_admin.get_actions(request))
        snapshot_admin = admin.site._registry[RawSourceSnapshot]
        self.assertIn("storage_key", snapshot_admin.exclude)
