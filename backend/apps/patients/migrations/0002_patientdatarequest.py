from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("patients", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PatientDataRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "request_type",
                    models.CharField(
                        choices=[
                            ("access_export", "Access export"),
                            ("deletion", "Deletion"),
                        ],
                        max_length=24,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("requested", "Requested"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("fulfilled", "Fulfilled"),
                        ],
                        default="requested",
                        max_length=16,
                    ),
                ),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("reason", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("fulfilled_at", models.DateTimeField(blank=True, null=True)),
                ("fulfillment_summary", models.JSONField(blank=True, default=dict)),
                ("review_notes", models.TextField(blank=True)),
                (
                    "fulfilled_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fulfilled_patient_data_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="data_requests",
                        to="patients.patient",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="patient_data_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_patient_data_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-requested_at",),
                "indexes": [
                    models.Index(
                        fields=["patient", "status", "requested_at"],
                        name="patients_pati_8c5d5d_idx",
                    )
                ],
            },
        ),
    ]
