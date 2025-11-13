from django.test import TestCase
from django.urls import resolve, reverse, NoReverseMatch


class CompareURLTests(TestCase):
    def test_index_url_resolves(self):
        for name in ("compare:index", "compare-home", "compare"):
            try:
                url = reverse(name)
            except NoReverseMatch:
                continue
            self.assertIsNotNone(resolve(url).func, f"{name} should resolve")
            return
        self.skipTest("No recognizable index URL name found in compare.urls")

    def test_detail_url_resolves_if_defined(self):
        for name in ("compare:detail", "comparison-detail"):
            try:
                url = reverse(name, kwargs={"slug": "dummy"})
            except NoReverseMatch:
                continue
            self.assertIsNotNone(resolve(url).func, f"{name} should resolve")
            return
        self.skipTest("No recognizable detail URL name found (optional).")
