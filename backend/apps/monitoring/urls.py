from django.urls import path

from .views import MeasurementIngestView, PatientLocationIngestView


urlpatterns = [
    path("measurements/", MeasurementIngestView.as_view(), name="measurement-ingest"),
    path("locations/", PatientLocationIngestView.as_view(), name="location-ingest"),
]