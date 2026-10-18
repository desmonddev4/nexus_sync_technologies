import hashlib
import hmac
import json
from datetime import datetime, timezone as datetime_timezone
from uuid import UUID

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.notifications.models import IncidentNotification
from apps.notifications.services import apply_sasusync_status


class SasuSyncWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        secret = settings.SASUSYNC_WEBHOOK_SECRET
        signature = request.headers.get("X-Webhook-Signature", "")
        if not secret or not signature:
            return HttpResponse(status=403)

        expected = hmac.new(
            secret.encode("utf-8"),
            request.body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return HttpResponse(status=403)

        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return HttpResponse(status=400)
        if not isinstance(payload, dict):
            return HttpResponse(status=400)

        data = payload.get("data")
        if not isinstance(data, dict) or not data.get("message_id"):
            return HttpResponse(status=200)

        metadata = data.get("metadata") or payload.get("metadata") or {}
        notification_id = metadata.get("notification_id") if isinstance(metadata, dict) else None
        try:
            notification_id = UUID(str(notification_id))
            event_at = datetime.fromisoformat(
                str(payload["timestamp"]).replace("Z", "+00:00")
            )
        except (KeyError, TypeError, ValueError):
            return HttpResponse(status=400)
        if timezone.is_naive(event_at):
            event_at = event_at.replace(tzinfo=datetime_timezone.utc)

        try:
            apply_sasusync_status(
                notification_id=notification_id,
                message_id=str(data["message_id"]),
                recipient=str(data.get("recipient", "")),
                provider_status=str(payload.get("event", data.get("status", ""))),
                event_at=event_at,
            )
        except IncidentNotification.DoesNotExist:
            return HttpResponse(status=200)
        except ValueError:
            return HttpResponse(status=409)
        return HttpResponse(status=200)