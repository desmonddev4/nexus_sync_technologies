from django.urls import path

from .views import AuditLogExportView, AuditLogListView


urlpatterns = [
    path("audit/logs/", AuditLogListView.as_view(), name="audit-log-list"),
    path("audit/logs/export/", AuditLogExportView.as_view(), name="audit-log-export"),
]
