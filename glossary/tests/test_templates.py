from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from glossary.models import GlossaryTerm


class GlossaryTemplateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        GlossaryTerm.objects.create(
            term="Durchsatz",
            slug="durchsatz",
            short_definition="Kurze Def.",
            long_definition="",
            category="Deployment",
            language="de",
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

    def test_seo_partials_if_included(self):
        url = reverse("glossary:list")
        resp = self.client.get(url, {"lang": "de"})
        html = resp.content.decode()
        self.assertIn("<meta", html)
        self.assertIn("canonical", html)
