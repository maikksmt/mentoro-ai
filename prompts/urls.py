from django.urls import path

from .views import PromptListView, PromptDetailView

app_name = "prompts"

urlpatterns = [
    path("", PromptListView.as_view(), name="list"),
    path("<slug:slug>/", PromptDetailView.as_view(), name="detail"),
]
