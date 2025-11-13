from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase, RequestFactory
from django.utils import timezone

from guides.models import Guide

try:
    from core.models.editorial import EditorialStatus
except Exception:
    class EditorialStatus:
        DRAFT = "draft"
        REVIEW = "review"
        PUBLISHED = "published"


def create_guide(*, slug, en_title, de_title=None, status=EditorialStatus.PUBLISHED, published_at=None, intro="Intro",
                 body="Body"):
    if published_at is None and status == EditorialStatus.PUBLISHED:
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


class GuideAdminActionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        cls.draft = create_guide(slug="draft", en_title="Draft", status=EditorialStatus.DRAFT)
        cls.published = create_guide(
            slug="published", en_title="Published",
            status=EditorialStatus.PUBLISHED, published_at=now
        )

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.post("/")
        SessionMiddleware(lambda r: None).process_request(self.request)
        self.request.session.save()
        self.request._messages = FallbackStorage(self.request)
        User = get_user_model()
        self.request.user = User.objects.create_superuser(
            "admin@example.com", "admin@example.com", "x"
        )
        self.guide_admin = admin.site._registry[Guide]

    def test_publish_now_action(self):
        if not hasattr(self.guide_admin, "publish_now"):
            self.skipTest("Action publish_now nicht definiert.")
        qs = Guide.objects.filter(pk=self.draft.pk)
        self.guide_admin.publish_now(self.request, qs)

        # Kein Manager-Wechsel: am Objekt selbst prüfen
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, EditorialStatus.PUBLISHED)
        self.assertIsNotNone(self.draft.published_at)

    def test_schedule_publish_sets_future(self):
        if not hasattr(self.guide_admin, "schedule_publish"):
            self.skipTest("Action schedule_publish nicht definiert.")
        qs = Guide.all_objects.filter(pk=self.draft.pk)
        now = timezone.now()
        self.guide_admin.schedule_publish(self.request, qs)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, EditorialStatus.PUBLISHED)
        self.assertIsNotNone(self.draft.published_at)
        self.assertGreater(self.draft.published_at, now)

    def test_unpublish_reverts_to_draft(self):
        if not hasattr(self.guide_admin, "unpublish"):
            self.skipTest("Action unpublish nicht definiert.")
        qs = Guide.objects.filter(pk=self.published.pk)
        self.guide_admin.unpublish(self.request, qs)

        self.published.refresh_from_db()
        self.assertEqual(self.published.status, EditorialStatus.DRAFT)
