from django.urls import path
from django.views.generic import TemplateView

app_name = "legal"

urlpatterns = [
    path(
        "legal-notice/",
        TemplateView.as_view(template_name="legal/legal_notice.html"),
        name="legal-notice",
    ),
    path(
        "privacy/",
        TemplateView.as_view(template_name="legal/privacy_policy.html"),
        name="privacy",
    ),
    path(
        "cookies/",
        TemplateView.as_view(template_name="legal/cookie_policy.html"),
        name="cookies",
    ),
    path(
        "terms/",
        TemplateView.as_view(template_name="legal/terms_of_use.html"),
        name="terms-of-use",
    ),
    path(
        "copyright/",
        TemplateView.as_view(template_name="legal/copyright.html"),
        name="copyright",
    ),
]
