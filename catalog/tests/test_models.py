from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from parler.utils.context import switch_language

from catalog.models import Tool, Category


class CatalogModelTests(TestCase):
    t1 = None

    @classmethod
    def setUpTestData(cls):
        cls.cat = Category.objects.create(name="Office & Tools", slug="office")
        cls.t1 = Tool.objects.create(slug="alpha", website="https://example.com/a")
        with switch_language(cls.t1, "en"):
            cls.t1.name = "Alpha"
            cls.t1.slug = "alpha"
            cls.t1.short_description = "A"
            cls.t1.long_description = "A long"
            cls.t1.save()

        with switch_language(cls.t1, "de"):
            cls.t1.name = "Alpha DE"
            cls.t1.slug = "alpha-de"
            cls.t1.short_description = "A DE"
            cls.t1.long_description = "A lang"
            cls.t1.save()

        cls.t1.categories.add(cls.cat)

    def test_str_returns_name(self):
        self.assertEqual(str(self.t1), "Alpha")

    def test_get_absolute_url_if_present(self):
        if not hasattr(self.t1, "get_absolute_url"):
            self.skipTest("Tool.get_absolute_url ist nicht implementiert.")
        url = self.t1.get_absolute_url()
        self.assertTrue(isinstance(url, str) and url)

        resp = self.client.get(url)
        self.assertIn(resp.status_code, (200, 302, 301))

    def test_slug_unique_constraint(self):
        with self.assertRaises(IntegrityError):
            Tool.objects.create(
                name="Alpha Copy",
                slug="alpha",  # duplicate
                vendor="Acme",
                short_description="copy",
                long_description="copy",
                website="https://example.com/alpha-copy",
                language_support=["de"],
                pricing_model="freemium",
                free_tier=True,
                monthly_price_min=0,
                rating=3.5,
                is_featured=False,
                published_at=timezone.now(),
            )
