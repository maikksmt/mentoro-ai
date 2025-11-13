# newsletter/tests/test_unsubscribe.py
from django.test import TestCase
from django.urls import reverse
from newsletter.models import Subscriber


class TestUnsubscribe(TestCase):
    def setUp(self):
        self.sub = Subscriber.objects.create(email="user@example.com", double_opt_in=True)

    def test_unsubscribe_idempotent(self):
        self.sub.mark_unsubscribed()
        r = self.client.post(reverse("newsletter:unsubscribe"), {"email": self.sub.email})
        self.assertEqual(r.status_code, 302)
