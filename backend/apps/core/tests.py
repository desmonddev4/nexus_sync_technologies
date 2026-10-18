from rest_framework.test import APITestCase


class HealthEndpointTests(APITestCase):
    def test_health_endpoint_returns_json_without_authentication(self):
        response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"service": "nexus-sync-api", "status": "ok"},
        )
        self.assertEqual(response["Content-Type"], "application/json")