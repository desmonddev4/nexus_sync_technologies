from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("emergency_services", "0003_alter_emergencyprovider_verification_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="emergencyprovider",
            name="api_integration_authorized",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="emergencyprovider",
            name="fleet_feed_authorized",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="emergencyprovider",
            name="integration_authorization_reference",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="emergencyprovider",
            name="integration_authorized_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
