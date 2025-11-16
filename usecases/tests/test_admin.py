from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from usecases.models import UseCase


class TestAdmin(TestCase):
    def test_registered(self):
        self.assertTrue(admin.site.is_registered(UseCase))

    def test_changelist_for_superuser(self):
        User = get_user_model()
        su = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pw"
        )
        self.client.force_login(su)
        url = reverse("admin:usecases_usecase_changelist")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
