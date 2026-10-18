import time
from dataclasses import dataclass

import requests
from django.conf import settings


@dataclass(frozen=True)
class SubmissionResult:
    provider_name: str
    task_id: str


class ProviderConfigurationError(Exception):
    pass


class ProviderRejectedError(Exception):
    def __init__(self, failure_code):
        self.failure_code = str(failure_code)[:80]


class ProviderSubmissionUnknownError(Exception):
    pass


class ProviderLookupError(Exception):
    pass


class SasuSyncSmsProvider:
    provider_name = "sasusync"
    retry_statuses = {429, 500, 502, 503, 504}

    def __init__(self, *, sandbox=False, session=None, sleep=None, require_sender=True):
        self.api_key = settings.SASUSYNC_API_KEY
        self.sender_id = settings.SASUSYNC_SENDER_ID
        self.base_url = settings.SASUSYNC_BASE_URL.rstrip("/")
        self.sandbox = sandbox
        self.provider_name = "sasusync-sandbox" if sandbox else "sasusync"
        self.session = session or requests
        self.sleep = sleep or time.sleep

        if not self.api_key:
            raise ProviderConfigurationError("SASUSYNC_API_KEY is not configured.")
        if require_sender and (not self.sender_id or len(self.sender_id) > 11):
            raise ProviderConfigurationError(
                "Configure an approved SasuSync sender ID of at most 11 characters."
            )
        if not self.base_url.startswith("https://"):
            raise ProviderConfigurationError("SasuSync API requests require HTTPS.")

    def submit(self, notification, *, idempotency_key):
        path = "/smssandbox/v1/send" if self.sandbox else "/api/v1/send"
        message = (
            f"Nexus Sync: A possible emergency alert has been raised for "
            f"{notification.incident.patient.full_name}. Please check on them. "
            f"For urgent help, call 112. Ref {notification.incident_id}."
        )
        payload = {
            "sender": self.sender_id,
            "recipients": [notification.recipient_address_snapshot],
            "message": message,
            "metadata": {"notification_id": idempotency_key},
        }
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

        for attempt in range(4):
            try:
                response = self.session.post(
                    f"{self.base_url}{path}",
                    headers=headers,
                    json=payload,
                    timeout=30,
                )
            except requests.RequestException as error:
                raise ProviderSubmissionUnknownError from error
            except Exception as error:
                raise ProviderSubmissionUnknownError from error

            if response.status_code in self.retry_statuses:
                if attempt < 3:
                    self.sleep(2**attempt)
                    continue
                raise ProviderSubmissionUnknownError
            if response.status_code >= 400:
                raise ProviderRejectedError(response.status_code)

            try:
                result = response.json()
            except ValueError as error:
                raise ProviderSubmissionUnknownError from error
            if not isinstance(result, dict):
                raise ProviderSubmissionUnknownError
            task_id = result.get("data", {}).get("task_id")
            if result.get("success") is not True or not task_id:
                raise ProviderSubmissionUnknownError
            return SubmissionResult(provider_name=self.provider_name, task_id=str(task_id))

        raise ProviderSubmissionUnknownError

    def fetch_status(self, task_id):
        for attempt in range(4):
            try:
                response = self.session.get(
                    f"{self.base_url}/api/v1/status/{task_id}",
                    headers={"X-API-Key": self.api_key},
                    timeout=30,
                )
            except requests.RequestException as error:
                if attempt < 3:
                    self.sleep(2**attempt)
                    continue
                raise ProviderLookupError from error

            if response.status_code in self.retry_statuses:
                if attempt < 3:
                    self.sleep(2**attempt)
                    continue
                raise ProviderLookupError(f"Transient SasuSync status HTTP {response.status_code}.")
            if response.status_code >= 400:
                raise ProviderRejectedError(response.status_code)

            try:
                result = response.json()
            except ValueError as error:
                raise ProviderLookupError("SasuSync returned invalid status JSON.") from error
            if not isinstance(result, dict) or result.get("success") is not True:
                raise ProviderLookupError("SasuSync did not return a successful status response.")
            return result

        raise ProviderLookupError("SasuSync status lookup did not complete.")