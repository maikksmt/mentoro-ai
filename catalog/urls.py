from django.urls import path

from .views import ToolListView, ToolDetailView

app_name = "catalog"

urlpatterns = [
    # path("", views.tool_list, name="list"),
    # path("<slug:slug>/", views.tool_detail, name="detail"),
    path("", ToolListView.as_view(), name="list"),
    path("<slug:slug>/", ToolDetailView.as_view(), name="detail"),
]
