"""
Beta 10.7: the global search service, exercised without a database.

Fake adapters make the service's own contract observable: what it does with an
unusable query, how it merges and orders results, and above all that a failing
adapter can never produce a partial answer. SimpleTestCase blocks database
access outright, so any accidental query here fails the test rather than
passing unnoticed.
"""
from datetime import UTC, datetime, timedelta

from django.test import SimpleTestCase

from search.exceptions import SearchExecutionError
from search.query import SearchQueryIssue
from search.responses import SearchResponse
from search.result_types import SearchMatchedField, SearchResult, SearchResultKind
from search.services import search_site

# UTC = UTC


def make_result(
    kind,
    object_id,
    *,
    title="Ai Tools",
    rank=0.5,
    language_code="en",
    url=None,
    published_at=None,
    matched_field=SearchMatchedField.TITLE,
):
    return SearchResult(
        kind=kind,
        object_id=object_id,
        title=title,
        summary="",
        url=url if url is not None else f"/en/{kind}/{object_id}/",
        language_code=language_code,
        published_at=published_at or datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=None,
        rank=rank,
        matched_field=matched_field,
    )


class FakeAdapter:
    """Records its calls and returns whatever it was configured with."""

    def __init__(self, kind, results=(), raises=None):
        self.kind = kind
        self._results = results
        self._raises = raises
        self.calls = []

    def search(self, *, query, language_code):
        self.calls.append((query, language_code))
        if self._raises is not None:
            raise self._raises
        return self._results


def adapters_for(**by_kind):
    """One fake adapter per kind, in registry order."""
    return tuple(
        FakeAdapter(kind, by_kind.get(kind.name.lower(), ()))
        for kind in SearchResultKind
    )


class InvalidQueryTests(SimpleTestCase):
    """An unusable query short-circuits before anything else happens."""

    def test_empty_query_returns_an_empty_response(self):
        adapters = adapters_for()
        response = search_site(
            raw_query="", language_code="en", adapters=adapters)
        self.assertIsInstance(response, SearchResponse)
        self.assertEqual(response.results, ())
        self.assertEqual(response.total_count, 0)
        self.assertIs(response.query.issue, SearchQueryIssue.EMPTY)

    def test_none_single_character_and_overlong_queries(self):
        for raw, issue in (
            (None, SearchQueryIssue.EMPTY),
            ("   ", SearchQueryIssue.EMPTY),
            ("a", SearchQueryIssue.TOO_SHORT),
            ("x" * 101, SearchQueryIssue.TOO_LONG),
        ):
            with self.subTest(raw=raw):
                response = search_site(
                    raw_query=raw, language_code="en", adapters=adapters_for()
                )
                self.assertIs(response.query.issue, issue)
                self.assertTrue(response.is_empty)

    def test_no_adapter_is_called(self):
        adapters = adapters_for()
        search_site(raw_query="a", language_code="en", adapters=adapters)
        for adapter in adapters:
            with self.subTest(kind=adapter.kind):
                self.assertEqual(adapter.calls, [])

    def test_all_counts_are_zero(self):
        response = search_site(
            raw_query="", language_code="en", adapters=adapters_for())
        self.assertEqual(len(response.counts), len(SearchResultKind))
        self.assertTrue(all(entry.count == 0 for entry in response.counts))

    def test_unusable_query_short_circuits_before_the_language_check(self):
        # Documented ordering: the query verdict does not depend on anything
        # else being right, so an unsupported language still yields the empty
        # response rather than an exception.
        response = search_site(
            raw_query="a", language_code="fr", adapters=adapters_for()
        )
        self.assertTrue(response.is_empty)
        self.assertEqual(response.language_code, "fr")


class LanguageTests(SimpleTestCase):
    def test_unsupported_language_fails_closed_for_a_searchable_query(self):
        from search.fts import UnsupportedSearchLanguage

        adapters = adapters_for()
        with self.assertRaises(UnsupportedSearchLanguage):
            search_site(raw_query="ai tools",
                        language_code="fr", adapters=adapters)
        for adapter in adapters:
            self.assertEqual(adapter.calls, [])

    def test_language_is_passed_to_every_adapter(self):
        adapters = adapters_for()
        search_site(raw_query="ai tools",
                    language_code="de", adapters=adapters)
        for adapter in adapters:
            with self.subTest(kind=adapter.kind):
                self.assertEqual([call[1] for call in adapter.calls], ["de"])


