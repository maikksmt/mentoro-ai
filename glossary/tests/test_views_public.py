from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from glossary.models import GlossaryTerm


def make_term(term, slug, lang):
    return GlossaryTerm.objects.create(
        term=term,
        slug=slug,
        short_definition=f"Kurz: {term}",
        long_definition=f"Lang: {term}",
        category="Allgemein",
        language=lang,
        created_at=timezone.now(),
        updated_at=timezone.now(),
    )


class GlossaryPublicViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.de_durchsatz = make_term("Durchsatz", "durchsatz", "de")
        cls.de_aehnlichkeit = make_term("Ähnlichkeit", "aehnlichkeit", "de")
        cls.en_throughput = make_term("Throughput", "throughput", "en")

    def test_list_view_status_template_context(self):
        resp = self.client.get(reverse("glossary:list"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("terms", resp.context)
        self.assertIn("paginator", resp.context)
        self.assertIn("page_obj", resp.context)
        # Template-Namen überprüfen
        names = [t.name for t in getattr(resp, "templates", []) if t.name]
        self.assertTrue(any(n.endswith("glossary_list.html") for n in names), names)
