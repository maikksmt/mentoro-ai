from django.test import TestCase
from django.urls import reverse, NoReverseMatch
from django.utils import timezone

from catalog.models import Tool


def _index_url():
    for name in ("compare:index", "compare-home", "compare"):
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
    return None


class CompareTemplateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.t1 = Tool.objects.create(
            name="Delta Tool",
            slug="delta-tool",
            vendor="D",
            short_description="D",
            long_description="D",
            website="https://example.com/d",
            language_support=["en"],
            pricing_model="freemium",
            free_tier=True,
            monthly_price_min=0,
            rating=3.9,
            is_featured=False,
            published_at=timezone.now(),
        )
        cls.t2 = Tool.objects.create(
            name="Epsilon Tool",
            slug="epsilon-tool",
            vendor="E",
            short_description="E",
            long_description="E",
            website="https://example.com/e",
            language_support=["de"],
            pricing_model="subscription",
            free_tier=False,
            monthly_price_min=12,
            rating=4.0,
            is_featured=False,
            published_at=timezone.now(),
        )
        cls.index_url = _index_url()

    def test_index_template_used_and_headers_present(self):
        resp = self.client.get(
            reverse("compare:index"), {"ids": "delta-tool,epsilon-tool"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "compare/index.html")
        html = resp.content.decode()
        self.assertIn("No comparisons found.", html)
        self.assertIn("canonical", html)
        self.assertIn("ids=delta-tool%2Cepsilon-tool", html)
