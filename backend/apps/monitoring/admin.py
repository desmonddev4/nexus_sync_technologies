from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.accounts.models import AccountProfile

from .models import Measurement, MonitoringRule, MonitoringRuleEvaluation
from .services import evaluate_measurement_for_rules


@admin.register(MonitoringRule)
class MonitoringRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "measurement_type",
        "operator",
        "threshold",
        "priority",
        "version",
        "is_enabled",
        "reviewed_at",
    )
    list_filter = ("measurement_type", "priority", "is_enabled")
    search_fields = ("name", "description")
    readonly_fields = ("reviewed_by", "reviewed_at")

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.evaluations.exists():
            return tuple(field.name for field in obj._meta.fields)
        return super().get_readonly_fields(request, obj)

    def save_model(self, request, obj, form, change):
        if obj.is_enabled:
            try:
                role = request.user.profile.role
            except AccountProfile.DoesNotExist:
                role = None
            if not request.user.is_superuser and role != AccountProfile.Role.CLINICIAN:
                raise PermissionDenied("Only a clinician or superuser may approve and enable a rule.")
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = (
        "patient",
        "measurement_type",
        "value",
        "unit",
        "source",
        "quality",
        "measured_at",
        "quality_reviewed_by",
    )
    list_filter = ("measurement_type", "source", "quality")
    search_fields = ("patient__full_name", "event_id")
    readonly_fields = (
        "id",
        "patient",
        "device",
        "recorded_by",
        "event_id",
        "measurement_type",
        "value",
        "unit",
        "source",
        "measured_at",
        "received_at",
        "quality_reviewed_by",
        "quality_reviewed_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.quality_reviewed_by = request.user
        obj.quality_reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)
        if obj.quality == Measurement.Quality.ACCEPTABLE:
            evaluate_measurement_for_rules(obj)


@admin.register(MonitoringRuleEvaluation)
class MonitoringRuleEvaluationAdmin(admin.ModelAdmin):
    list_display = ("rule", "measurement", "status", "incident", "created_at")
    list_filter = ("status", "rule")
    readonly_fields = tuple(field.name for field in MonitoringRuleEvaluation._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False