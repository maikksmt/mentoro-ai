from django.test import TestCase

from newsletter.models import Subscriber


class TestNewsletterForms(TestCase):
    def test_model_has_fields(self):
        fields = {f.name for f in Subscriber._meta.get_fields()}
        self.assertIn("email", fields)
        for fname in ("status", "doi_token", "doi_confirmed_at", "created_at"):
            if fname in fields:
                self.assertIn(fname, fields)
