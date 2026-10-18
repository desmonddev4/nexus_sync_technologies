from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounts.models import AccountProfile

from .models import EscalationPolicy


class EscalationPolicyApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.coordinator = user_model.objects.create_user(username="settings-coordinator")
        AccountProfile.objects.create(
            user=self.coordinator,
            role=AccountProfile.Role.EMERGENCY_COORDINATOR,
        )
        self.clinician = user_model.objects.create_user(username="settings-clinician")
        AccountProfile.objects.create(
            user=self.clinician,
            role=AccountProfile.Role.CLINICIAN,
        )
        self.patient = user_model.objects.create_user(username="settings-patient")
        AccountProfile.objects.create(
            user=self.patient,
            role=AccountProfile.Role.PATIENT,
        )

    def test_operations_staff_can_read_escalation_policy(self):
        self.client.force_authenticate(self.clinician)

        response = self.client.get("/api/v1/settings/escalation-policy/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("initial_notification_timeout_minutes", response.json())

    def test_non_operations_role_cannot_read_escalation_policy(self):
        self.client.force_authenticate(self.patient)

        response = self.client.get("/api/v1/settings/escalation-policy/")

        self.assertEqual(response.status_code, 403)

    def test_only_coordinator_can_update_escalation_policy(self):
        self.client.force_authenticate(self.clinician)

        denied = self.client.patch(
            "/api/v1/settings/escalation-policy/",
            {"max_retry_attempts": 5},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.coordinator)
        allowed = self.client.patch(
            "/api/v1/settings/escalation-policy/",
            {
                "initial_notification_timeout_minutes": 7,
                "retry_interval_minutes": 3,
                "max_retry_attempts": 4,
                "escalate_to_coordinator_after_minutes": 12,
                "require_operator_acknowledgement": True,
            },
            format="json",
        )

        self.assertEqual(allowed.status_code, 200)
        policy = EscalationPolicy.objects.get(singleton_key="default")
        self.assertEqual(policy.max_retry_attempts, 4)
        self.assertEqual(policy.updated_by, self.coordinator)

    def test_escalation_policy_validation_rejects_invalid_time_relationships(self):
        self.client.force_authenticate(self.coordinator)

        response = self.client.patch(
            "/api/v1/settings/escalation-policy/",
            {
                "initial_notification_timeout_minutes": 5,
                "retry_interval_minutes": 7,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("retry_interval_minutes", response.json())
