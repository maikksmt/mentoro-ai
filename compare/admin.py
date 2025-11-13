from django.contrib import admin, messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.admin import TranslatableTinyMCEMixin
from .models import Comparison


@admin.register(Comparison)
class ComparisonAdmin(TranslatableTinyMCEMixin):
    tinymce_fields = ("intro",)

    # Listenansicht
    list_display = (
        "title_col",
        "status",
        "published_at",
        "author",
        "reviewer",
        "winner",
        "updated_at",
        "pk",
    )
    list_display_links = ("title_col",)
    ordering = ("-published_at", "-updated_at")

    # Filter & Suche
    list_filter = ("status", "author", "reviewer")
    search_fields = ("translations__title", "translations__intro", "slug")

    # Felder im Formular
    fieldsets = (
        (_("Meta"), {
            "fields": ("status", "published_at", "updated_at", "author", "reviewer")
        }),
        (_("Routing"), {
            "fields": ("slug",)
        }),
        (_("Content (translated)"), {
            "fields": ("title", "intro"),
            "description": _(
                "These fields are language-specific. Use the language tabs above."
            ),
        }),
        (_("Relations"), {
            "fields": ("tools", "winner"),
        }),
        (_("Scoring"), {
            "fields": ("score_breakdown",),
        }),
    )

    readonly_fields = ("updated_at",)
    filter_horizontal = ("tools",)

    def get_prepopulated_fields(self, request, obj=None):
        return {"slug": ("title",)}

    def title_col(self, obj):
        return obj.safe_translation_getter("title", any_language=True) or f"#{obj.pk}"

    title_col.short_description = _("Title")
    title_col.admin_order_field = "translations__title"
    actions = ("publish_now", "unpublish")

    def save_model(self, request, obj, form, change):
        if not obj.author and request.user and request.user.is_authenticated:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description=_("Publish now"))
    def publish_now(self, request, queryset):
        n = 0
        now = timezone.now()
        for obj in queryset:
            obj.publish(when=now)
            obj.save(update_fields=["status", "published_at", "updated_at"])
            n += 1
        self.message_user(request, _("%(n)d comparison(s) published.") % {"n": n}, messages.SUCCESS)

    @admin.action(description=_("Unpublish (revert to draft)"))
    def unpublish(self, request, queryset):
        n = 0
        for obj in queryset:
            obj.unpublish()
            obj.save(update_fields=["status", "updated_at"])
            n += 1
        self.message_user(request, _("%(n)d comparison(s) reverted to draft.") % {"n": n}, messages.WARNING)
