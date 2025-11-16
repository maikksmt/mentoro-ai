from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from prompts.models import Prompt

User = get_user_model()


class PromptAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="admin", password="pass", email="admin@example.com"
        )
        cls.p = Prompt.objects.create(
            title="AdminPub",
            slug="admin-pub",
            body="Body",
            status="published",
            published_at=timezone.now(),
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_admin_changelist_loads(self):
        url = reverse("admin:prompts_prompt_changelist")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_admin_change_page_loads(self):
        url = reverse("admin:prompts_prompt_change", args=[self.p.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
