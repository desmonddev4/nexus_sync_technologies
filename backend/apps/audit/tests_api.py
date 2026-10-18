from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from io import StringIO
from rest_framework.test import APITestCase
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import AccountProfile

from .models import AuditLog


class AuditLogApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.coordinator = user_model.objects.create_user(username="audit-coordinator")
        AccountProfile.objects.create(
            user=self.coordinator,
            role=AccountProfile.Role.EMERGENCY_COORDINATOR,
        )
        self.clinician = user_model.objects.create_user(username="audit-clinician")
        AccountProfile.objects.create(
            user=self.clinician,
            role=AccountProfile.Role.CLINICIAN,
        )
        self.patient_user = user_model.objects.create_user(username="audit-patient")
        AccountProfile.objects.create(
            user=self.patient_user,
            role=AccountProfile.Role.PATIENT,
        )
        AuditLog.objects.create(
            actor=self.coordinator,
            action="incident.read",
            resource_type="incident",
            resource_id="abc-1",
            outcome=AuditLog.Outcome.SUCCESS,
            metadata={"note": "visible"},
        )
        AuditLog.objects.create(
            actor=self.clinician,
            action="patient.access_denied",
            resource_type="patient",
            resource_id="pat-1",
            outcome=AuditLog.Outcome.DENIED,
            metadata={"note": "denied"},
        )

    def test_operations_staff_can_list_audit_logs(self):
        self.client.force_authenticate(self.coordinator)

        response = self.client.get("/api/v1/audit/logs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_non_operations_role_cannot_list_audit_logs(self):
        self.client.force_authenticate(self.patient_user)

        response = self.client.get("/api/v1/audit/logs/")

        self.assertEqual(response.status_code, 403)

    def test_audit_logs_support_filtering(self):
        self.client.force_authenticate(self.coordinator)

        response = self.client.get(
            "/api/v1/audit/logs/?outcome=denied&action=access_denied&resource=patient"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["resource_type"], "patient")
        self.assertEqual(payload[0]["outcome"], "denied")

    def test_audit_logs_support_actor_username_filter(self):
        self.client.force_authenticate(self.coordinator)

        response = self.client.get("/api/v1/audit/logs/?actor=audit-clinician")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["actor_username"], "audit-clinician")

    @override_settings(AUDIT_EXPORT_MAX_ROWS=10)
    def test_coordinator_can_export_audit_logs_csv(self):
        self.client.force_authenticate(self.coordinator)

        response = self.client.get("/api/v1/audit/logs/export/?outcome=denied")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        content = response.content.decode("utf-8")
        self.assertIn("actor_username", content)
        self.assertIn("patient.access_denied", content)

    def test_clinician_cannot_export_audit_logs(self):
        self.client.force_authenticate(self.clinician)

        response = self.client.get("/api/v1/audit/logs/export/")

        self.assertEqual(response.status_code, 403)


class AuditRetentionCommandTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        actor = user_model.objects.create_user(username="audit-retention-actor")
        old_entry = AuditLog.objects.create(
            actor=actor,
            action="old.entry",
            resource_type="audit_log",
            outcome=AuditLog.Outcome.SUCCESS,
        )
        recent_entry = AuditLog.objects.create(
            actor=actor,
            action="recent.entry",
            resource_type="audit_log",
            outcome=AuditLog.Outcome.SUCCESS,
        )
        old_entry.created_at = timezone.now() - timedelta(days=500)
        old_entry.save(update_fields=("created_at", "updated_at"))
        self.old_entry_id = old_entry.pk
        self.recent_entry_id = recent_entry.pk

    @override_settings(AUDIT_RETENTION_DAYS=365)
    def test_prune_audit_logs_dry_run_does_not_delete_rows(self):
        output = StringIO()

        call_command("prune_audit_logs", "--dry-run", stdout=output)

        self.assertIn("would be deleted", output.getvalue())
        self.assertTrue(AuditLog.objects.filter(pk=self.old_entry_id).exists())
        self.assertTrue(AuditLog.objects.filter(pk=self.recent_entry_id).exists())

    @override_settings(AUDIT_RETENTION_DAYS=365)
    def test_prune_audit_logs_deletes_only_out_of_retention_rows(self):
        output = StringIO()

        call_command("prune_audit_logs", stdout=output)

        self.assertIn("Deleted", output.getvalue())
        self.assertFalse(AuditLog.objects.filter(pk=self.old_entry_id).exists())
        self.assertTrue(AuditLog.objects.filter(pk=self.recent_entry_id).exists())

    def test_prune_audit_logs_rejects_invalid_days(self):
        with self.assertRaises(CommandError):
            call_command("prune_audit_logs", "--days", "0")
