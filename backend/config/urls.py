from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.views import AuditedObtainAuthToken, CurrentUserView
from apps.incidents.views import IncidentViewSet
from apps.notifications.webhooks import SasuSyncWebhookView
from apps.patients.views import PatientDataRequestViewSet, PatientViewSet


api_router = DefaultRouter()
api_router.register("incidents", IncidentViewSet, basename="incident")
api_router.register("patients", PatientViewSet, basename="patient")
api_router.register("patient-data-requests", PatientDataRequestViewSet, basename="patient-data-request")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/token/", AuditedObtainAuthToken.as_view(), name="api-token-auth"),
    path("api/v1/auth/me/", CurrentUserView.as_view(), name="api-current-user"),
    path("api/v1/integrations/sasusync/webhook/", SasuSyncWebhookView.as_view(), name="sasusync-webhook"),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.devices.urls")),
    path("api/v1/", include("apps.emergency_services.urls")),
    path("api/v1/", include("apps.monitoring.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.audit.urls")),
    path("api/v1/", include(api_router.urls)),
]