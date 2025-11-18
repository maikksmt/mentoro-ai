import reversion
from django.conf import settings
from django.contrib import admin, messages
from django.db import transaction
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _, get_language, get_language_info
from django_fsm import can_proceed
from parler.admin import TranslatableStackedInline
from parler.utils.context import switch_language
from reversion.admin import VersionAdmin

from core.admin import TranslatableTinyMCEMixin, TranslatableTinyMCEInlineMixin, set_last_published_revision
from core.services import get_live_display_instance, build_field_diffs, build_section_diffs
from .models import GuideItem, GuideSection, Guide


class GuideItemInline(TranslatableTinyMCEInlineMixin, TranslatableStackedInline):
    model = GuideItem
    extra = 0
    fields = ("order", "is_published", "kind", "content_type", "object_id", "url", "title", "teaser")
    tinymce_fields = ("teaser",)
    ordering = ("order", "id")
    show_change_link = True


class GuideSectionInline(TranslatableTinyMCEInlineMixin, TranslatableStackedInline):
    model = GuideSection
    extra = 0
    fields = ("order", "title", "body")
    ordering = ("order", "id")
    tinymce_fields = ("body",)
    show_change_link = True


@admin.register(Guide)
class GuideAdmin(TranslatableTinyMCEMixin, VersionAdmin):
    tinymce_fields = ("intro", "body")
    list_display = (
        "display_title", "pk", "status", "is_published", "author", "reviewed_by", "published_at_formatted",
        "updated_at_formatted")
    list_filter = ("status", "categories", "author", "reviewed_by")
    search_fields = ("translations__title", "translations__intro", "slug")
    ordering = ("-published_at", "-updated_at")
    date_hierarchy = "published_at"
    readonly_fields = (
        "status", "submitted_for_review_at", "reviewed_at", "reviewed_by", "live_i18n", "is_published",
        "public_slug", "updated_at", "last_published_revision_id",)
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
                "status",
                "is_published",
                "published_at",
                "updated_at",
                "submitted_for_review_at",
                "reviewed_at",
                "reviewed_by",
                "last_published_revision_id",

            )
        }),
        (_("Relations"), {
            "fields": ("categories", "tools"),
        }),
        (_("Routing"), {
            "fields": ("public_slug", "slug")
        }),
        (_("Content (translated)"), {
            "fields": ("title", "intro", "body"),
            "description": _("These fields are language-specific. Use the language tabs above."),
        }),

    )

    # ------- kleine Helfer für Spalten -------
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

    @admin.display(ordering="translations__title", description=_("Title"))
    def title_col(self, obj):
        return obj.safe_translation_getter("title", any_language=True) or f"Guide #{obj.pk}"

    published_at_formatted.short_description = "published_at"
    published_at_formatted.admin_order_field = "published_at"
    updated_at_formatted.short_description = "updated_at"
    updated_at_formatted.admin_order_field = "updated_at"
    title_col.short_description = _("Title")
    title_col.admin_order_field = "translations__title"

    def _must_auto_review(self, original_obj, form, formsets):
        """
        True, wenn der Guide aktuell published ist UND im Hauptformular
        ODER irgendeinem Inline Änderungen vorgenommen wurden.
        """
        if original_obj is None:
            return False
        if getattr(original_obj, "status", None) != original_obj.STATUS_PUBLISHED:
            return False

        if form and form.has_changed():
            return True

        for fs in (formsets or []):
            if getattr(fs, "changed_objects", None):
                if fs.changed_objects:
                    return True
            if getattr(fs, "new_objects", None):
                if fs.new_objects:
                    return True
            if getattr(fs, "deleted_objects", None):
                if fs.deleted_objects:
                    return True

            if getattr(fs, "changed_forms", None):
                if fs.changed_forms:
                    return True
            if getattr(fs, "new_forms", None):
                if fs.new_forms:
                    return True
            if getattr(fs, "deleted_forms", None):
                if fs.deleted_forms:
                    return True

        return False

    def _auto_transition_to_review(self, request, obj):
        """
        Führt die FSM-Transition aus PUBLISHED -> REVIEW aus, wenn der Benutzer darf.
        Nutzt rules-Permissions (submit_for_review: is_author | is_editor).
        """
        if not request.user.has_perm("content.submit_for_review", obj):
            # kein harter Fehler – wir lassen speichern, aber ohne Statuswechsel
            return
        # FSM-Transition (setzt submitted_for_review_at)
        obj.submit_for_review(by=request.user)

    def save_model(self, request, obj, form, change):
        if not change and getattr(obj, "author_id", None) is None:
            obj.author = request.user

        original = None
        if change and obj.pk:
            try:
                original = Guide.objects.get(pk=obj.pk)
            except Guide.DoesNotExist:
                original = None
        if self._must_auto_review(original, form, formsets=None):
            self._auto_transition_to_review(request, obj)

        super().save_model(request, obj, form, change)
        if getattr(obj, "status", None) == getattr(obj, "STATUS_PUBLISHED", "published") \
                and not getattr(obj, "last_published_revision_id", None):
            set_last_published_revision(obj)
            obj.save(update_fields=["last_published_revision_id"])

    def save_related(self, request, form, formsets, change):
        """
        Detects changes in the GuideSection inlines and automatically sets a published
        Guide to REVIEW before the relations are saved.
        """
        guide = form.instance
        inline_changed = False
        for fs in formsets:
            changed = any(getattr(f, "has_changed", lambda: False)() for f in fs.forms)
            new_forms = [
                f for f in fs.forms
                if not getattr(getattr(f, "instance", None), "pk", None)
                   and not f.cleaned_data.get("DELETE", False)
            ]
            deleted = bool(getattr(fs, "deleted_objects", []))

            if changed or new_forms or deleted:
                inline_changed = True
                break

        if inline_changed and getattr(guide, "status", None) == getattr(guide, "STATUS_PUBLISHED", "published"):
            if hasattr(guide, "move_to_review") and can_proceed(guide.move_to_review):
                try:
                    guide.move_to_review(by=request.user, note=_("Auto: Change to GuideSection (Inline)"))
                except TypeError:
                    guide.move_to_review()
                guide.save()

        return super().save_related(request, form, formsets, change)

    # ------- Actions -------
    @admin.action(description=_("Send to review"))
    def action_submit_for_review(self, request, queryset):
        ok = 0
        with reversion.create_revision():
            for obj in queryset:
                try:
                    if not request.user.has_perm("content.submit_for_review", obj):
                        raise PermissionError(_("You are not authorized to perform this action."))
                    obj.submit_for_review(by=request.user)
                    obj.save(update_fields=["status", "submitted_for_review_at", "updated_at"])
                    ok += 1
                except Exception as e:
                    self.message_user(request, f"{obj}: {e}", messages.ERROR)
            reversion.set_user(request.user)
            reversion.set_comment("submit_for_review")
        self.message_user(request, _("%(n)d Article(s) → Review.") % {"n": ok}, messages.SUCCESS)

    @admin.action(description=_("Request changes (→ Rework)"))
    def action_request_rework(self, request, queryset):
        ok = 0
        note = request.POST.get("review_note", "")
        with reversion.create_revision():
            for obj in queryset:
                try:
                    if not request.user.has_perm("content.request_rework", obj):
                        raise PermissionError("You are not authorized to perform this action.")
                    obj.request_rework(by=request.user, note=note)
                    obj.save(update_fields=["status", "review_note", "reviewed_at", "reviewed_by", "updated_at"])
                    ok += 1
                except Exception as e:
                    self.message_user(request, f"{obj}: {e}", messages.ERROR)
            reversion.set_user(request.user)
            reversion.set_comment("request_rework")
        self.message_user(request, _("%(n)d Article(s) → Rework.") % {"n": ok}, messages.SUCCESS)

    @admin.action(description=_("Publish selected Guide(s)"))
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
                            set_last_published_revision(obj)
                            obj.save(update_fields=["last_published_revision_id"])
                            published += 1
                        except Exception as e:
                            skipped.append((obj.pk, str(e)))
                    else:
                        skipped.append((obj.pk, "Transition 'publish' not executable"))

        if published:
            self.message_user(request, _(f"{published} Item(s) published."), level=messages.SUCCESS)
        if skipped:
            detail = ", ".join([f"#{pk}: {reason}" for pk, reason in skipped])
            self.message_user(
                request,
                f"{len(skipped)} Skipped post(s): {detail}",
                level=messages.WARNING,
            )

    @admin.action(description=_("Archiving (Soft Delete)"))
    def action_archive(self, request, queryset):
        ok = 0
        note = request.POST.get("review_note", "")
        with reversion.create_revision():
            for obj in queryset:
                if not request.user.has_perm("content.archive", obj):
                    self.message_user(request, f"{obj}: You are not authorized to perform this action.",
                                      level=messages.ERROR)
                    continue
                try:
                    obj.archive(by=request.user, note=note)
                    obj.is_published = False
                    obj.save(update_fields=["status", "review_note", "is_published", "updated_at"])
                    ok += 1
                except Exception as e:
                    self.message_user(request, f"{obj}: {e}", level=messages.ERROR)
            reversion.set_user(request.user)
            reversion.set_comment("archive")
        self.message_user(request, _("%(n)d Article(s) archived.") % {"n": ok}, level=messages.SUCCESS)

    @admin.action(description=_("Restore (→ Draft)"))
    def action_restore_draft(self, request, queryset):
        ok = 0
        note = request.POST.get("review_note", "")
        with reversion.create_revision():
            for obj in queryset:
                if not request.user.has_perm("content.restore", obj):
                    self.message_user(request, f"{obj}: You are not authorized to perform this action.",
                                      level=messages.ERROR)
                    continue
                try:
                    obj.restore(by=request.user, note=note)
                    obj.is_published = False
                    obj.save(update_fields=["status", "review_note", "is_published", "updated_at"])
                    ok += 1
                except Exception as e:
                    self.message_user(request, f"{obj}: {e}", level=messages.ERROR)
            reversion.set_user(request.user)
            reversion.set_comment("restore")
        self.message_user(request, _("%(n)d Article(s) restored (draft).") % {"n": ok},
                          level=messages.SUCCESS)

    def get_urls(self):
        base_urls = super().get_urls()
        custom = [
            path("<path:object_id>/diff/", self.admin_site.admin_view(self.diff_view), name="guides_guide_diff", ),
        ]
        return custom + base_urls

    def diff_view(self, request, object_id, *args, **kwargs):
        guide = self.get_object(request, object_id)
        live_keys = set((guide.live_i18n or {}).keys()) if hasattr(guide, "live_i18n") else set()
        obj_langs = set(getattr(guide, "get_available_languages", lambda: [])())
        project_langs = {code for code, _ in getattr(settings, "LANGUAGES", [])}
        langs = []
        for code in list(project_langs) + list(obj_langs) + list(live_keys):
            if code and code not in langs:
                langs.append(code)
        if not langs:
            langs = [get_language()]

        comparisons = []
        for lang in langs:
            with switch_language(guide, lang):
                left = {
                    "slug": guide.safe_translation_getter("slug"),
                    "public_slug": guide.safe_translation_getter("public_slug"),
                    "title": guide.safe_translation_getter("title"),
                    "intro": guide.safe_translation_getter("intro"),
                    "body": guide.safe_translation_getter("body"),
                }

            live = get_live_display_instance(guide, lang)
            with switch_language(guide, lang):
                right = {
                    "slug": getattr(live, "slug", None),
                    "public_slug": getattr(live, "public_slug", None),
                    "title": getattr(live, "title", None),
                    "intro": getattr(live, "intro", None),
                    "body": getattr(live, "body", None),
                }

            guide_changes = build_field_diffs(left, right)
            section_changes = build_section_diffs(guide, lang)
            if not guide_changes and not section_changes:
                continue

            info = get_language_info(lang)
            comparisons.append({
                "code": lang,
                "name": info.get("name_local") or info.get("name") or lang,
                "changes": guide_changes,
                "section_changes": section_changes,  # << neu
            })

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "object": guide,
            "comparisons": comparisons,
        }
        return TemplateResponse(request, "admin/guides/guide_diff.html", context)

    inlines = [GuideSectionInline]


@admin.register(GuideSection)
class GuideSectionAdmin(TranslatableTinyMCEMixin):
    tinymce_fields = ("body",)
    list_display = ("title", "pk", "guide__id", "order")
    list_filter = ("guide__id", "guide")
    ordering = ("guide__id", "order")
    search_fields = ("translations__title",)
    readonly_fields = ("live_i18n",)

    inlines = [GuideItemInline]
