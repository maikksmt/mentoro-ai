from django.test import TestCase
from django.urls import reverse, resolve


class GlossaryURLSmokeTests(TestCase):
    def test_list_url_resolves(self):
        url = reverse("glossary:list")
        match = resolve(url)
        self.assertEqual(match.view_name, "glossary:list")

    def test_detail_url_resolves(self):
        url = reverse("glossary:detail", kwargs={"slug": "durchsatz"})
        match = resolve(url)
        self.assertEqual(match.view_name, "glossary:detail")
