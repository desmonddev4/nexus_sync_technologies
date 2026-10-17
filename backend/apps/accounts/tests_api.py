from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounts.models import AccountProfile


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