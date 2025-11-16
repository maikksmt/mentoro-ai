from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from taggit.models import Tag

from core.models.editorial import EditorialWorkflowMixin
from prompts.models import Prompt


def create_prompt(*, slug, en_title, de_title=None,
                  status=EditorialWorkflowMixin.STATUS_PUBLISHED, published_at=None):
    if published_at is None and status == EditorialWorkflowMixin.STATUS_PUBLISHED:
        published_at = timezone.now()
    p = Prompt.objects.create(slug=slug, status=status, published_at=published_at)
    p.set_current_language("en")
    p.title = en_title
    p.body = "Body EN"
    p.save()
    p.set_current_language("de")
    p.title = de_title or en_title
    p.body = "Body DE"
    p.save()
    return p


class PromptPublicViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tag_ai = Tag.objects.create(name="ai")
        cls.p_en_pub = create_prompt(slug="hello-en", en_title="Hello EN")

    def test_list_page_200(self):
        url = reverse("prompts:list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
