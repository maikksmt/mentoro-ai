from django.test import TestCase
from django.urls import reverse, resolve
from django.utils import translation


class PromptURLTests(TestCase):
    def test_list_url_resolves(self):
        with translation.override("en"):
            url = reverse("prompts:list")
            self.assertTrue(url.startswith("/en/"))
            match = resolve(url)
            self.assertEqual(match.namespace, "prompts")
            self.assertEqual(match.url_name, "list")

    def test_detail_url_resolves(self):
        with translation.override("de"):
            url = reverse("prompts:detail", kwargs={"slug": "foo"})
            self.assertTrue(url.startswith("/de/"))
            match = resolve(url)
            self.assertEqual(match.namespace, "prompts")
            self.assertEqual(match.url_name, "detail")
            self.assertEqual(match.kwargs["slug"], "foo")
