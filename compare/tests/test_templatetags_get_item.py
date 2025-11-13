from django.test import SimpleTestCase
from compare.templatetags.get_item import get_item


class GetItemTemplateTagTests(SimpleTestCase):
    def test_get_existing_key(self):
        data = {"a": 1, "b": "x"}
        self.assertEqual(get_item(data, "a"), 1)
        self.assertEqual(get_item(data, "b"), "x")

    def test_missing_key_returns_empty_string(self):
        data = {"a": 1}
        self.assertEqual(get_item(data, "missing"), "")
