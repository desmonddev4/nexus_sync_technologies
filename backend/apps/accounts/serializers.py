from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.patients.models import Patient

from .models import AccountProfile


class AccountAdminSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=AccountProfile.Role.choices, write_only=True, required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True, write_only=True)
    patient = serializers.PrimaryKeyRelatedField(
        queryset=Patient.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "username",
            "email",
            "is_active",
            "date_joined",
            "last_login",
            "role",
            "phone_number",
            "patient",
            "password",
        )
        read_only_fields = ("id", "date_joined", "last_login")

    def validate(self, attrs):
        current_profile = getattr(self.instance, "profile", None) if self.instance else None
        effective_role = attrs.get("role", current_profile.role if current_profile else None)
        effective_patient = attrs.get("patient", current_profile.patient if current_profile else None)

        if effective_role == AccountProfile.Role.PATIENT and effective_patient is None:
            raise serializers.ValidationError({"patient": "Patient role requires a linked patient record."})
        if effective_role != AccountProfile.Role.PATIENT and effective_patient is not None:
            raise serializers.ValidationError({"patient": "Only patient-role accounts may be linked to a patient."})

        if effective_patient is not None:
            existing_profile = AccountProfile.objects.filter(patient=effective_patient).first()
            if existing_profile and (self.instance is None or existing_profile.user_id != self.instance.pk):
                raise serializers.ValidationError({"patient": "This patient is already linked to another account."})

        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Password is required when creating an account."})
        if (self.instance is None or current_profile is None) and not attrs.get("role"):
            raise serializers.ValidationError({"role": "An explicit role is required when creating or provisioning an account."})
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        profile = getattr(instance, "profile", None)
        data["role"] = profile.role if profile else None
        data["phone_number"] = profile.phone_number if profile else ""
        data["patient"] = str(profile.patient_id) if profile and profile.patient_id else None
        return data

    def create(self, validated_data):
        role = validated_data.pop("role", None)
        phone_number = validated_data.pop("phone_number", "")
        patient = validated_data.pop("patient", None)
        password = validated_data.pop("password")

        user_model = get_user_model()
        user = user_model.objects.create_user(password=password, **validated_data)
        AccountProfile.objects.create(
            user=user,
            role=role,
            phone_number=phone_number,
            patient=patient,
        )
        return user

    def update(self, instance, validated_data):
        role = validated_data.pop("role", None)
        phone_number = validated_data.pop("phone_number", None)
        patient_provided = "patient" in validated_data
        patient = validated_data.pop("patient", None)
        password = validated_data.pop("password", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()

        profile = getattr(instance, "profile", None)
        if profile is None:
            profile = AccountProfile(user=instance, role=role)
        if role is not None:
            profile.role = role
        if phone_number is not None:
            profile.phone_number = phone_number
        if role == AccountProfile.Role.PATIENT:
            if patient_provided:
                profile.patient = patient
        elif role is not None:
            profile.patient = None
        elif patient_provided:
            profile.patient = patient
        profile.save()
        return instance
