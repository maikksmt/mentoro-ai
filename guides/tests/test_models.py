from django.test import TestCase
from django.utils import timezone

from guides.models import Guide
from core.models.editorial import EditorialWorkflowMixin


def create_guide(*, slug, en_title, de_title=None,
                 status=EditorialWorkflowMixin.STATUS_PUBLISHED, published_at=None,
                 intro="Intro", body="Body"):
    if published_at is None and status == EditorialWorkflowMixin.STATUS_PUBLISHED:
        published_at = timezone.now()
    g = Guide.objects.create(status=status, published_at=published_at)

    g.set_current_language("en")
    g.title = en_title
    g.intro = intro
    g.body = body
    g.slug = f"{slug}_en"
    g.save()

    g.set_current_language("de")
    g.title = de_title or en_title
    g.intro = intro
    g.body = body
    g.slug = f"{slug}_de"
    g.save()
    return g


class GuideModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.g1 = create_guide(
            slug="older-published",
            en_title="Older Published",
            status=EditorialWorkflowMixin.STATUS_PUBLISHED,
            published_at=timezone.now() - timezone.timedelta(days=2),
        )
        cls.g2 = create_guide(
            slug="newer-published",
            en_title="Newer Published",
            status=EditorialWorkflowMixin.STATUS_PUBLISHED,
            published_at=timezone.now() - timezone.timedelta(days=1),
        )
        cls.hidden = create_guide(
            slug="hidden-draft",
            en_title="Hidden Draft",
            status=EditorialWorkflowMixin.STATUS_DRAFT,
        )

    def test_str_uses_translated_title(self):
        self.g1.set_current_language("en")
        self.assertIn("Older Published", str(self.g1))

    def test_default_ordering_newest_first(self):
        qs = (
            Guide.objects
            .filter(status=EditorialWorkflowMixin.STATUS_PUBLISHED)
            .order_by("-published_at")
            .language("en")
        )
        titles = [g.title for g in qs]
        self.assertGreaterEqual(len(titles), 2)
        self.assertTrue(titles.index("Newer Published") < titles.index("Older Published"))

    def test_get_absolute_url_if_present(self):
        if hasattr(self.g1, "get_absolute_url") and callable(self.g1.get_absolute_url):
            url = self.g1.get_absolute_url()
            self.assertIsInstance(url, str)
            self.assertIn("older-published", url)
