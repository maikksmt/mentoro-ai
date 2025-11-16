from django.contrib import admin

from core.admin import TranslatableTinyMCEMixin
from .models import Subscriber

admin.site.site_header = "MentoroAI – Admin"


@admin.register(Subscriber)
class SubscriberAdmin(TranslatableTinyMCEMixin):
    list_display = ("email", "double_opt_in", "is_subscribed", "created_at", "unsubscribed_at")
    search_fields = ("email",)
    readonly_fields = ("confirmed_at", "unsubscribed_at")
