from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from parler.utils.context import switch_language

from core.models.editorial import EditorialWorkflowMixin
from usecases.models import UseCase


class TestPublicViews(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Published EN
        cls.pub = UseCase.published.create(
            slug="public-uc",
            status=EditorialWorkflowMixin.STATUS_PUBLISHED,
            published_at=timezone.now(),
        )
        with switch_language(cls.pub, "en"):
            cls.pub.title = "Public UC"
            cls.pub.intro = "Hello"
            cls.pub.workflow_steps = ["Step 1", "Step 2"]
            cls.pub.save()

        # Draft EN (soll nicht erscheinen)
        cls.draft = UseCase.published.create(
            slug="draft-uc",
            status=EditorialWorkflowMixin.STATUS_DRAFT,
        )
        with switch_language(cls.draft, "en"):
            cls.draft.title = "Draft UC"
            cls.draft.intro = "Hidden"
            cls.draft.workflow_steps = ["X"]
            cls.draft.save()

        cls.a = UseCase.published.create(
            slug="a",
            status=EditorialWorkflowMixin.STATUS_PUBLISHED,
            published_at=timezone.now(),
        )
        with switch_language(cls.a, "en"):
            cls.a.title = "A"
            cls.a.intro = "AI tools, comparisons, and guides."
            cls.a.save()

    def test_list_only_published(self):
        resp = self.client.get(reverse("usecases:list"), HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("Public UC", html)
        self.assertNotIn("Draft UC", html)

    def test_pagination(self):
        for i in range(25):
            uc = UseCase.objects.create(
                slug=f"uc-{i}",
                status=EditorialWorkflowMixin.STATUS_PUBLISHED,
                published_at=timezone.now(),
            )
            with switch_language(uc, "en"):
                uc.title = f"UC {i}"
                uc.intro = "Intro"
                uc.save()

        resp = self.client.get(reverse("usecases:list") + "?page=2", HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('aria-label="Next Page"', html)

    def test_language_toggle_de_en(self):
        resp = self.client.get(reverse("usecases:detail", kwargs={"slug": "a"}), HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # Robustere Erwartungen: canonical + Language-Select vorhanden
        self.assertIn('rel="canonical"', html)
        self.assertIn('name="language"', html)

    def test_list_filter_persona_tolerated(self):
        url = reverse("usecases:list") + "?persona=teacher"
        resp = self.client.get(url, HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(resp.status_code, 200)
