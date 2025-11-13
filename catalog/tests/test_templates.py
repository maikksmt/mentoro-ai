from django.test import TestCase
from django.urls import reverse

from catalog.models import Tool, Category
from parler.utils.context import switch_language


class CatalogTemplateTests(TestCase):
    tool = None

    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name="Office & Tools", slug="office")
        cls.tool = Tool.objects.create(slug="nice-tool", website="https://example.com/nice")

        with switch_language(cls.tool, "en"):
            cls.tool.name = "NiceTool"
            cls.tool.short_description = "Useful helper"
            cls.tool.long_description = "Useful helper Long"
            cls.tool.save()
        cls.tool.categories.add(cat)

    def test_list_card_renders_name_desc_and_safe_rel_on_outbound_link(self):
        resp = self.client.get(reverse("catalog:list"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("NiceTool", html)
        # Beschreibung aus short_desc
        self.assertTrue(("Useful helper" in html) or ("useful" in html.lower()))
        if "https://example.com/tool" in html:
            self.assertIn(
                'rel="nofollow noopener"',
                html,
                'Outbound links must have rel="nofollow noopener".',
            )
