from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied

from apps.accounts.models import AccountProfile
from apps.audit.services import record_audit_event

from .models import Patient
from .permissions import CanAccessPatientRecords
from .serializers import PatientSerializer


class PatientViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PatientSerializer
    permission_classes = [CanAccessPatientRecords]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Patient.objects.all()

        try:
            profile = user.profile
        except AccountProfile.DoesNotExist:
            return Patient.objects.none()

        if profile.role in {
            AccountProfile.Role.EMERGENCY_COORDINATOR,
            AccountProfile.Role.CLINICIAN,
        }:
            return Patient.objects.all()
        if profile.role == AccountProfile.Role.PATIENT and profile.patient_id:
            return Patient.objects.filter(pk=profile.patient_id)
        return Patient.objects.none()

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        record_audit_event(
            request=request,
            action="patient.list",
            resource_type="patient",
            metadata={"result_count": len(response.data)},
        )
        return response

    def get_object(self):
        try:
            patient = super().get_object()
        except (Http404, DjangoPermissionDenied, DRFPermissionDenied):
            record_audit_event(
                request=self.request,
                action="patient.access_denied",
                resource_type="patient",
                resource_id=self.kwargs.get(self.lookup_url_kwarg or self.lookup_field, ""),
                outcome="denied",
            )
            raise
        record_audit_event(
            request=self.request,
            action="patient.read" if self.action == "retrieve" else f"patient.{self.action}.accessed",
            resource_type="patient",
            resource_id=patient.pk,
        )
        return patient

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        patient = serializer.save()
        record_audit_event(
            request=self.request,
            action="patient.created",
            resource_type="patient",
            resource_id=patient.pk,
        )

    def perform_update(self, serializer):
        patient = serializer.save()
        record_audit_event(
            request=self.request,
            action="patient.updated",
            resource_type="patient",
            resource_id=patient.pk,
        )