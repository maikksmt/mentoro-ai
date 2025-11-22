from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from newsletter.models import Subscriber


class TestNewsletterViews(TestCase):
    def test_subscribe_get_displays_form(self):
        response = self.client.get(reverse("newsletter:subscribe"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_subscribe_post_triggers_double_opt_in_email(self):
        response = self.client.post(
            reverse("newsletter:subscribe"), {"email": "a@example.com"}
        )
        self.assertEqual(response.status_code, 302)
        subscriber = Subscriber.objects.get(email="a@example.com")
        self.assertFalse(subscriber.double_opt_in)
        self.assertIsNotNone(subscriber.doi_token)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(subscriber.doi_token, mail.outbox[0].body)

    def test_subscribe_existing_confirmed_user_shows_message(self):
        Subscriber.objects.create(
            email="confirmed@example.com",
            double_opt_in=True,
            confirmed_at=timezone.now(),
        )
        response = self.client.post(
            reverse("newsletter:subscribe"), {"email": "confirmed@example.com"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_confirm_view_marks_subscription_confirmed(self):
        subscriber = Subscriber.objects.create(email="pending@example.com")
        token = subscriber.refresh_doi_token()
        response = self.client.get(reverse("newsletter:confirm", args=[token]))
        self.assertEqual(response.status_code, 200)
        subscriber.refresh_from_db()
        self.assertTrue(subscriber.double_opt_in)
        self.assertIsNone(subscriber.doi_token)
