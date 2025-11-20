from django.urls import path

from .views import AccountDashboardView

urlpatterns = [
    path("", AccountDashboardView.as_view(), name="account_dashboard"),
]
