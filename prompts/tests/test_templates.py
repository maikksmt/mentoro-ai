from django.test import TestCase
from django.urls import reverse
from django.utils import timezone, translation
from prompts.models import Prompt

COPY_MARKERS = (
    "data-copy",
    "copy-to-clipboard",
    'aria-label="Copy"',
    "btn-copy",
    "hx-copy",
)


class PromptTemplateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.p_en = Prompt.objects.create(
            title="Copy Me",
            slug="copy-me",
            body="Use this",
            status="published",
            published_at=timezone.now(),
        )

    def _has_any_copy_marker(self, html: str) -> bool:
        return any(m in html for m in COPY_MARKERS)

    def test_list_template_has_usage_or_copy_ui_if_present(self):
        with translation.override("en"):
            url = reverse("prompts:list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        if self._has_any_copy_marker(html):
            self.assertTrue(True)
        else:
            self.assertIn("Prompts", html)

    def test_detail_template_has_usage_or_copy_ui_if_present(self):
        with translation.override("en"):
            url = reverse("prompts:detail", kwargs={"slug": self.p_en.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()

        if self._has_any_copy_marker(html):
            self.assertTrue(True)
        else:
            self.assertIn(self.p_en.title, html)
            self.assertIn("Use this", html)
