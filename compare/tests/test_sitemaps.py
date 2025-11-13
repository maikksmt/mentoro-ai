from django.test import TestCase

CANDIDATES = [
    ("compare.sitemaps", "CompareSitemap"),
    ("compare.sitemaps", "ComparisonSitemap"),
    ("compare.sitemaps", "CompareIndexSitemap"),
]


class CompareSitemapTests(TestCase):
    def _import_sitemap(self):
        for mod_name, cls_name in CANDIDATES:
            try:
                mod = __import__(mod_name, fromlist=[cls_name])
            except Exception:
                continue
            if hasattr(mod, cls_name):
                return getattr(mod, cls_name)
        self.skipTest("No recognizable sitemap class found in compare.sitemaps")

    def test_items_iterable_and_non_erroring(self):
        SiteMap = self._import_sitemap()
        sm = SiteMap()
        items = list(sm.items())
        self.assertIsInstance(items, list)
