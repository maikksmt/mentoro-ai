from django.contrib import admin as django_admin
from django.db import models
from django.test import RequestFactory
from django.test import TestCase

from catalog.admin import (
    ToolAdmin,
    CategoryAdmin,
    PricingInline,
    AffiliateInline,
)
from catalog.models import Category, Tool, PricingTier, AffiliateProgram
from core.admin import TranslatableTinyMCEMixin


class CatalogAdminSmokeTests(TestCase):
    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get("/")
        self.site = django_admin.site
        # Admin-Instanzen
        self.tool_admin = ToolAdmin(Tool, self.site)
        self.category_admin = CategoryAdmin(Category, self.site)

    def test_models_registered_on_site(self):
        self.assertIn(
            Tool, self.site._registry
        )
        self.assertIn(
            Category, self.site._registry
        )

        self.assertIn(
            PricingTier, self.site._registry
        )
        self.assertIn(
            AffiliateProgram, self.site._registry
        )

    def test_tooladmin_is_configured(self):
        expected_list_display = ("name", "pk", "vendor", "pricing_model", "rating", "is_featured", "published_at")
        expected_search_fields = ("translations__name", "vendor", "translations__short_description")
        expected_prepop = {"slug": ("name",)}
        expected_inlines = (
            PricingInline,
            AffiliateInline,
        )

        self.assertTupleEqual(
            tuple(self.tool_admin.list_display), expected_list_display
        )
        self.assertTupleEqual(
            tuple(self.tool_admin.search_fields), expected_search_fields
        )
        self.assertDictEqual(self.tool_admin.get_prepopulated_fields(self.request), expected_prepop)
        self.assertEqual(tuple(self.tool_admin.inlines), expected_inlines)

    def test_tooladmin_inherits_tinymce_admin(self):
        self.assertTrue(issubclass(ToolAdmin, TranslatableTinyMCEMixin))
        overrides = getattr(self.tool_admin, "formfield_overrides", {})
        self.assertIsInstance(overrides, dict)
        self.assertIn(models.TextField, overrides)

    def test_categoryadmin_is_configured(self):
        expected = {"slug": ("name",)}
        got = self.category_admin.get_prepopulated_fields(self.request)
        self.assertDictEqual(got, expected)


class CatalogAdminInlineTests(TestCase):
    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get("/")
        self.site = django_admin.site

    def test_pricing_inline(self):
        inline = PricingInline(Tool, self.site)  # Parent ist Tool
        self.assertIs(
            inline.model, PricingTier
        )
        self.assertEqual(inline.extra, 1)

    def test_affiliate_inline(self):
        inline = AffiliateInline(Tool, self.site)
        self.assertIs(
            inline.model, AffiliateProgram
        )
        self.assertEqual(inline.extra, 0)
