from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models.editorial import EditorialWorkflowMixin
from guides.models import Guide


def create_guide(*, slug, en_title, de_title=None,
                 status=EditorialWorkflowMixin.STATUS_PUBLISHED, published_at=None):
    if published_at is None and status == EditorialWorkflowMixin.STATUS_PUBLISHED:
        published_at = timezone.now()
    g = Guide.objects.create(status=status, published_at=published_at)
    g.create_translation("en", slug=f"{slug}-en", title=en_title, intro="i", body="b")
    g.create_translation("de", slug=f"{slug}-de", title=de_title or en_title, intro="i", body="b")
    return g


class GuideListViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pub = create_guide(slug="visible", en_title="Visible")
        cls.pub2 = create_guide(
            slug="another", en_title="Another",
            published_at=timezone.now() - timezone.timedelta(minutes=1)
        )
        cls.draft = create_guide(slug="hidden-draft", en_title="Hidden Draft",
                                 status=EditorialWorkflowMixin.STATUS_DRAFT)

    def _list(self):
        url = reverse("guides:list")
        return self.client.get(url)

    def _detail(self, slug):
        url = reverse("guides:detail", kwargs={"slug": slug})
        return self.client.get(url)

    def test_list_only_published_and_ordering(self):
        resp = self._list()
        self.assertEqual(resp.status_code, 200)
        objs = list(resp.context["object_list"])
        self.assertTrue(all(o.status == EditorialWorkflowMixin.STATUS_PUBLISHED for o in objs))
        if len(objs) >= 2:
            self.assertGreaterEqual(objs[0].published_at, objs[1].published_at)

    def test_pagination_is_stable(self):
        for i in range(22):
            create_guide(slug=f"more-{i}", en_title=f"More {i}",
                         published_at=timezone.now() - timezone.timedelta(minutes=i))
        resp = self._list()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("paginator", resp.context)
        self.assertEqual(resp.context["paginator"].per_page, 20)

    def test_detail_i18n_and_canonical(self):
        resp = self._detail(self.pub.slug)
        html = resp.content.decode("utf-8")
        self.assertEqual(resp.status_code, 200)
        self.assertIn('<link rel="canonical"', html)
        self.assertIn(self.pub.slug, html)
        if 'rel="alternate"' in html:
            self.assertIn('hreflang="en"', html)
            self.assertIn('hreflang="de"', html)
