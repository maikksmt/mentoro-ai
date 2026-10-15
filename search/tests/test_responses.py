from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

from django.test import SimpleTestCase

from search.query import normalize_search_query
from search.responses import (
    COUNT_ORDER,
    SearchKindCount,
    SearchResponse,
    build_counts,
    empty_response,
)
from search.result_types import SearchMatchedField, SearchResult, SearchResultKind

QUERY = normalize_search_query("ai tools")


def result(kind, object_id):
    return SearchResult(
        kind=kind,
        object_id=object_id,
        title=f"{kind} {object_id}",
        summary="",
        url=f"/en/{kind}/{object_id}/",
        language_code="en",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=None,
        rank=0.5,
        matched_field=SearchMatchedField.TITLE,
    )


class SearchKindCountTests(SimpleTestCase):
    def test_is_immutable(self):
        entry = SearchKindCount(kind=SearchResultKind.TOOL, count=3)
        with self.assertRaises(FrozenInstanceError):
            entry.count = 4

    def test_uses_slots(self):
        self.assertFalse(hasattr(SearchKindCount(kind=SearchResultKind.TOOL, count=0), "__dict__"))

    def test_zero_is_valid(self):
        self.assertEqual(SearchKindCount(kind=SearchResultKind.TOOL, count=0).count, 0)

    def test_negative_count_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "count must not be negative"):
            SearchKindCount(kind=SearchResultKind.TOOL, count=-1)


class BuildCountsTests(SimpleTestCase):
    def test_every_kind_appears_once_even_at_zero(self):
        counts = build_counts(())
        self.assertEqual([entry.kind for entry in counts], list(COUNT_ORDER))
        self.assertTrue(all(entry.count == 0 for entry in counts))

    def test_counts_reflect_the_results(self):
        results = (
            result(SearchResultKind.TOOL, 1),
            result(SearchResultKind.TOOL, 2),
            result(SearchResultKind.GUIDE, 3),
        )
        counts = {entry.kind: entry.count for entry in build_counts(results)}
        self.assertEqual(counts[SearchResultKind.TOOL], 2)
        self.assertEqual(counts[SearchResultKind.GUIDE], 1)
        self.assertEqual(counts[SearchResultKind.PROMPT], 0)

    def test_order_is_stable(self):
        self.assertEqual(COUNT_ORDER, tuple(SearchResultKind))
        self.assertEqual(
            [entry.kind for entry in build_counts(())],
            [entry.kind for entry in build_counts((result(SearchResultKind.PROMPT, 1),))],
        )

    def test_returns_a_tuple(self):
        self.assertIsInstance(build_counts(()), tuple)


class SearchResponseTests(SimpleTestCase):
    def _response(self, results):
        return SearchResponse(
            query=QUERY,
            language_code="en",
            results=results,
            counts=build_counts(results),
        )

    def test_total_count_cannot_drift_from_results(self):
        results = (result(SearchResultKind.TOOL, 1), result(SearchResultKind.GUIDE, 2))
        self.assertEqual(self._response(results).total_count, 2)

    def test_counts_sum_to_total(self):
        results = tuple(
            result(kind, index) for index, kind in enumerate(SearchResultKind, start=1)
        )
        response = self._response(results)
        self.assertEqual(
            sum(entry.count for entry in response.counts), response.total_count
        )

    def test_is_empty(self):
        self.assertTrue(self._response(()).is_empty)
        self.assertFalse(self._response((result(SearchResultKind.TOOL, 1),)).is_empty)

    def test_count_for(self):
        response = self._response((result(SearchResultKind.PROMPT, 1),))
        self.assertEqual(response.count_for(SearchResultKind.PROMPT), 1)
        self.assertEqual(response.count_for(SearchResultKind.TOOL), 0)

    def test_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self._response(()).language_code = "de"

    def test_uses_slots(self):
        self.assertFalse(hasattr(self._response(()), "__dict__"))

    def test_results_and_counts_are_tuples(self):
        response = self._response((result(SearchResultKind.TOOL, 1),))
        self.assertIsInstance(response.results, tuple)
        self.assertIsInstance(response.counts, tuple)

    def test_carries_the_normalized_query(self):
        self.assertIs(self._response(()).query, QUERY)


class EmptyResponseTests(SimpleTestCase):
    def test_carries_zero_counts_for_every_kind(self):
        query = normalize_search_query("a")
        response = empty_response(query=query, language_code="de")
        self.assertEqual(response.results, ())
        self.assertEqual(response.total_count, 0)
        self.assertTrue(response.is_empty)
        self.assertEqual(len(response.counts), len(SearchResultKind))
        self.assertTrue(all(entry.count == 0 for entry in response.counts))
        self.assertEqual(response.language_code, "de")
        self.assertIs(response.query, query)
