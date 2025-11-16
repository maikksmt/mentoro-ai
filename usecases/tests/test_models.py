# usecases/tests/test_models.py
from django.test import TestCase
from django.utils import timezone

from core.models.editorial import EditorialWorkflowMixin
from usecases.models import UseCase


class TestModels(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.uc_pub = UseCase.objects.create(
            status=EditorialWorkflowMixin.STATUS_PUBLISHED,
            published_at=timezone.now(),
        )
        cls.uc_pub.set_current_language("en")
        cls.uc_pub.title = "EN Title"
        cls.uc_pub.slug = "uc-pub-en",
        if hasattr(cls.uc_pub, "intro"):
            cls.uc_pub.intro = "Intro EN"
        if hasattr(cls.uc_pub, "body"):
            cls.uc_pub.body = "Body EN"
        cls.uc_pub.save()

        cls.uc_pub.set_current_language("de")
        cls.uc_pub.title = "DE Title"
        cls.uc_pub.slug = "uc-pub-de",
        if hasattr(cls.uc_pub, "intro"):
            cls.uc_pub.intro = "Intro DE"
        if hasattr(cls.uc_pub, "body"):
            cls.uc_pub.body = "Body DE"
        cls.uc_pub.save()

    def test_str(self):
        self.uc_pub.set_current_language("en")
        self.assertEqual(str(self.uc_pub), "EN Title")
