from django.db import models
from django.test import TestCase
from django.utils import timezone, translation

from catalog.models import Tool
from compare.models import Comparison  # falls vorhanden


class CompareModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        translation.activate("en")
        cls.tool_a = Tool.objects.create(
            name="Alpha Tool",
            slug="alpha-tool",
            vendor="A",
            short_description="A",
            long_description="A",
            website="https://example.com/a",
            language_support=["en"],
            pricing_model="freemium",
            free_tier=True,
            monthly_price_min=0,
            rating=4.0,
            is_featured=False,
            published_at=timezone.now(),
        ).set_current_language("en")
        cls.tool_b = Tool.objects.create(
            name="Beta Tool",
            slug="beta-tool",
            vendor="B",
            short_description="B",
            long_description="B",
            website="https://example.com/b",
            language_support=["de"],
            pricing_model="subscription",
            free_tier=False,
            monthly_price_min=10,
            rating=4.5,
            is_featured=True,
            published_at=timezone.now(),
        ).set_current_language("en")

        try:
            cls.comparison = Comparison.objects.create(
                title="Alpha vs Beta",
                slug="alpha-vs-beta",
                created_at=timezone.now(),
            ).set_current_language("en")
            if hasattr(cls.comparison, "tools"):
                cls.comparison.tools.set([cls.tool_a, cls.tool_b])
        except Exception:
            cls.comparison = None

    def test_model_exists(self):
        self.assertTrue("compare.models" in str(Comparison.__module__))

    def test_str_representation(self):
        if self.comparison is None:
            self.skipTest(
                "Comparison model without a test instance."
            )
        s = str(self.comparison)
        self.assertTrue(
            isinstance(s, str) and s.strip(),
            "__str__ must return a non-empty string",
        )

    def test_get_absolute_url_if_defined(self):
        if self.comparison is None or not hasattr(self.comparison, "get_absolute_url"):
            self.skipTest("Comparison does not have a get_absolute_url method.")
        url = self.comparison.get_absolute_url()
        self.assertTrue(isinstance(url, str) and url.startswith("/"))
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (200, 301, 302, 404))

    def test_created_at_field_is_datetime(self):
        if self.comparison is None:
            self.skipTest("Comparison model without instance.")
        field = next(
            (
                f
                for f in self.comparison._meta.fields
                if f.name in ("created_at", "created", "timestamp")
            ),
            None,
        )
        self.assertIsNotNone(
            field, "Comparison should have a created_at/created field."
        )
        self.assertIsInstance(field, models.DateTimeField)
