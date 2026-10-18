from django.urls import path

from .views import (
    MeasurementIngestView,
    MonitoringRuleDetailView,
    MonitoringRuleEvaluationsView,
    MonitoringRuleListCreateView,
    MonitoringRuleReviewView,
    PatientLocationIngestView,
)


urlpatterns = [
    path("measurements/", MeasurementIngestView.as_view(), name="measurement-ingest"),
    path("locations/", PatientLocationIngestView.as_view(), name="location-ingest"),
    path("monitoring/rules/", MonitoringRuleListCreateView.as_view(), name="monitoring-rule-list"),
    path("monitoring/rules/<uuid:pk>/", MonitoringRuleDetailView.as_view(), name="monitoring-rule-detail"),
    path("monitoring/rules/<uuid:rule_id>/review/", MonitoringRuleReviewView.as_view(), name="monitoring-rule-review"),
    path(
        "monitoring/rules/<uuid:rule_id>/evaluations/",
        MonitoringRuleEvaluationsView.as_view(),
        name="monitoring-rule-evaluations",
    ),
]