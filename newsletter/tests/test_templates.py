from django.test import TestCase
from django.urls import reverse


class TestNewsletterTemplates(TestCase):
    def test_subscribe_template_has_privacy_and_i18n_copy(self):
        r = self.client.get(reverse("newsletter:subscribe"))
        html = r.content.decode()
        markers = [
            "privacy",
            "datenschutz",
            "terms",
            "bedingungen",
            'id="newsletter-subscribe"',
            'class="newsletter-form"',
        ]
        self.assertTrue(any(m.lower() in html.lower() for m in markers))
