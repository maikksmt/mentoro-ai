from django.contrib import admin
from django.contrib.admin import ModelAdmin

from .models import GlossaryTerm


@admin.register(GlossaryTerm)
class GlossaryTermAdmin(ModelAdmin):
    list_display = ("term", "pk", "category", "language", "updated_at", "translation_group")
    list_filter = ("language", "category")
    search_fields = ("term", "short_definition", "long_definition")
    prepopulated_fields = {"slug": ("term",)}
    readonly_fields = ("created_at", "updated_at",)
