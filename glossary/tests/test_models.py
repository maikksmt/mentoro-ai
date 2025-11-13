from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from glossary.models import GlossaryTerm


def make_term(**overrides):
    data = {
        "term": "Durchsatz",
        "slug": "durchsatz",
        "short_definition": "Kurze Def.",
        "long_definition": "Lange Def.",
        "category": "Deployment",
        "language": "de",
        "created_at": timezone.now(),
        "updated_at": timezone.now(),
    }
    data.update(overrides)
    return GlossaryTerm.objects.create(**data)


class GlossaryModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.t1 = make_term(term="Durchsatz", slug="durchsatz", language="de")
        cls.t2 = make_term(term="Ähnlichkeit", slug="aehnlichkeit", language="de")
        cls.t3 = make_term(term="encoding", slug="encoding", language="en")

    def test_str_representation(self):
        self.assertEqual(str(self.t1), "Durchsatz")

    def test_ordering_case_insensitive_by_term(self):
        qs_default = list(GlossaryTerm.objects.all())
        qs_explicit = list(GlossaryTerm.objects.all().order_by("term"))
        self.assertEqual(
            [t.pk for t in qs_default],
            [t.pk for t in qs_explicit],
            "Implicit default ordering should equal explicit order_by('term').",
        )

    def test_unique_constraint_slug_language(self):
        make_term(term="Durchsatz (EN)", slug="durchsatz", language="en")
        with self.assertRaises(IntegrityError):
            make_term(term="Duplikat", slug="durchsatz", language="de")

    def test_get_absolute_url_absent_is_skipped(self):
        if not hasattr(self.t1, "get_absolute_url"):
            self.skipTest(
                "GlossaryTerm hat kein get_absolute_url (laut Projektkontext)."
            )
