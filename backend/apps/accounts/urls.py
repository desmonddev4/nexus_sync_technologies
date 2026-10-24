from django.urls import path

from .biometric_views import FaceResearchSamplesView
from .face_auth_views import FaceLoginEnrollmentView, FaceLivenessChallengeView, FaceMotionResearchCheckView, FaceTokenView
from .views import AccountDetailView, AccountListCreateView


urlpatterns = [
    path("accounts/", AccountListCreateView.as_view(), name="account-list-create"),
    path("accounts/<int:pk>/", AccountDetailView.as_view(), name="account-detail"),
    path("auth/biometrics/research-samples/", FaceResearchSamplesView.as_view(), name="biometric-research-samples"),
    path("auth/biometrics/face-enrollment/", FaceLoginEnrollmentView.as_view(), name="biometric-face-enrollment"),
    path("auth/face-liveness-challenge/", FaceLivenessChallengeView.as_view(), name="face-liveness-challenge"),
    path("auth/biometrics/motion-check/", FaceMotionResearchCheckView.as_view(), name="face-motion-research-check"),
    path("auth/face-token/", FaceTokenView.as_view(), name="face-token-auth"),
]
