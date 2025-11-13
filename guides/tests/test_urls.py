from django.test import SimpleTestCase
from django.urls import resolve, reverse


class GuideURLTests(SimpleTestCase):
    def test_list_url_resolves(self):
        url = reverse("guides:list")
        match = resolve(url)
        self.assertEqual(match.view_name, "guides:list")

    def test_detail_url_resolves(self):
        url = reverse("guides:detail", kwargs={"slug": "some-slug"})
        match = resolve(url)
        self.assertEqual(match.view_name, "guides:detail")
