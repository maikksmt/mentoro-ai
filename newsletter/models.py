import secrets

from django.db import models
from django.utils import timezone


class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    double_opt_in = models.BooleanField(default=False)
    unsubscribed_at = models.DateTimeField(blank=True, null=True)
    unsubscribed_reason = models.CharField(max_length=250, blank=True)
    source = models.CharField(max_length=150, blank=True)
    tags = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    doi_token = models.CharField(max_length=64, unique=True, blank=True, null=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.email

    @property
    def is_subscribed(self) -> bool:
        return bool(self.double_opt_in and not self.unsubscribed_at)

    def refresh_doi_token(self, commit: bool = True) -> str:
        token = secrets.token_urlsafe(32)
        self.doi_token = token
        if commit:
            self.save(update_fields=["doi_token"])
        return token

    def mark_confirmed(self) -> None:
        self.double_opt_in = True
        self.confirmed_at = timezone.now()
        self.doi_token = None
        self.unsubscribed_at = None
        self.save(update_fields=["double_opt_in", "confirmed_at", "doi_token", "unsubscribed_at"])

    def mark_unsubscribed(self, reason: str = "") -> None:
        self.double_opt_in = False
        self.unsubscribed_at = timezone.now()
        self.unsubscribed_reason = (reason or "")[:250]
        self.save(update_fields=["double_opt_in", "unsubscribed_at", "unsubscribed_reason"])
