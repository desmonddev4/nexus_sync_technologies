from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounts.models import AccountProfile
from apps.audit.models import AuditLog
from apps.patients.models import Patient


class CurrentUserApiTests(APITestCase):
    def test_current_user_requires_authentication(self):
        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 401)

    def test_current_user_reports_operations_access_without_sensitive_profile_data(self):
        user = get_user_model().objects.create_user(username="operator")
        AccountProfile.objects.create(
            user=user,
            role=AccountProfile.Role.EMERGENCY_COORDINATOR,
            phone_number="+233200000000",
        )
        self.client.force_authenticate(user)

        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "username": "operator",
                "role": AccountProfile.Role.EMERGENCY_COORDINATOR,
                "can_access_operations": True,
            },
        )

    def test_patient_role_is_not_granted_operations_access(self):
        user = get_user_model().objects.create_user(username="patient")
        AccountProfile.objects.create(user=user, role=AccountProfile.Role.PATIENT)
        self.client.force_authenticate(user)

        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["can_access_operations"])


class TokenAuthAuditTests(APITestCase):
    def test_token_issue_records_audit(self):
        user = get_user_model().objects.create_user(username="token-user", password="safe-password-123")
        AccountProfile.objects.create(user=user, role=AccountProfile.Role.CLINICIAN)

        response = self.client.post(
            "/api/v1/auth/token/",
            {"username": "token-user", "password": "safe-password-123"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())
        audit = AuditLog.objects.get(action="auth.token.issued")
        self.assertEqual(audit.actor, user)
        self.assertEqual(audit.resource_id, str(user.pk))
        self.assertEqual(audit.metadata.get("username"), "token-user")
        self.assertEqual(audit.metadata.get("role"), AccountProfile.Role.CLINICIAN)

    def test_token_failure_records_audit(self):
        user = get_user_model().objects.create_user(username="token-fail", password="safe-password-123")
        AccountProfile.objects.create(user=user, role=AccountProfile.Role.CLINICIAN)

        response = self.client.post(
            "/api/v1/auth/token/",
            {"username": "token-fail", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        audit = AuditLog.objects.get(action="auth.token.failed")
        self.assertEqual(audit.outcome, AuditLog.Outcome.FAILURE)
        self.assertIsNone(audit.actor)
        self.assertEqual(audit.metadata.get("username"), "token-fail")


class AccountManagementApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.coordinator = user_model.objects.create_user(username="ops-admin")
        AccountProfile.objects.create(
            user=self.coordinator,
            role=AccountProfile.Role.EMERGENCY_COORDINATOR,
        )
        self.clinician = user_model.objects.create_user(username="ops-clinician")
        AccountProfile.objects.create(
            user=self.clinician,
            role=AccountProfile.Role.CLINICIAN,
        )
        self.patient_user = user_model.objects.create_user(username="ops-patient")
        AccountProfile.objects.create(
            user=self.patient_user,
            role=AccountProfile.Role.PATIENT,
        )

    def test_coordinator_can_list_accounts(self):
        self.client.force_authenticate(self.coordinator)

        response = self.client.get("/api/v1/accounts/")

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()), 3)

    def test_non_manager_cannot_list_accounts(self):
        self.client.force_authenticate(self.clinician)

        response = self.client.get("/api/v1/accounts/")

        self.assertEqual(response.status_code, 403)
        denied_audit = AuditLog.objects.get(action="account.manage.denied")
        self.assertEqual(denied_audit.actor, self.clinician)
        self.assertEqual(denied_audit.outcome, AuditLog.Outcome.DENIED)
        self.assertEqual(denied_audit.metadata.get("role"), AccountProfile.Role.CLINICIAN)

    def test_coordinator_can_create_account(self):
        self.client.force_authenticate(self.coordinator)

        response = self.client.post(
            "/api/v1/accounts/",
            {
                "username": "new-operator",
                "email": "new-operator@nexus.test",
                "password": "safe-password-123",
                "is_active": True,
                "role": AccountProfile.Role.CLINICIAN,
                "phone_number": "+233200000099",
                "patient": None,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        created = get_user_model().objects.get(username="new-operator")
        self.assertEqual(created.profile.role, AccountProfile.Role.CLINICIAN)
        audit = AuditLog.objects.get(action="account.created", resource_id=str(created.pk))
        self.assertEqual(audit.actor, self.coordinator)
        self.assertEqual(audit.metadata.get("role"), AccountProfile.Role.CLINICIAN)

    def test_patient_role_requires_patient_link(self):
        self.client.force_authenticate(self.coordinator)

        response = self.client.post(
            "/api/v1/accounts/",
            {
                "username": "bad-patient",
                "password": "safe-password-123",
                "is_active": True,
                "role": AccountProfile.Role.PATIENT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("patient", response.json())

    def test_account_creation_requires_explicit_role(self):
        self.client.force_authenticate(self.coordinator)

        response = self.client.post(
            "/api/v1/accounts/",
            {
                "username": "role-required",
                "password": "safe-password-123",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.json())
        self.assertFalse(get_user_model().objects.filter(username="role-required").exists())

    def test_profileless_account_update_requires_role_and_does_not_grant_coordinator(self):
        legacy_user = get_user_model().objects.create_user(username="legacy-no-profile")
        self.client.force_authenticate(self.coordinator)

        response = self.client.patch(
            f"/api/v1/accounts/{legacy_user.pk}/",
            {"email": "legacy@nexus.test"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.json())
        self.assertFalse(AccountProfile.objects.filter(user=legacy_user).exists())

    def test_partial_patient_link_update_preserves_existing_role_and_patient(self):
        first_patient = Patient.objects.create(full_name="First Linked Patient")
        second_patient = Patient.objects.create(full_name="Second Linked Patient")
        self.patient_user.profile.patient = first_patient
        self.patient_user.profile.save(update_fields=("patient", "updated_at"))
        self.client.force_authenticate(self.coordinator)

        response = self.client.patch(
            f"/api/v1/accounts/{self.patient_user.pk}/",
            {"patient": str(second_patient.pk)},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.patient_user.profile.refresh_from_db()
        self.assertEqual(self.patient_user.profile.role, AccountProfile.Role.PATIENT)
        self.assertEqual(self.patient_user.profile.patient_id, second_patient.pk)

    def test_coordinator_can_update_role_and_patient_link(self):
        patient = Patient.objects.create(full_name="Linked Patient")
        self.client.force_authenticate(self.coordinator)

        response = self.client.patch(
            f"/api/v1/accounts/{self.patient_user.pk}/",
            {
                "role": AccountProfile.Role.PATIENT,
                "patient": str(patient.pk),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.patient_user.refresh_from_db()
        self.assertEqual(self.patient_user.profile.patient_id, patient.pk)
        audit = AuditLog.objects.get(action="account.updated", resource_id=str(self.patient_user.pk))
        self.assertEqual(audit.actor, self.coordinator)
        self.assertEqual(audit.metadata.get("previous_role"), AccountProfile.Role.PATIENT)
        self.assertEqual(audit.metadata.get("new_role"), AccountProfile.Role.PATIENT)