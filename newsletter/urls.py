from django.urls import path

from .views import ConfirmSubscriptionView, SubscribeView, UnsubscribeView, UnsubscribeDoneView, UnsubscribeConfirmView

app_name = "newsletter"

urlpatterns = [
    path("", SubscribeView.as_view(), name="subscribe"),
    path("confirm/<str:token>/", ConfirmSubscriptionView.as_view(), name="confirm"),
    path("unsubscribe/", UnsubscribeView.as_view(), name="unsubscribe"),
    path("unsubscribe/done/", UnsubscribeDoneView.as_view(), name="unsubscribe_done"),
    path("u/<str:token>/", UnsubscribeConfirmView.as_view(), name="unsubscribe_confirm"),
]