class MergeAndSortTests(SimpleTestCase):
    def test_every_adapter_is_called_exactly_once(self):
        adapters = adapters_for()
        search_site(raw_query="ai tools",
                    language_code="en", adapters=adapters)
        for adapter in adapters:
            with self.subTest(kind=adapter.kind):
                self.assertEqual(len(adapter.calls), 1)

    def test_results_from_all_adapters_are_merged(self):
        adapters = adapters_for(
            tool=(make_result(SearchResultKind.TOOL, 1),),
            guide=(make_result(SearchResultKind.GUIDE, 2),),
            prompt=(make_result(SearchResultKind.PROMPT, 3),),
        )
        response = search_site(
            raw_query="ai tools", language_code="en", adapters=adapters
        )
        self.assertEqual(response.total_count, 3)

    def test_results_are_sorted_globally_not_per_adapter(self):
        # The prompt adapter runs last but its result ranks highest, so a
        # per-adapter merge would put it at the end.
        adapters = adapters_for(
            tool=(make_result(SearchResultKind.TOOL, 1, title="Unrelated", rank=0.1,
                              matched_field=SearchMatchedField.BODY),),
            prompt=(make_result(SearchResultKind.PROMPT,
                    2, title="Ai Tools", rank=0.9),),
        )
        response = search_site(
            raw_query="ai tools", language_code="en", adapters=adapters
        )
        self.assertEqual(
            [(r.kind, r.object_id) for r in response.results],
            [(SearchResultKind.PROMPT, 2), (SearchResultKind.TOOL, 1)],
        )

    def test_adapter_order_does_not_influence_the_result_order(self):
        def build():
            return adapters_for(
                tool=(make_result(SearchResultKind.TOOL, 1),),
                guide=(make_result(SearchResultKind.GUIDE, 2),),
                prompt=(make_result(SearchResultKind.PROMPT, 3),),
                usecase=(make_result(SearchResultKind.USE_CASE, 4),),
                comparison=(make_result(SearchResultKind.COMPARISON, 5),),
            )

        forward = search_site(
            raw_query="ai tools", language_code="en", adapters=build()
        )
        reverse = search_site(
            raw_query="ai tools", language_code="en", adapters=tuple(reversed(build()))
        )
        rotated = search_site(
            raw_query="ai tools", language_code="en", adapters=build()[2:] + build()[:2]
        )
        expected = [(r.kind, r.object_id) for r in forward.results]
        self.assertEqual([(r.kind, r.object_id)
                         for r in reverse.results], expected)
        self.assertEqual([(r.kind, r.object_id)
                         for r in rotated.results], expected)
        self.assertEqual(reverse.counts, forward.counts)
        self.assertEqual(rotated.counts, forward.counts)

    def test_no_type_blocks_or_round_robin(self):
        # Two tools rank above one guide; they must stay adjacent rather than
        # being interleaved for variety.
        adapters = adapters_for(
            tool=(
                make_result(SearchResultKind.TOOL, 1, rank=0.9),
                make_result(SearchResultKind.TOOL, 2, rank=0.8),
            ),
            guide=(make_result(SearchResultKind.GUIDE, 3, rank=0.1),),
        )
        response = search_site(
            raw_query="ai tools", language_code="en", adapters=adapters
        )
        self.assertEqual(
            [r.kind for r in response.results],
            [SearchResultKind.TOOL, SearchResultKind.TOOL, SearchResultKind.GUIDE],
        )

    def test_repeated_calls_are_deterministic(self):
        first = search_site(
            raw_query="ai tools",
            language_code="en",
            adapters=adapters_for(
                tool=(make_result(SearchResultKind.TOOL, 1),)),
        )
        second = search_site(
            raw_query="ai tools",
            language_code="en",
            adapters=adapters_for(
                tool=(make_result(SearchResultKind.TOOL, 1),)),
        )
        self.assertEqual(first.results, second.results)


class CountTests(SimpleTestCase):
    def test_counts_match_the_results_exactly(self):
        adapters = adapters_for(
            tool=(
                make_result(SearchResultKind.TOOL, 1),
                make_result(SearchResultKind.TOOL, 2),
            ),
            guide=(make_result(SearchResultKind.GUIDE, 3),),
        )
        response = search_site(
            raw_query="ai tools", language_code="en", adapters=adapters
        )
        self.assertEqual(response.total_count, 3)
        self.assertEqual(response.count_for(SearchResultKind.TOOL), 2)
        self.assertEqual(response.count_for(SearchResultKind.GUIDE), 1)
        self.assertEqual(response.count_for(SearchResultKind.PROMPT), 0)
        self.assertEqual(
            sum(entry.count for entry in response.counts), response.total_count
        )

    def test_no_matches_yields_zero_counts_for_every_kind(self):
        response = search_site(
            raw_query="ai tools", language_code="en", adapters=adapters_for()
        )
        self.assertTrue(response.is_empty)
        self.assertEqual(len(response.counts), len(SearchResultKind))
        self.assertTrue(all(entry.count == 0 for entry in response.counts))


