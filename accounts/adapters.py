# accounts/adapters.py
from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class ToggleSignupAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return getattr(settings, "ACCOUNT_SIGNUP_ENABLED", True)
