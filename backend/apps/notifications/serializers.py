from rest_framework import serializers

from .models import IncidentNotification


class IncidentNotificationStatusSerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(
        source="emergency_contact.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = IncidentNotification
        fields = (
            "id",
            "contact_name",
            "channel",
            "status",
            "retry_count",
            "last_attempt_at",
            "submitted_at",
            "delivered_at",
            "acknowledged_at",
            "provider_name",
            "provider_task_id",
            "provider_status_updated_at",
            "failure_code",
            "created_at",
        )
        read_only_fields = fields