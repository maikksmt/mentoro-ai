from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

from django.test import SimpleTestCase

from search.result_types import SearchMatchedField, SearchResult, SearchResultKind

VALID = {
    "kind": SearchResultKind.GUIDE,
    "object_id": 1,
    "title": "Getting started with AI",
    "summary": "A short plain-text teaser.",
    "url": "/en/guides/getting-started/",
    "language_code": "en",
    "published_at": datetime(2026, 1, 1, tzinfo=UTC),
    "updated_at": datetime(2026, 2, 1, tzinfo=UTC),
    "rank": 0.42,
    "matched_field": SearchMatchedField.TITLE,
}


def build(**overrides) -> SearchResult:
    return SearchResult(**{**VALID, **overrides})


class SearchResultConstructionTests(SimpleTestCase):
    def test_full_instantiation(self):
        result = build()
        self.assertIs(result.kind, SearchResultKind.GUIDE)
        self.assertEqual(result.object_id, 1)
        self.assertEqual(result.rank, 0.42)
        self.assertIs(result.matched_field, SearchMatchedField.TITLE)

    def test_supports_template_style_attribute_access(self):
        result = build()
        for attribute in (
            "kind",
            "object_id",
            "title",
            "summary",
            "url",
            "language_code",
            "published_at",
            "updated_at",
            "rank",
            "matched_field",
        ):
            with self.subTest(attribute=attribute):
                self.assertTrue(hasattr(result, attribute))

    def test_dates_are_optional(self):
        result = build(published_at=None, updated_at=None)
        self.assertIsNone(result.published_at)
        self.assertIsNone(result.updated_at)

    def test_summary_may_be_empty(self):
        self.assertEqual(build(summary="").summary, "")

    def test_is_immutable(self):
        result = build()
        with self.assertRaises(FrozenInstanceError):
            result.title = "changed"

    def test_uses_slots(self):
        self.assertFalse(hasattr(build(), "__dict__"))


class SearchResultValidationTests(SimpleTestCase):
    def test_rank_zero_is_valid(self):
        self.assertEqual(build(rank=0.0).rank, 0.0)

    def test_negative_rank_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "rank must not be negative"):
            build(rank=-0.1)

    def test_nan_rank_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "rank must be a finite number"):
            build(rank=float("nan"))

    def test_infinite_rank_is_rejected(self):
        for rank in (float("inf"), float("-inf")):
            with self.subTest(rank=rank), self.assertRaises(ValueError):
                build(rank=rank)

    def test_non_positive_object_id_is_rejected(self):
        for object_id in (0, -1):
            with self.subTest(object_id=object_id), self.assertRaisesMessage(ValueError, "object_id must be positive"):
                build(object_id=object_id)

    def test_blank_title_is_rejected(self):
        for title in ("", "   "):
            with self.subTest(title=title), self.assertRaisesMessage(ValueError, "title must not be empty"):
                build(title=title)

    def test_blank_url_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "url must not be empty"):
            build(url="  ")

    def test_blank_language_code_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "language_code must not be empty"):
            build(language_code="")

    def test_language_code_is_not_restricted_to_project_languages(self):
        # The contract must not need editing when a language is added.
        for language_code in ("fr", "pt-br", "zh-hans"):
            with self.subTest(language_code=language_code):
                self.assertEqual(build(language_code=language_code).language_code, language_code)


class SearchResultKindTests(SimpleTestCase):
    def test_values_match_the_project_kind_strings(self):
        self.assertEqual(SearchResultKind.TOOL, "tool")
        self.assertEqual(SearchResultKind.GUIDE, "guide")
        self.assertEqual(SearchResultKind.PROMPT, "prompt")
        self.assertEqual(SearchResultKind.USE_CASE, "usecase")
        self.assertEqual(SearchResultKind.COMPARISON, "comparison")

    def test_covers_exactly_the_five_searchable_types(self):
        self.assertEqual(len(SearchResultKind), 5)

    def test_is_usable_as_a_plain_string(self):
        self.assertEqual(f"btn-{SearchResultKind.TOOL}", "btn-tool")


class SearchMatchedFieldTests(SimpleTestCase):
    def test_values_are_stable_strings(self):
        self.assertEqual(SearchMatchedField.TITLE, "title")
        self.assertEqual(SearchMatchedField.SUMMARY, "summary")
        self.assertEqual(SearchMatchedField.BODY, "body")
        self.assertEqual(SearchMatchedField.METADATA, "metadata")

    def test_has_no_app_specific_members(self):
        self.assertEqual(len(SearchMatchedField), 4)
