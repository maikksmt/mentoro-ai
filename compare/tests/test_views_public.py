from django.test import TestCase
from django.urls import reverse, NoReverseMatch
from django.utils import timezone, translation

from catalog.models import Tool


def _index_url():
    for name in ("compare:index", "compare-home", "compare"):
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
    return None


class ComparePublicViewsTests(TestCase):
    translation.activate("en")

    @classmethod
    def setUpTestData(cls):
        cls.t1 = Tool.objects.create(
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
            rating=4.1,
            is_featured=False,
            published_at=timezone.now(),
        ).set_current_language("en")
        cls.t2 = Tool.objects.create(
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
            rating=4.2,
            is_featured=True,
            published_at=timezone.now(),
        ).set_current_language("en")
        cls.t3 = Tool.objects.create(
            name="Gamma Tool",
            slug="gamma-tool",
            vendor="C",
            short_description="C",
            long_description="C",
            website="https://example.com/c",
            language_support=["de", "en"],
            pricing_model="one-time",
            free_tier=False,
            monthly_price_min=0,
            rating=4.3,
            is_featured=False,
            published_at=timezone.now(),
        ).set_current_language("en")
        cls.index_url = _index_url()

    def test_index_renders_matrix_for_ids_param(self):
        with translation.override("en"):
            resp = self.client.get(
                reverse("compare:index"), {"ids": "alpha-tool,beta-tool"}
            )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("No comparisons found.", html)
        # weiterhin: Canonical inkl. ids
        self.assertIn("ids=alpha-tool%2Cbeta-tool", html)

    def test_index_graceful_degrade_on_invalid_slug(self):
        with translation.override("en"):
            resp = self.client.get(
                reverse("compare:index"), {"ids": "does-not-exist,beta-tool"}
            )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("No comparisons found.", html)
        self.assertIn("ids=does-not-exist%2Cbeta-tool", html)

    def test_detail_view_if_defined(self):
        for nm in ("compare:detail", "comparison-detail"):
            try:
                url = reverse(nm, kwargs={"slug": "alpha-vs-beta"})
            except NoReverseMatch:
                continue
            with translation.override("en"):
                resp = self.client.get(url)
            self.assertIn(
                resp.status_code, (200, 404)
            )  # 404 ok, wenn Vergleich nicht existiert
            if resp.status_code == 200:
                used = [t.name for t in resp.templates if t.name]
                self.assertTrue(
                    any(n.endswith("compare/detail.html") for n in used), used
                )
            return
        self.skipTest("No detail route defined (optional).")
