# prompts/admin.py
import reversion
from django.conf import settings
from django.contrib import admin, messages
from django.db import transaction
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _, get_language, get_language_info
from django_fsm import can_proceed
from parler.utils.context import switch_language

from core.admin import TranslatableTinyMCEMixin
from core.services import get_live_display_instance, build_field_diffs
from .models import Prompt


@admin.register(Prompt)
class PromptAdmin(TranslatableTinyMCEMixin):
    tinymce_fields = ("intro", "body", "outro")
    list_display = (
        "display_title", "pk", "status", "is_published", "author", "reviewer",
        "published_at_formatted", "updated_at_formatted",
    )
    list_filter = ("status", "author", "reviewer")
    search_fields = ("translations__title", "translations__intro", "translations__body", "translations__slug")
    ordering = ("-published_at", "-updated_at")
    date_hierarchy = "published_at"

    readonly_fields = (
        "status",
        "submitted_for_review_at",
        "reviewed_at",
        "reviewed_by",
        "live_i18n",
        "is_published",
        "public_slug",
        "updated_at",
    )

    actions = [
        "action_submit_for_review",
        "action_request_rework",
        "action_publish",
        "action_archive",
        "action_restore_draft",
    ]

    fieldsets = (
        (_("Meta"), {
            "fields": (
                "author",
                "reviewer",
                "status",
                "is_published",
                "published_at",
                "updated_at",
                "submitted_for_review_at",
                "reviewed_at",
                "reviewed_by",
            ),
        }),
        (_("Routing"), {
            "fields": ("slug", "public_slug"),
        }),
        (_("Content (translated)"), {
            "fields": ("title", "intro", "body", "outro"),
            "description": _("These fields are language-specific. Use the language tabs above."),
        }),
        (_("Internals"), {
            "classes": ("collapse",),
            "fields": ("live_i18n",),
        }),
    )

    def get_urls(self):
        base_urls = super().get_urls()
        custom = [
            path("<path:object_id>/diff/", self.admin_site.admin_view(self.diff_view),
                 name="prompts_prompt_diff"),
        ]
        return custom + base_urls

    def diff_view(self, request, object_id, *args, **kwargs):
        prompt = self.get_object(request, object_id)
        live_keys = set((prompt.live_i18n or {}).keys()) if hasattr(prompt, "live_i18n") else set()
        obj_langs = set(getattr(prompt, "get_available_languages", lambda: [])())  # Parler
        project_langs = {code for code, _ in getattr(settings, "LANGUAGES", [])}
        langs = []
        for code in list(project_langs) + list(obj_langs) + list(live_keys):
            if code and code not in langs:
                langs.append(code)
        if not langs:
            langs = [get_language()]

        comparisons = []
        for lang in langs:
            with switch_language(prompt, lang):
                left = {
                    "slug": prompt.safe_translation_getter("slug"),
                    "public_slug": prompt.safe_translation_getter("public_slug"),
                    "title": prompt.safe_translation_getter("title"),
                    "intro": prompt.safe_translation_getter("intro"),
                    "body": prompt.safe_translation_getter("body"),
                    "outro": prompt.safe_translation_getter("outro"),
                }

            live = get_live_display_instance(prompt, lang)
            with switch_language(prompt, lang):
                right = {
                    "slug": getattr(live, "slug", None),
                    "public_slug": getattr(live, "public_slug", None),
                    "title": getattr(live, "title", None),
                    "intro": getattr(live, "intro", None),
                    "body": getattr(live, "body", None),
                    "outro": getattr(live, "outro", None),
                }

            changes = build_field_diffs(left, right)
            if not changes:
                continue

            info = get_language_info(lang)
            comparisons.append({
                "code": lang,
                "name": info.get("name_local") or info.get("name") or lang,
                "changes": changes,
            })

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "object": prompt,
            "comparisons": comparisons,
        }
        return TemplateResponse(request, "admin/prompts/prompt_diff.html", context)

    def get_prepopulated_fields(self, request, obj=None):
        return {"slug": ("title",)}

    def published_at_formatted(self, obj):
        if not obj.published_at:
            return "-"
        return date_format(obj.published_at, format="d.m.Y H:i", use_l10n=True)

    def updated_at_formatted(self, obj):
        if not obj.updated_at:
            return "-"
        return date_format(obj.updated_at, format="d.m.Y H:i", use_l10n=True)

    def save_model(self, request, obj: Prompt, form, change):
        if not change and getattr(obj, "author_id", None) is None:
            obj.author = request.user

        original = None
        if change and obj.pk:
            try:
                original = Prompt.objects.get(pk=obj.pk)
            except Prompt.DoesNotExist:
                original = None

        if self._must_auto_review(original, form, formsets=None):
            self._auto_transition_to_review(request, obj)

        super().save_model(request, obj, form, change)

    def _must_auto_review(self, original, form, formsets) -> bool:
        if not original:
            return False
        if getattr(original, "status", "") != getattr(original, "STATUS_PUBLISHED", "published"):
            return False
        return form.has_changed()

    def _auto_transition_to_review(self, request, obj):
        if hasattr(obj, "move_to_review") and can_proceed(obj.move_to_review):
            try:
                obj.move_to_review(by=request.user, note=_("Auto: Change in the admin form (prompt)"))
            except TypeError:
                obj.move_to_review()
            obj.save()
            self.message_user(
                request,
                _('Prompt was automatically set to "Review" due to changes.'),
                level=messages.INFO,
            )

    @admin.action(description=_("Submit for Review"))
    def action_submit_for_review(self, request, queryset):
        moved, skipped = 0, []
        with transaction.atomic():
            with reversion.create_revision():
                reversion.set_user(request.user)
                reversion.set_comment("Admin-Action: submit_for_review")
                for obj in queryset.select_for_update():
                    if hasattr(obj, "move_to_review") and can_proceed(obj.move_to_review):
                        try:
                            obj.move_to_review(by=request.user, note="Admin-Action: submit_for_review")
                        except TypeError:
                            obj.move_to_review()
                        obj.save()
                        moved += 1
                    else:
                        skipped.append((obj.pk, "Transition 'move_to_review' not possible"))
        if moved:
            self.message_user(request, _("%d Article(s) set for review.") % moved, level=messages.SUCCESS)
        if skipped:
            info = ", ".join([f"#{pk}: {reason}" for pk, reason in skipped])
            self.message_user(request, "%d skipped: %s" % (len(skipped), info), level=messages.WARNING)

    @admin.action(description=_("Request rework"))
    def action_request_rework(self, request, queryset):
        moved, skipped = 0, []
        with transaction.atomic():
            with reversion.create_revision():
                reversion.set_user(request.user)
                reversion.set_comment("Admin-Action: request_rework")
                for obj in queryset.select_for_update():
                    if hasattr(obj, "request_rework") and can_proceed(obj.request_rework):
                        try:
                            obj.request_rework(by=request.user, note="Admin-Action: request_rework")
                        except TypeError:
                            obj.request_rework()
                        obj.save()
                        moved += 1
                    else:
                        skipped.append((obj.pk, "Transition 'request_rework' not possible"))
        if moved:
            self.message_user(request, _("%d Article(s) set to rework.") % moved, level=messages.SUCCESS)
        if skipped:
            info = ", ".join([f"#{pk}: {reason}" for pk, reason in skipped])
            self.message_user(request, "%d skipped: %s" % (len(skipped), info), level=messages.WARNING)

    @admin.action(description=_("Publish"))
    def action_publish(self, request, queryset):
        published, skipped = 0, []
        with transaction.atomic():
            with reversion.create_revision():
                reversion.set_user(request.user)
                reversion.set_comment("Admin-Action: publish")
                for obj in queryset.select_for_update():
                    if getattr(obj, "status", None) == getattr(obj, "STATUS_PUBLISHED", "published"):
                        continue
                    if hasattr(obj, "publish") and can_proceed(obj.publish):
                        try:
                            obj.publish(by=request.user, note="Admin-Action publish")
                            obj.save()
                            published += 1
                        except Exception as e:
                            skipped.append((obj.pk, str(e)))
                    else:
                        skipped.append((obj.pk, "Transition 'publish' not possible"))
        if published:
            self.message_user(request, _("%d Article(s) published.") % published, level=messages.SUCCESS)
        if skipped:
            info = ", ".join([f"#{pk}: %s" % reason for pk, reason in skipped])
            self.message_user(request, "%d skipped: %s" % (len(skipped), info), level=messages.WARNING)

    @admin.action(description=_("Archive (Soft-Delete)"))
    def action_archive(self, request, queryset):
        ok, skipped = 0, []
        with reversion.create_revision():
            for obj in queryset:
                if hasattr(obj, "archive") and can_proceed(obj.archive):
                    try:
                        obj.archive(by=request.user, note="Admin-Action: archive")
                    except TypeError:
                        obj.archive(by=request.user)
                    obj.save()
                    ok += 1
                else:
                    skipped.append(obj.pk)
        if ok:
            self.message_user(request, _("%d Article(s) archived.") % ok, level=messages.SUCCESS)
        if skipped:
            self.message_user(request, "%d Skipped: Transition not possible (%s)." % (
                len(skipped), ", ".join(map(str, skipped))), level=messages.WARNING)

    @admin.action(description=_("Restore as draft"))
    def action_restore_draft(self, request, queryset):
        ok, skipped = 0, []
        with reversion.create_revision():
            for obj in queryset:
                if hasattr(obj, "restore") and can_proceed(obj.restore):
                    try:
                        obj.restore(by=request.user, note="Admin-Action: restore_to_draft")
                    except TypeError:
                        obj.restore(by=request.user)
                    obj.save()
                    ok += 1
                else:
                    skipped.append(obj.pk)
        if ok:
            self.message_user(request, _("%d Article(s) restored (Draft).") % ok, level=messages.SUCCESS)
        if skipped:
            self.message_user(request, "%d Skipped: Transition not possible (%s)." % (
                len(skipped), ", ".join(map(str, skipped))), level=messages.WARNING)
