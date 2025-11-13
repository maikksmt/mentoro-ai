from django.contrib import admin
from django.test import TestCase
from glossary.models import GlossaryTerm


class GlossaryAdminTests(TestCase):
    def test_model_registered_in_admin(self):
        Model = GlossaryTerm
        self.assertIn(
            Model,
            admin.site._registry,
            f"{Model.__name__} should be registered in Django admin.",
        )
