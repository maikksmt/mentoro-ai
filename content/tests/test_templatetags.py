from django.test import SimpleTestCase
from compare.templatetags.get_item import get_item
from django.template import Template, Context
from django.test import TestCase


class TestTemplateTagsCore(TestCase):
    def render(self, tpl, ctx=None):
        return Template(tpl).render(Context(ctx or {}))

    def test_richtext_safe_render(self):
        tpl = '{% load richtext %}{{ "<b>x</b>"|richtext }}'
        out = self.render(tpl)
        self.assertIn("<b>x</b>", out)


class TestTemplateTagGetItem(SimpleTestCase):
    def test_dict_and_missing(self):
        d = {"a": 1, "b": 0}
        self.assertEqual(get_item(d, "a"), 1)
        self.assertEqual(get_item(d, "b"), 0)
        self.assertEqual(get_item(d, "x"), "")
