from django.urls import path
from .views import UseCaseListView, UseCaseDetailView

app_name = "usecases"

urlpatterns = [
    path("", UseCaseListView.as_view(), name="list"),
    path("<slug:slug>/", UseCaseDetailView.as_view(), name="detail"),
]
