from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from newsletter.models import Subscriber


class TestNewsletterAdmin(TestCase):
    def test_registered(self):
        self.assertTrue(admin.site.is_registered(Subscriber))

    def test_changelist_accessible(self):
        User = get_user_model()
        su = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pw"
        )
        self.client.force_login(su)
        url = reverse("admin:newsletter_subscriber_changelist")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
