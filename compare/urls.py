from django.urls import path

from .views import ComparisonListView, ComparisonDetailView

app_name = "compare"

urlpatterns = [
    # path("", views.index, name="index"),
    # path("<slug:slug>/", views.detail, name="detail"),
    path("", ComparisonListView.as_view(), name="index"),
    path("<slug:slug>/", ComparisonDetailView.as_view(), name="detail"),
]
