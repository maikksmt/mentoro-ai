from django.test import TestCase
from django.utils import timezone

from guides.models import Guide
from core.models.editorial import EditorialWorkflowMixin
from core import services as core_services


def make_guide(*, title, slug, status=EditorialWorkflowMixin.STATUS_PUBLISHED, published_at=None):
    if published_at is None and status == EditorialWorkflowMixin.STATUS_PUBLISHED:
        published_at = timezone.now()
    g = Guide.objects.create(status=status, published_at=published_at)
    g.create_translation("en", slug=f"{slug}_en", title=title, intro="", body="")
    g.create_translation("de", slug=f"{slug}_de", title=title, intro="", body="")
    return g


class GuideServicesBlackBoxTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.target = make_guide(title="Target", slug="target", published_at=timezone.now())
        for i in range(12):
            make_guide(title=f"Rel #{i:02d}", slug=f"rel-{i:02d}", published_at=timezone.now())
        make_guide(title="Hidden Draft", slug="hidden-draft", status=EditorialWorkflowMixin.STATUS_DRAFT)

    def test_related_guides_black_box(self):
        qs = core_services.related_guides(self.target, limit=6)
        rel = list(qs)
        self.assertLessEqual(len(rel), 6)
        self.assertTrue(all(isinstance(g, Guide) for g in rel))
        self.assertTrue(all(g.pk != self.target.pk for g in rel))
        self.assertTrue(all(getattr(g, "status", None) == EditorialWorkflowMixin.STATUS_PUBLISHED for g in rel))
