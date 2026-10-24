import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_faceresearchsample"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FaceLoginEmbedding",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("encrypted_embedding", models.BinaryField()),
                ("model_name", models.CharField(max_length=64)),
                ("consent_version", models.CharField(max_length=40)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="face_login_embedding", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
