from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from parler.admin import TranslatableTabularInline
from parler.forms import TranslatableModelForm
from taggit.models import Tag

from core.admin import TranslatableTinyMCEMixin
from .models import Category, Tool, PricingTier, AffiliateProgram

admin.site.site_header = "MentoroAI – Admin"


class ToolAdminForm(TranslatableModelForm):
    language_support_input = forms.CharField(
        label=_("Language support"),
        required=False,
        help_text=_("Comma-separated language codes, e.g. de,en,fr"),
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "style": "min-width:30rem;",  # Breite nach Geschmack
            }
        ),
    )

    class Meta:
        model = Tool
        exclude = ("language_support",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # bestehende Sprachen in das Textfeld schreiben
        if self.instance and self.instance.pk and self.instance.language_support:
            self.fields["language_support_input"].initial = ", ".join(
                self.instance.language_support
            )
        if "tags" in self.fields:
            w = self.fields["tags"].widget
            style = w.attrs.get("style", "")
            # Höhe + Breite anpassen – Taggit nutzt ein <input>, die Höhe kommt über CSS
            w.attrs["style"] = (style + "; min-width:50rem;").strip("; ")

    def clean_language_support_input(self):
        raw = self.cleaned_data.get("language_support_input", "")
        if not raw.strip():
            return []
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return parts

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.language_support = self.cleaned_data.get("language_support_input", [])
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class PricingTierInlineForm(TranslatableModelForm):
    # Komfort-Textarea statt JSON direkt
    features_input = forms.CharField(
        label=_("Features"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=_("One feature per line (stored as a list per language)."),
    )

    class Meta:
        model = PricingTier
        # 'features' selbst bearbeiten wir über features_input
        fields = ("name", "price_month", "price_year", "features_input")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # bestehende Features (für aktuelle Sprache) -> Zeilen
        if self.instance and self.instance.pk:
            features = self.instance.safe_translation_getter(
                "features",
                default=[],
                any_language=False,
            )
            if features:
                self.fields["features_input"].initial = "\n".join(features)

        # Name-Feld im Inline schmaler machen
        if "name" in self.fields:
            w = self.fields["name"].widget
            style = w.attrs.get("style", "")
            w.attrs["style"] = (style + "; max-width: 16rem").strip("; ")

    def clean_features_input(self):
        raw = self.cleaned_data.get("features_input", "") or ""
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        return lines

    def save(self, commit=True):
        instance = super().save(commit=False)
        # features pro Sprache speichern
        instance.features = self.cleaned_data.get("features_input", [])
        if commit:
            instance.save()
        return instance


class PricingInline(TranslatableTabularInline):
    model = PricingTier
    form = PricingTierInlineForm
    extra = 1
    fields = ("name", "price_month", "price_year", "features_input")


class AffiliateInline(admin.TabularInline):
    model = AffiliateProgram
    extra = 0
    fields = ("network", "program_url", "commission_type", "commission_value", "cookie_days", "tracking_note")


@admin.register(Tool)
class ToolAdmin(TranslatableTinyMCEMixin):
    form = ToolAdminForm
    tinymce_fields = ("short_description", "long_description")

    # Listenansicht
    list_display = (
        "name",
        "vendor",
        "pricing_model",
        "free_tier",
        "is_featured",
        "rating",
        "published_at",
        "updated_at",
    )
    list_editable = (
        "free_tier",
        "is_featured",
    )
    list_filter = (
        "is_featured",
        "free_tier",
        "pricing_model",
        "categories",
    )
    search_fields = (
        "translations__name",
        "vendor",
        "translations__short_description",
        "translations__long_description",
        "tags__name",
    )
    readonly_fields = ("created_at", "updated_at", "existing_tags_display")
    autocomplete_fields = ("categories",)

    inlines = [PricingInline, AffiliateInline]

    # Übersicht aller existierenden Tags (nur Anzeige)
    def existing_tags_display(self, obj=None):
        names = Tag.objects.order_by("name").values_list("name", flat=True)
        return ", ".join(names)

    existing_tags_display.short_description = _("Existing tags")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "slug",
                    "vendor",
                    "website",
                    "logo",
                )
            },
        ),
        (
            _("Content"),
            {
                "fields": (
                    "short_description",
                    "long_description",
                )
            },
        ),
        (
            _("Classification"),
            {
                "fields": (
                    "categories",
                    "tags",
                    "language_support_input",
                    "existing_tags_display",
                )
            },
        ),
        (
            _("Pricing & Highlight"),
            {
                "fields": (
                    "pricing_model",
                    "free_tier",
                    "rating",
                    "is_featured",
                )
            },
        ),
        (
            _("Meta"),
            {
                "fields": (
                    "published_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_prepopulated_fields(self, request, obj=None):
        # Slug pro Sprache aus name
        return {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(TranslatableTinyMCEMixin):
    list_display = ("name", "slug")
    search_fields = ("translations__name", "translations__description")
    fields = ("slug", "name", "description")

    def get_prepopulated_fields(self, request, obj=None):
        return {"slug": ("name",)}


@admin.register(AffiliateProgram)
class AffiliateProgramAdmin(admin.ModelAdmin):
    list_display = ("tool", "network", "program_url", "commission_type", "commission_value")
    search_fields = ("tool__translations__name", "network")


admin.site.register(PricingTier)
