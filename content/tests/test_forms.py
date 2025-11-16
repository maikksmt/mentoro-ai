from importlib import import_module

from django.test import SimpleTestCase


class ContentEditorialFormsTests(SimpleTestCase):
    def test_forms_import_and_basic_validation(self):
        fm = import_module("content.forms_editorial")
        from django import forms

        found_any = False
        for name in dir(fm):
            obj = getattr(fm, name)
            if (
                    isinstance(obj, type)
                    and issubclass(obj, forms.BaseForm)
                    and obj is not forms.BaseForm
            ):
                found_any = True
                form = obj(data={})  # leere Daten
                self.assertFalse(
                    form.is_valid(), msg=f"{name} should not be valid with empty data"
                )
        if not found_any:
            self.skipTest(
                "No concrete Django Form subclasses found in content.forms_editorial"
            )
