from apps.accounts.models import AccountProfile
from .models import EmergencyContact, PatientAccessGrant


def has_patient_access(user, patient, scope="patient"):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        profile = user.profile
    except AccountProfile.DoesNotExist:
        return False
    if profile.role == AccountProfile.Role.PATIENT:
        return profile.patient_id == patient.pk
    if profile.role != AccountProfile.Role.EMERGENCY_CONTACT or not profile.phone_number:
        return False
    verified_contact = EmergencyContact.objects.filter(
        patient=patient, phone_number=profile.phone_number,
        verification_status=EmergencyContact.VerificationStatus.VERIFIED,
    ).exists()
    if not verified_contact:
        return False
    grants = PatientAccessGrant.objects.filter(patient=patient, user=user, revoked_at__isnull=True)
    return any(scope in scopes for scopes in grants.values_list("scopes", flat=True))