class FailClosedTests(SimpleTestCase):
    def _adapters_failing_at(self, failing_index, exception):
        adapters = []
        for index, kind in enumerate(SearchResultKind):
            if index == failing_index:
                adapters.append(FakeAdapter(kind, raises=exception))
            else:
                adapters.append(FakeAdapter(
                    kind, (make_result(kind, index + 1),)))
        return tuple(adapters)

    def test_failure_in_the_first_adapter_stops_everything(self):
        adapters = self._adapters_failing_at(0, RuntimeError("boom"))
        with self.assertRaises(SearchExecutionError):
            search_site(raw_query="ai tools",
                        language_code="en", adapters=adapters)
        for adapter in adapters[1:]:
            with self.subTest(kind=adapter.kind):
                self.assertEqual(adapter.calls, [])

    def test_failure_after_successful_adapters_discards_their_results(self):
        adapters = self._adapters_failing_at(2, RuntimeError("boom"))
        with self.assertRaises(SearchExecutionError) as caught:
            search_site(raw_query="ai tools",
                        language_code="en", adapters=adapters)
        # Nothing partial escaped: the exception carries no results at all.
        self.assertFalse(hasattr(caught.exception, "results"))
        self.assertEqual(len(adapters[0].calls), 1)
        self.assertEqual(len(adapters[1].calls), 1)
        self.assertEqual(adapters[3].calls, [])
        self.assertEqual(adapters[4].calls, [])

    def test_error_names_the_failing_content_type(self):
        adapters = self._adapters_failing_at(1, RuntimeError("boom"))
        with self.assertRaises(SearchExecutionError) as caught:
            search_site(raw_query="ai tools",
                        language_code="en", adapters=adapters)
        self.assertIs(caught.exception.kind, SearchResultKind.GUIDE)
        self.assertIn("guide", str(caught.exception))

    def test_original_exception_is_chained(self):
        original = RuntimeError("database exploded")
        adapters = self._adapters_failing_at(0, original)
        with self.assertRaises(SearchExecutionError) as caught:
            search_site(raw_query="ai tools",
                        language_code="en", adapters=adapters)
        self.assertIs(caught.exception.__cause__, original)

    def test_database_detail_stays_out_of_the_message(self):
        adapters = self._adapters_failing_at(
            0, RuntimeError("SELECT * FROM secret"))
        with self.assertRaises(SearchExecutionError) as caught:
            search_site(raw_query="ai tools",
                        language_code="en", adapters=adapters)
        self.assertNotIn("SELECT", str(caught.exception))

    def test_keyboard_interrupt_is_not_captured(self):
        adapters = self._adapters_failing_at(0, KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            search_site(raw_query="ai tools",
                        language_code="en", adapters=adapters)

    def test_system_exit_is_not_captured(self):
        adapters = self._adapters_failing_at(0, SystemExit())
        with self.assertRaises(SystemExit):
            search_site(raw_query="ai tools",
                        language_code="en", adapters=adapters)


class ContractViolationTests(SimpleTestCase):
    def _run(self, adapter):
        others = tuple(
            FakeAdapter(kind) for kind in SearchResultKind if kind is not adapter.kind
        )
        return search_site(
            raw_query="ai tools", language_code="en", adapters=(adapter,) + others
        )

    def _assert_rejected(self, adapter, fragment):
        with self.assertRaises(SearchExecutionError) as caught:
            self._run(adapter)
        self.assertIs(caught.exception.kind, adapter.kind)
        self.assertIn(fragment, str(caught.exception))

    def test_list_instead_of_tuple_is_rejected(self):
        adapter = FakeAdapter(
            SearchResultKind.TOOL, [make_result(SearchResultKind.TOOL, 1)]
        )
        self._assert_rejected(adapter, "expected a tuple")

    def test_non_search_result_element_is_rejected(self):
        adapter = FakeAdapter(SearchResultKind.TOOL,
                              ({"title": "not a result"},))
        self._assert_rejected(adapter, "expected SearchResult")

    def test_wrong_kind_is_rejected(self):
        adapter = FakeAdapter(
            SearchResultKind.TOOL, (make_result(SearchResultKind.GUIDE, 1),)
        )
        self._assert_rejected(adapter, "guide result")

    def test_wrong_language_is_rejected(self):
        adapter = FakeAdapter(
            SearchResultKind.TOOL,
            (make_result(SearchResultKind.TOOL, 1, language_code="de"),),
        )
        self._assert_rejected(adapter, "expected 'en'")

    def test_external_url_is_rejected(self):
        for url in ("https://example.test/x", "http://example.test/x"):
            with self.subTest(url=url):
                adapter = FakeAdapter(
                    SearchResultKind.TOOL, (make_result(
                        SearchResultKind.TOOL, 1, url=url),)
                )
                self._assert_rejected(adapter, "non-internal url")

    def test_protocol_relative_url_is_rejected(self):
        adapter = FakeAdapter(
            SearchResultKind.TOOL,
            (make_result(SearchResultKind.TOOL, 1, url="//example.test/x"),),
        )
        self._assert_rejected(adapter, "non-internal url")

    def test_placeholder_url_is_rejected(self):
        adapter = FakeAdapter(
            SearchResultKind.TOOL, (make_result(
                SearchResultKind.TOOL, 1, url="#"),)
        )
        self._assert_rejected(adapter, "non-internal url")

    def test_relative_url_without_leading_slash_is_rejected(self):
        adapter = FakeAdapter(
            SearchResultKind.TOOL,
            (make_result(SearchResultKind.TOOL, 1, url="catalog/x/"),),
        )
        self._assert_rejected(adapter, "non-internal url")

    def test_duplicate_object_within_one_adapter_is_rejected(self):
        adapter = FakeAdapter(
            SearchResultKind.TOOL,
            (
                make_result(SearchResultKind.TOOL, 1),
                make_result(SearchResultKind.TOOL, 1),
            ),
        )
        self._assert_rejected(adapter, "duplicate")

    def test_same_object_id_across_kinds_is_allowed(self):
        adapters = adapters_for(
            tool=(make_result(SearchResultKind.TOOL, 7),),
            guide=(make_result(SearchResultKind.GUIDE, 7),),
        )
        response = search_site(
            raw_query="ai tools", language_code="en", adapters=adapters
        )
        self.assertEqual(response.total_count, 2)

    def test_a_violation_yields_no_partial_response(self):
        broken = FakeAdapter(
            SearchResultKind.PROMPT, [make_result(SearchResultKind.PROMPT, 1)]
        )
        adapters = (
            FakeAdapter(SearchResultKind.TOOL,
                        (make_result(SearchResultKind.TOOL, 1),)),
            FakeAdapter(SearchResultKind.GUIDE,
                        (make_result(SearchResultKind.GUIDE, 2),)),
            broken,
            FakeAdapter(SearchResultKind.USE_CASE),
            FakeAdapter(SearchResultKind.COMPARISON),
        )
        with self.assertRaises(SearchExecutionError):
            search_site(raw_query="ai tools",
                        language_code="en", adapters=adapters)
        self.assertEqual(adapters[3].calls, [])
        self.assertEqual(adapters[4].calls, [])


class ResponseShapeTests(SimpleTestCase):
    def test_response_carries_no_model_instances(self):
        adapters = adapters_for(tool=(make_result(SearchResultKind.TOOL, 1),))
        response = search_site(
            raw_query="ai tools", language_code="en", adapters=adapters
        )
        for result in response.results:
            self.assertIsInstance(result, SearchResult)
            self.assertFalse(hasattr(result, "_meta"))

    def test_response_is_immutable(self):
        from dataclasses import FrozenInstanceError

        response = search_site(
            raw_query="ai tools", language_code="en", adapters=adapters_for()
        )
        with self.assertRaises(FrozenInstanceError):
            response.results = ()

    def test_recency_only_breaks_ties(self):
        older_strong = make_result(
            SearchResultKind.TOOL,
            1,
            title="Unrelated",
            rank=0.9,
            matched_field=SearchMatchedField.BODY,
            published_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        newer_weak = make_result(
            SearchResultKind.GUIDE,
            2,
            title="Unrelated",
            rank=0.1,
            matched_field=SearchMatchedField.BODY,
            published_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=1),
        )
        response = search_site(
            raw_query="ai tools",
            language_code="en",
            adapters=adapters_for(tool=(older_strong,), guide=(newer_weak,)),
        )
        self.assertEqual(
            [r.object_id for r in response.results], [
                1, 2], "rank must beat recency"
        )
