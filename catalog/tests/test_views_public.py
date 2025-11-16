from django.test import TestCase
from django.urls import reverse
from parler.utils.context import switch_language

from catalog.models import Tool, Category


class CatalogPublicViewsTests(TestCase):
    t_b = None
    t_a = None

    @classmethod
    def setUpTestData(cls):
        cls.cat_ai = Category.objects.create(
            name="Automatisierung", slug="automatisierung"
        )
        cls.cat_office = Category.objects.create(name="Office & Tools", slug="office")
        cls.t_a = Tool.objects.create(slug="alpha-tool", website="https://example.com/a")
        with switch_language(cls.t_a, "en"):
            cls.t_a.name = "Alpha Tool"
            cls.t_a.short_description = "SA"
            cls.t_a.long_description = "LA"
            cls.t_a.free_tier = True
            cls.t_a.save()

        cls.t_b = Tool.objects.create(slug="beta-tool", website="https://example.com/b")
        with switch_language(cls.t_b, "en"):
            cls.t_b.name = "Beta Tool"
            cls.t_b.short_description = "SB"
            cls.t_b.long_description = "LB"
            cls.t_b.save()
        cls.t_a.categories.add(cls.cat_ai)
        cls.t_b.categories.add(cls.cat_office)

        cls.list_url = reverse("catalog:list")

    def test_list_view_status_template_context(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)
        # korrektes Template
        used = [t.name for t in resp.templates if t.name]
        self.assertTrue(any(t.endswith("catalog/tool_list.html") for t in used), used)
        # Standard-Kontext laut View
        for key in (
                "page_obj",
                "object_list",
        ):
            self.assertIn(key, resp.context)

    def test_detail_view_200_for_existing_slug(self):
        resp = self.client.get(
            reverse("catalog:detail", kwargs={"slug": "alpha-tool"})
        )
        self.assertEqual(resp.status_code, 200)
        used = [t.name for t in resp.templates if t.name]
        self.assertTrue(any(t.endswith("catalog/tool_detail.html") for t in used), used)
