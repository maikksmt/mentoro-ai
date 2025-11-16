# usecases/admin.py
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
from .models import UseCase


@admin.register(UseCase)
class UseCaseAdmin(TranslatableTinyMCEMixin):
    tinymce_fields = ("intro", "body")
    list_display = (
        "display_title", "pk", "status", "is_published", "author", "reviewer",
        "published_at_fmt", "updated_at_fmt",
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
            "fields": ("slug", "public_slug", "tools"),
        }),
        (_("Content (translated)"), {
            "fields": ("title", "intro", "body"),
            "description": _(
                "These fields are language-specific. Use the language tabs above."
            ),
        }),
        (_("Internals"), {
            "classes": ("collapse",),
            "fields": ("live_i18n",),
        }),
    )

    def get_urls(self):
        base = super().get_urls()
        custom = [
            path("<path:object_id>/diff/", self.admin_site.admin_view(self.diff_view),
                 name="usecases_usecase_diff"),
        ]
        return custom + base

    def diff_view(self, request, object_id, *args, **kwargs):
        obj = self.get_object(request, object_id)

        project_langs = [code for code, _ in getattr(settings, "LANGUAGES", ())]
        obj_langs = list(getattr(obj, "get_available_languages", lambda: [])())
        live_langs = list((getattr(obj, "live_i18n", {}) or {}).keys())

        langs, seen = [], set()
        for code in project_langs + obj_langs + live_langs:
            if code and code not in seen:
                langs.append(code)
                seen.add(code)
        if not langs:
            langs = [get_language()]

        comparisons = []
        for lang in langs:
            with switch_language(obj, lang):
                left = {
                    "slug": obj.safe_translation_getter("slug"),
                    "public_slug": obj.safe_translation_getter("public_slug"),
                    "title": obj.safe_translation_getter("title"),
                    "intro": obj.safe_translation_getter("intro"),
                    "body": obj.safe_translation_getter("body"),
                }

            live = get_live_display_instance(obj, lang)
            right = {
                "slug": getattr(live, "slug", None),
                "public_slug": getattr(live, "public_slug", None),
                "title": getattr(live, "title", None),
                "intro": getattr(live, "intro", None),
                "body": getattr(live, "body", None),
            }

            changes = build_field_diffs(left, right)
            if changes:
                info = get_language_info(lang)
                comparisons.append({
                    "code": lang,
                    "name": info.get("name_local") or info.get("name") or lang,
                    "changes": changes,
                })

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "object": obj,
            "comparisons": comparisons,
        }
        return TemplateResponse(request, "admin/usecases/usecase_diff.html", context)

    def get_prepopulated_fields(self, request, obj=None):
        return {"slug": ("title",)}

    def display_title(self, obj):
        return obj.safe_translation_getter("title", any_language=True) or f"#{obj.pk}"

    display_title.short_description = _("Title")

    def published_at_fmt(self, obj):
        return date_format(obj.published_at, "d.m.Y H:i", use_l10n=True) if obj.published_at else "-"

    def updated_at_fmt(self, obj):
        return date_format(obj.updated_at, "d.m.Y H:i", use_l10n=True) if obj.updated_at else "-"

    # --- Auto-Review bei Änderungen eines veröffentlichten Objekts ---
    def save_model(self, request, obj: UseCase, form, change):
        if not change and getattr(obj, "author_id", None) is None:
            obj.author = request.user

        original = None
        if change and obj.pk:
            try:
                original = UseCase.objects.get(pk=obj.pk)
            except UseCase.DoesNotExist:
                pass

        if original and getattr(original, "status", "") == getattr(obj, "STATUS_PUBLISHED", "published"):
            if form.has_changed():
                if hasattr(obj, "move_to_review") and can_proceed(obj.move_to_review):
                    try:
                        obj.move_to_review(by=request.user, note="Auto: Änderung im Admin-Formular (UseCase)")
                    except TypeError:
                        obj.move_to_review()
        super().save_model(request, obj, form, change)

    @admin.action(description=_("Submit for review"))
    def action_submit_for_review(self, request, queryset):
        moved, skipped = 0, []
        with transaction.atomic():
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
            self.message_user(request, _("%d item(s) moved to review.") % moved, level=messages.SUCCESS)
        if skipped:
            self.message_user(request,
                              "%d skipped: %s" % (len(skipped), ", ".join([f"#{pk}: {r}" for pk, r in skipped])),
                              level=messages.WARNING)

    @admin.action(description=_("Request rework"))
    def action_request_rework(self, request, queryset):
        moved, skipped = 0, []
        with transaction.atomic():
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
            self.message_user(request, _("%d item(s) moved to rework.") % moved, level=messages.SUCCESS)
        if skipped:
            self.message_user(request,
                              "%d skipped: %s" % (len(skipped), ", ".join([f"#{pk}: {r}" for pk, r in skipped])),
                              level=messages.WARNING)

    @admin.action(description=_("Publish"))
    def action_publish(self, request, queryset):
        ok, skipped = 0, []
        with transaction.atomic():
            for obj in queryset.select_for_update():
                if hasattr(obj, "publish") and can_proceed(obj.publish):
                    try:
                        obj.publish(by=request.user, note="Admin-Action: publish")
                    except TypeError:
                        obj.publish(by=request.user)
                    obj.save()
                    ok += 1
                else:
                    skipped.append((obj.pk, "Transition 'publish' not possible"))
        if ok:
            self.message_user(request, _("%d item(s) published.") % ok, level=messages.SUCCESS)
        if skipped:
            self.message_user(request,
                              "%d skipped: %s" % (len(skipped), ", ".join([f"#{pk}: {r}" for pk, r in skipped])),
                              level=messages.WARNING)

    @admin.action(description=_("Archive"))
    def action_archive(self, request, queryset):
        ok, skipped = 0, []
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
            self.message_user(request, _("%d item(s) archived.") % ok, level=messages.SUCCESS)
        if skipped:
            self.message_user(request,
                              "%d skipped: no transition (%s)." % (len(skipped), ", ".join(map(str, skipped))),
                              level=messages.WARNING)

    @admin.action(description=_("Restore to draft"))
    def action_restore_draft(self, request, queryset):
        ok, skipped = 0, []
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
            self.message_user(request, _("%d item(s) restored to draft.") % ok, level=messages.SUCCESS)
        if skipped:
            self.message_user(request,
                              "%d skipped: no transition (%s)." % (len(skipped), ", ".join(map(str, skipped))),
                              level=messages.WARNING)
