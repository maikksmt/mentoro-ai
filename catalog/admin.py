from django.contrib import admin

from core.admin import TranslatableTinyMCEMixin
from .models import Category, Tool, PricingTier, AffiliateProgram

admin.site.site_header = "MentoroAI – Admin"


class PricingInline(admin.TabularInline):
    model = PricingTier
    extra = 1


class AffiliateInline(admin.TabularInline):
    model = AffiliateProgram
    extra = 0


@admin.register(Tool)
class ToolAdmin(TranslatableTinyMCEMixin):
    tinymce_fields = ("short_description", "long_description")
    list_display = ("name", "pk", "vendor", "pricing_model", "rating", "is_featured", "published_at")
    search_fields = ("translations__name", "vendor", "translations__short_description")
    inlines = [PricingInline, AffiliateInline]
    fields = (
        "slug",
        "vendor",
        "website",
        "free_tier",
        "pricing_model",
        "rating",
        "is_featured",
        "published_at",
        "name",
        "short_description",
        "long_description",
        "categories",
        "tags",
    )

    def get_prepopulated_fields(self, request, obj=None):
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
    list_display = ("tool", "program_url", "commission_type", "commission_value")
    search_fields = ("tool__translations__name",)


admin.site.register(PricingTier)
