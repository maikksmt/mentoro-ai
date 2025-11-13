from django.test import TestCase
from parler.utils.context import switch_language
from usecases.models import UseCase
from core.models.editorial import EditorialWorkflowMixin
from django.utils import timezone


class TestTemplates(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.uc = UseCase.objects.create(
            status=EditorialWorkflowMixin.STATUS_PUBLISHED,
            published_at=timezone.now(),
        )
        # DE
        with switch_language(cls.uc, "de"):
            cls.uc.title = "Workflow Demo"
            cls.uc.slug = "workflow-demo-de",
            cls.uc.intro = "Intro DE"
            cls.uc.save()
        # EN
        with switch_language(cls.uc, "en"):
            cls.uc.title = "Workflow Demo"
            cls.uc.slug = "workflow-demo-en",
            cls.uc.intro = "Intro EN"
            cls.uc.save()
