from django.urls import path

from .views import EscalationPolicyView


urlpatterns = [
    path("settings/escalation-policy/", EscalationPolicyView.as_view(), name="escalation-policy"),
]
