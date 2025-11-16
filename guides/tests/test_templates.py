from django.test import TestCase
from django.urls import reverse
from django.utils import timezone, translation

from core.models.editorial import EditorialWorkflowMixin
from guides.models import Guide


def make_pub():
    g = Guide.objects.create(status=EditorialWorkflowMixin.STATUS_PUBLISHED, published_at=timezone.now())
    g.create_translation("en", slug="hello-en", title="Hello EN", intro="i", body="b")
    g.create_translation("de", slug="hello-de", title="Hallo DE", intro="i", body="b")
    return g


class GuideTemplateContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pub = make_pub()

    def test_list_template_context_and_meta(self):
        with translation.override("en"):
            url = reverse("guides:list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn("Guides", html)

    def test_detail_template_context_and_meta(self):
        with translation.override("en"):
            url = reverse("guides:detail", kwargs={"slug": self.pub.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn("Guides", html)
        self.assertIn(self.pub.safe_translation_getter("title", language_code="en"), html)
        self.assertTrue(len(html) > 0)
