from django.contrib import admin
from django.utils import timezone
from tinymce.widgets import TinyMCE
from parler.admin import TranslatableAdmin
from django.utils.translation import gettext_lazy as _


class TranslatableTinyMCEMixin(TranslatableAdmin):
    """
    Admin mixin for Parler models: swaps specified translation fields to TinyMCE,
    and loads wide-field CSS for better authoring UX.
    """
    tinymce_fields: tuple[str, ...] = ()

    class Media:
        css = {
            'all': ('admin/custom/wide-fields.css',)
        }

    def get_form(self, request, obj=None, **kwargs):
        """
        Wraps the standard admin form and injects TinyMCE widgets for configured fields;
        also widens common title fields to improve readability.
        """
        form = super().get_form(request, obj, **kwargs)
        for name in self.tinymce_fields:
            if name in form.base_fields:
                form.base_fields[name].widget = TinyMCE(attrs={"rows": 18})
        if 'title' in form.base_fields:
            w = form.base_fields['title'].widget
            style = w.attrs.get('style', '')
            w.attrs['style'] = (style + '; width:60em').strip('; ')
            css_classes = w.attrs.get('class', '')
            if 'vTextField' not in css_classes.split():
                w.attrs['class'] = (css_classes + ' vTextField').strip()
        if 'slug' in form.base_fields:
            w = form.base_fields['slug'].widget
            style = w.attrs.get('style', '')
            w.attrs['style'] = (style + '; width:60em').strip('; ')
            css_classes = w.attrs.get('class', '')
            if 'vTextField' not in css_classes.split():
                w.attrs['class'] = (css_classes + ' vTextField').strip()

        return form


class TranslatableTinyMCEInlineMixin:
    """
    Inline admin counterpart that applies TinyMCE to translation fields inside inlines
    to keep the editing experience consistent.
    """
    tinymce_fields: tuple[str, ...] = ()
    wide_text_inputs: tuple[str, ...] = ("title",)

    class Media:
        css = {
            'all': ('admin/custom/wide-fields.css',)
        }

    def get_formset(self, request, obj=None, **kwargs):
        """
        Overrides formset creation to attach TinyMCE widgets for inline translation fields.
        """
        formset = super().get_formset(request, obj, **kwargs)
        base_fields = formset.form.base_fields

        for name in self.tinymce_fields:
            if name in base_fields:
                base_fields[name].widget = TinyMCE(attrs={"rows": 14})

        # Gezielt Breite erhöhen (z. B. für title)
        for name in self.wide_text_inputs:
            if name in base_fields:
                w = base_fields[name].widget
                attrs = getattr(w, "attrs", {})
                attrs.update({"style": "min-width:40rem"})  # oder 60rem
                w.attrs = attrs

        return formset


class PublishableAdmin(TranslatableTinyMCEMixin):
    """
    Base admin for content with a status and timestamps;
    provides slug prepopulation and bulk actions for draft/publish to speed up editorial ops.
    """
    list_display = ("title", "status", "published_at", "updated_at", "author")
    list_filter = ("status", "author", "published_at", "updated_at")
    search_fields = ("title", "slug", "excerpt")
    actions = ("make_published", "make_draft")
    readonly_fields = ("published_at", "updated_at")

    def get_prepopulated_fields(self, request, obj=None):
        return {"slug": ("title",)}

    @admin.action(description=_("Mark as published"))
    def make_published(self, request, queryset):
        updated = queryset.update(status="published", published_at=timezone.now())
        self.message_user(request, _(f"{updated} Article(s) published."))

    @admin.action(description=_("Mark as Draft"))
    def make_draft(self, request, queryset):
        updated = queryset.update(status="draft")
        self.message_user(request, _(f"{updated} Article(s) marked as draft"))
