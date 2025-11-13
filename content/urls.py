from django.urls import path, include
from .views import home

app_name = "content"

urlpatterns = [
    path("", home.HomePageView.as_view(), name="home"),
    path("editorial/", include("content.urls_editorial", namespace="editorial")),
]
