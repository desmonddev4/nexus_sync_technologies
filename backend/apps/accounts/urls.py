from django.urls import path

from .views import AccountDetailView, AccountListCreateView


urlpatterns = [
    path("accounts/", AccountListCreateView.as_view(), name="account-list-create"),
    path("accounts/<int:pk>/", AccountDetailView.as_view(), name="account-detail"),
]
