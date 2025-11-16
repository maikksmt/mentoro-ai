from django.test import TestCase
from parler.utils.context import switch_language

from catalog.models import Tool
from core.sitemaps import ToolSitemap


class CatalogSitemapTests(TestCase):
    p2 = None
    p1 = None

    @classmethod
    def setUpTestData(cls):
        cls.p1 = Tool.objects.create(slug="one", website="https://example.com/1")
        with switch_language(cls.p1, "en"):
            cls.p1.name = "Visible One"
            cls.p1.short_description = "S1"
            cls.p1.long_description = "L1"
            cls.p1.save()

        cls.p2 = Tool.objects.create(slug="two", website="https://example2.com/1")
        with switch_language(cls.p2, "en"):
            cls.p2.name = "Visible Two"
            cls.p2.short_description = "S2"
            cls.p2.long_description = "L2"
            cls.p2.save()

    def test_items_include_tools(self):
        sm = ToolSitemap()
        items = list(sm.items())
        names = [t.name for t in items]
        self.assertIn("Visible One", names)
        self.assertIn("Visible Two", names)
