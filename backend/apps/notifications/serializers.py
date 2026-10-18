from rest_framework import serializers

from .models import EscalationPolicy, IncidentNotification


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


class EscalationPolicySerializer(serializers.ModelSerializer):
    updated_by_username = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = EscalationPolicy
        fields = (
            "id",
            "initial_notification_timeout_minutes",
            "retry_interval_minutes",
            "max_retry_attempts",
            "escalate_to_coordinator_after_minutes",
            "require_operator_acknowledgement",
            "allow_simulation_escalation",
            "notes",
            "updated_by",
            "updated_by_username",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "updated_by", "updated_by_username", "created_at", "updated_at")

    def validate(self, attrs):
        initial_timeout = attrs.get("initial_notification_timeout_minutes", getattr(self.instance, "initial_notification_timeout_minutes", 5))
        retry_interval = attrs.get("retry_interval_minutes", getattr(self.instance, "retry_interval_minutes", 3))
        escalation_timeout = attrs.get("escalate_to_coordinator_after_minutes", getattr(self.instance, "escalate_to_coordinator_after_minutes", 10))
        if retry_interval > initial_timeout:
            raise serializers.ValidationError({"retry_interval_minutes": "Retry interval cannot exceed initial timeout."})
        if escalation_timeout < initial_timeout:
            raise serializers.ValidationError({"escalate_to_coordinator_after_minutes": "Escalation timeout must be greater than or equal to initial timeout."})
        return attrs

    def get_updated_by_username(self, obj):
        return obj.updated_by.get_username() if obj.updated_by else None