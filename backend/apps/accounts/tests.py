from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from django.test import TestCase

from apps.accounts.models import AccountProfile


class AccountProfileTests(TestCase):
    def test_profile_records_an_explicit_role(self):
        user = get_user_model().objects.create_user(
            username="coordinator",
            password="test-password",
        )
        profile = AccountProfile.objects.create(
            user=user,
            role=AccountProfile.Role.EMERGENCY_COORDINATOR,
        )

        self.assertEqual(profile.user, user)
        self.assertEqual(profile.role, AccountProfile.Role.EMERGENCY_COORDINATOR)


class TokenAuthenticationTests(APITestCase):
    def test_valid_credentials_return_a_token(self):
        get_user_model().objects.create_user(
            username="mobile-user",
            password="test-password",
        )

        response = self.client.post(
            "/api/v1/auth/token/",
            {"username": "mobile-user", "password": "test-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["token"])

    def test_invalid_credentials_are_rejected(self):
        response = self.client.post(
            "/api/v1/auth/token/",
            {"username": "unknown", "password": "incorrect"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)