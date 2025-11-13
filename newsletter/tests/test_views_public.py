from django.test import TestCase
from django.urls import reverse
from newsletter.models import Subscriber


class TestNewsletterViews(TestCase):
    def test_get_subscribe_200_and_form_present(self):
        url = reverse("newsletter:subscribe")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertTrue(("<form" in html) and ('name="email"' in html))

    def test_post_valid_creates_or_idempotent(self):
        url = reverse("newsletter:subscribe")
        payload = {"email": "user@example.com"}
        r1 = self.client.post(url, data=payload, follow=True)
        self.assertIn(r1.status_code, (200, 302))
        self.assertEqual(Subscriber.objects.filter(email=payload["email"]).count(), 1)
        r2 = self.client.post(url, data=payload, follow=True)
        self.assertIn(r2.status_code, (200, 302))
        self.assertEqual(Subscriber.objects.filter(email=payload["email"]).count(), 1)

    def test_post_invalid_shows_form_error(self):
        url = reverse("newsletter:subscribe")
        r = self.client.post(url, data={"email": "not-an-email"}, follow=True)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertTrue("error" in html.lower() or "invalid" in html.lower())
