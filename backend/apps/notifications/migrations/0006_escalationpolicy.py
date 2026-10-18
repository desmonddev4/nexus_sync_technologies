from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0005_incidentnotification_provider_status_updated_at_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EscalationPolicy",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("singleton_key", models.CharField(default="default", max_length=32, unique=True)),
                ("initial_notification_timeout_minutes", models.PositiveSmallIntegerField(default=5)),
                ("retry_interval_minutes", models.PositiveSmallIntegerField(default=3)),
                ("max_retry_attempts", models.PositiveSmallIntegerField(default=3)),
                ("escalate_to_coordinator_after_minutes", models.PositiveSmallIntegerField(default=10)),
                ("require_operator_acknowledgement", models.BooleanField(default=True)),
                ("allow_simulation_escalation", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_escalation_policies",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-updated_at",),
            },
        ),
    ]
