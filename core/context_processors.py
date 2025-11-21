# core/context_processors.py
from django.conf import settings


def account_signup_settings(request):
    return {
        "ACCOUNT_SIGNUP_ENABLED": getattr(settings, "ACCOUNT_SIGNUP_ENABLED", True),
    }
