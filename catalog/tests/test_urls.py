from django.test import TestCase
from django.urls import resolve, reverse


class CatalogURLTests(TestCase):
    def test_list_url_resolves(self):
        url = reverse("catalog:list")
        match = resolve(url)
        self.assertIsNotNone(match.func)

    def test_detail_url_resolves(self):
        url = reverse("catalog:detail", kwargs={"slug": "x"})
        match = resolve(url)
        self.assertIsNotNone(match.func)
