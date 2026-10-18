from django.db import transaction
from django.utils import timezone

from apps.accounts.models import AccountProfile
from apps.devices.models import Device

from .models import ConsentRecord, EmergencyContact, Patient, PatientDataRequest


@transaction.atomic
def build_patient_data_export(patient):
    patient = Patient.objects.get(pk=patient.pk)
    return {
        "patient": {
            "id": str(patient.pk),
            "full_name": patient.full_name,
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "phone_number": patient.phone_number,
            "relevant_medical_notes": patient.relevant_medical_notes,
            "status": patient.status,
        },
        "emergency_contacts": list(
            patient.emergency_contacts.values(
                "id",
                "name",
                "relationship",
                "phone_number",
                "priority_order",
                "verification_status",
            )
        ),
        "consent_records": list(
            patient.consent_records.values(
                "id",
                "scope",
                "status",
                "policy_version",
                "recorded_at",
            )
        ),
        "device_count": patient.devices.count(),
        "measurement_count": patient.measurements.count(),
        "location_count": patient.locations.count(),
        "incident_count": patient.incidents.count(),
    }


@transaction.atomic
def redact_patient_data(patient, *, actor=None):
    patient = Patient.objects.select_for_update().get(pk=patient.pk)
    patient.full_name = "Redacted Patient"
    patient.date_of_birth = None
    patient.phone_number = ""
    patient.relevant_medical_notes = ""
    patient.status = Patient.Status.INACTIVE
    patient.save(
        update_fields=("full_name", "date_of_birth", "phone_number", "relevant_medical_notes", "status", "updated_at")
    )
    EmergencyContact.objects.filter(patient=patient).delete()
    ConsentRecord.objects.filter(patient=patient).delete()
    Device.objects.filter(patient=patient).update(patient=None, status=Device.Status.INACTIVE)
    AccountProfile.objects.filter(patient=patient).update(patient=None)
    return patient


@transaction.atomic
def create_patient_data_request(*, patient, requested_by, request_type, reason=""):
    return PatientDataRequest.objects.create(
        patient=patient,
        requested_by=requested_by,
        request_type=request_type,
        reason=reason,
    )


@transaction.atomic
def approve_patient_data_request(*, data_request, reviewer, notes=""):
    data_request = PatientDataRequest.objects.select_for_update().get(pk=data_request.pk)
    if data_request.status != PatientDataRequest.Status.REQUESTED:
        raise ValueError("Only requested data requests can be approved.")
    data_request.status = PatientDataRequest.Status.APPROVED
    data_request.reviewed_by = reviewer
    data_request.reviewed_at = timezone.now()
    data_request.review_notes = notes
    data_request.save(
        update_fields=("status", "reviewed_by", "reviewed_at", "review_notes", "updated_at")
    )
    return data_request


@transaction.atomic
def reject_patient_data_request(*, data_request, reviewer, notes=""):
    data_request = PatientDataRequest.objects.select_for_update().get(pk=data_request.pk)
    if data_request.status not in {PatientDataRequest.Status.REQUESTED, PatientDataRequest.Status.APPROVED}:
        raise ValueError("Only pending requests can be rejected.")
    data_request.status = PatientDataRequest.Status.REJECTED
    data_request.reviewed_by = reviewer
    data_request.reviewed_at = timezone.now()
    data_request.review_notes = notes
    data_request.save(
        update_fields=("status", "reviewed_by", "reviewed_at", "review_notes", "updated_at")
    )
    return data_request


@transaction.atomic
def fulfill_patient_data_request(*, data_request, fulfiller):
    data_request = PatientDataRequest.objects.select_for_update().get(pk=data_request.pk)
    if data_request.status != PatientDataRequest.Status.APPROVED:
        raise ValueError("Only approved requests can be fulfilled.")

    if data_request.request_type == PatientDataRequest.RequestType.ACCESS_EXPORT:
        summary = build_patient_data_export(data_request.patient)
    else:
        redacted_patient = redact_patient_data(data_request.patient, actor=fulfiller)
        summary = {
            "patient_id": str(redacted_patient.pk),
            "action": "redacted",
            "contacts_deleted": True,
            "consents_deleted": True,
            "devices_unlinked": True,
        }

    data_request.status = PatientDataRequest.Status.FULFILLED
    data_request.fulfilled_by = fulfiller
    data_request.fulfilled_at = timezone.now()
    data_request.fulfillment_summary = summary
    data_request.save(
        update_fields=("status", "fulfilled_by", "fulfilled_at", "fulfillment_summary", "updated_at")
    )
    return data_request
