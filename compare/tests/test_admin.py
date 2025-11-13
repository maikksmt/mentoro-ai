from django.test import TestCase


class CompareAdminTests(TestCase):
    def test_all_compare_models_are_registered(self):
        from django.contrib import admin
        from compare.models import Comparison
        self.assertIn(Comparison, admin.site._registry)
