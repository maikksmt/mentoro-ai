from django.test import TestCase
from django.utils import timezone

from core.models.editorial import EditorialWorkflowMixin
from prompts.models import Prompt


def create_prompt(*, slug, en_title, de_title=None, status=EditorialWorkflowMixin.STATUS_PUBLISHED, published_at=None,
                  body_en="Body EN", body_de="Body DE"):
    if published_at is None and status == EditorialWorkflowMixin.STATUS_PUBLISHED:
        published_at = timezone.now()
    p = Prompt.objects.create(status=status, published_at=published_at)

    p.set_current_language("en")
    p.title = en_title
    p.body = body_en
    p.slug = f"{slug}_en"
    p.save()

    p.set_current_language("de")
    p.title = de_title or en_title
    p.body = body_de
    p.slug = f"{slug}_de"
    p.save()
    return p


class PromptModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.p_en_pub = create_prompt(slug="en-pub", en_title="EN Published")

    def test_str_returns_title_or_repr(self):
        self.p_en_pub.set_current_language("en")
        self.assertEqual(str(self.p_en_pub), "EN Published")

    def test_get_absolute_url_resolves(self):
        url = self.p_en_pub.get_absolute_url()
        self.assertIsInstance(url, str)
        self.assertIn("en-pub", url)
