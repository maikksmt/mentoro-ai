from datetime import UTC, datetime, timedelta, timezone

from django.test import SimpleTestCase

from search.query import NormalizedSearchQuery, SearchQueryIssue, normalize_search_query
from search.ranking import (
    CONTENT_KIND_ORDER,
    RANK_PRECISION,
    SearchMatchTier,
    determine_match_tier,
    sort_search_results,
)
from search.result_types import SearchMatchedField, SearchResult, SearchResultKind

QUERY = normalize_search_query("ai tools")

# UTC = UTC


def build(
    *,
    title="Something entirely different",
    kind=SearchResultKind.GUIDE,
    object_id=1,
    rank=0.5,
    matched_field=SearchMatchedField.BODY,
    published_at=None,
    updated_at=None,
) -> SearchResult:
    return SearchResult(
        kind=kind,
        object_id=object_id,
        title=title,
        summary="",
        url=f"/en/{kind}/{object_id}/",
        language_code="en",
        published_at=published_at,
        updated_at=updated_at,
        rank=rank,
        matched_field=matched_field,
    )


class DetermineMatchTierTests(SimpleTestCase):
    def test_exact_title(self):
        self.assertIs(
            determine_match_tier(build(title="ai tools"), QUERY),
            SearchMatchTier.TITLE_EXACT,
        )

    def test_title_prefix(self):
        self.assertIs(
            determine_match_tier(build(title="ai tools for writers"), QUERY),
            SearchMatchTier.TITLE_PREFIX,
        )

    def test_title_contains(self):
        self.assertIs(
            determine_match_tier(
                build(title="The best ai tools of 2026"), QUERY),
            SearchMatchTier.TITLE_CONTAINS,
        )

    def test_metadata_match(self):
        self.assertIs(
            determine_match_tier(
                build(title="Unrelated", matched_field=SearchMatchedField.METADATA),
                QUERY,
            ),
            SearchMatchTier.METADATA,
        )

    def test_summary_and_body_matches_are_full_text(self):
        for matched_field in (SearchMatchedField.SUMMARY, SearchMatchedField.BODY):
            with self.subTest(matched_field=matched_field):
                self.assertIs(
                    determine_match_tier(
                        build(title="Unrelated",
                              matched_field=matched_field), QUERY
                    ),
                    SearchMatchTier.FULL_TEXT,
                )

    def test_title_hit_outranks_the_reported_matched_field(self):
        self.assertIs(
            determine_match_tier(
                build(title="ai tools", matched_field=SearchMatchedField.BODY), QUERY
            ),
            SearchMatchTier.TITLE_EXACT,
        )

    def test_comparison_is_case_insensitive(self):
        self.assertIs(
            determine_match_tier(build(title="AI TOOLS"), QUERY),
            SearchMatchTier.TITLE_EXACT,
        )

    def test_comparison_casefolds_german_sharp_s(self):
        query = normalize_search_query("STRASSE")
        self.assertIs(
            determine_match_tier(build(title="Straße"), query),
            SearchMatchTier.TITLE_EXACT,
        )

    def test_comparison_normalizes_unicode(self):
        query = normalize_search_query("find")
        self.assertIs(
            determine_match_tier(build(title="ﬁnd"), query),
            SearchMatchTier.TITLE_EXACT,
        )

    def test_comparison_collapses_whitespace(self):
        self.assertIs(
            determine_match_tier(build(title="  ai\t\ntools  "), QUERY),
            SearchMatchTier.TITLE_EXACT,
        )

    def test_unsearchable_query_is_rejected(self):
        for raw in (None, "", "a", "x" * 101):
            with self.subTest(raw=raw), self.assertRaisesMessage(ValueError, "unsearchable query"):
                determine_match_tier(build(), normalize_search_query(raw))

    def test_tier_ordering_is_ascending_by_specificity(self):
        self.assertLess(SearchMatchTier.FULL_TEXT, SearchMatchTier.METADATA)
        self.assertLess(SearchMatchTier.METADATA,
                        SearchMatchTier.TITLE_CONTAINS)
        self.assertLess(SearchMatchTier.TITLE_CONTAINS,
                        SearchMatchTier.TITLE_PREFIX)
        self.assertLess(SearchMatchTier.TITLE_PREFIX,
                        SearchMatchTier.TITLE_EXACT)


class SortPrecedenceTests(SimpleTestCase):
    def test_tier_beats_rank(self):
        exact = build(title="ai tools", rank=0.01, object_id=1)
        full_text = build(title="Unrelated", rank=0.99, object_id=2)
        self.assertEqual(
            sort_search_results([full_text, exact],
                                query=QUERY), (exact, full_text)
        )

    def test_rank_beats_recency(self):
        strong_old = build(
            rank=0.9, object_id=1, published_at=datetime(2020, 1, 1, tzinfo=UTC)
        )
        weak_new = build(
            rank=0.1, object_id=2, published_at=datetime(2026, 1, 1, tzinfo=UTC)
        )
        self.assertEqual(
            sort_search_results([weak_new, strong_old], query=QUERY),
            (strong_old, weak_new),
        )

    def test_recency_beats_kind(self):
        # PROMPT sorts last by kind, but is newer here and must win.
        newer_prompt = build(
            kind=SearchResultKind.PROMPT,
            object_id=1,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        older_tool = build(
            kind=SearchResultKind.TOOL,
            object_id=2,
            published_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        self.assertEqual(
            sort_search_results([older_tool, newer_prompt], query=QUERY),
            (newer_prompt, older_tool),
        )

    def test_kind_beats_object_id(self):
        tool = build(kind=SearchResultKind.TOOL, object_id=999)
        prompt = build(kind=SearchResultKind.PROMPT, object_id=1)
        self.assertEqual(
            sort_search_results([prompt, tool], query=QUERY), (tool, prompt)
        )

    def test_object_id_is_the_final_tie_breaker(self):
        first = build(object_id=1)
        second = build(object_id=2)
        self.assertEqual(
            sort_search_results([second, first], query=QUERY), (first, second)
        )

    def test_content_kind_order_is_the_documented_sequence(self):
        self.assertEqual(
            CONTENT_KIND_ORDER,
            (
                SearchResultKind.TOOL,
                SearchResultKind.GUIDE,
                SearchResultKind.USE_CASE,
                SearchResultKind.COMPARISON,
                SearchResultKind.PROMPT,
            ),
        )

    def test_content_kind_order_covers_every_kind(self):
        self.assertEqual(set(CONTENT_KIND_ORDER), set(SearchResultKind))


class TypeNeutralityTests(SimpleTestCase):
    def test_weak_tool_hit_does_not_displace_exact_guide_title_hit(self):
        weak_tool = build(
            kind=SearchResultKind.TOOL, title="Unrelated", rank=0.99, object_id=1
        )
        exact_guide = build(
            kind=SearchResultKind.GUIDE, title="ai tools", rank=0.02, object_id=2
        )
        self.assertEqual(
            sort_search_results([weak_tool, exact_guide], query=QUERY),
            (exact_guide, weak_tool),
        )

    def test_rank_is_compared_raw_without_per_kind_normalization(self):
        # The lone PROMPT hit is weak. If its rank were rescaled against its
        # own content type's maximum it would become 1.0 and jump to the top.
        lone_weak_prompt = build(
            kind=SearchResultKind.PROMPT, rank=0.01, object_id=1)
        strong_tool = build(kind=SearchResultKind.TOOL, rank=0.90, object_id=2)
        other_tool = build(kind=SearchResultKind.TOOL, rank=0.80, object_id=3)
        self.assertEqual(
            sort_search_results(
                [lone_weak_prompt, strong_tool, other_tool], query=QUERY
            ),
            (strong_tool, other_tool, lone_weak_prompt),
        )

    def test_no_kind_is_preferred_at_equal_relevance_except_as_tie_break(self):
        # Same tier and rank but the guide is newer: recency decides, not kind.
        tool = build(
            kind=SearchResultKind.TOOL,
            object_id=1,
            published_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        guide = build(
            kind=SearchResultKind.GUIDE,
            object_id=2,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        self.assertEqual(
            sort_search_results([tool, guide], query=QUERY), (guide, tool)
        )


class RankRoundingTests(SimpleTestCase):
    def test_ranks_within_the_precision_are_treated_as_equal(self):
        # Both round to 0.1 at 4 decimal places, so the kind tie-break decides
        # even though the prompt's raw rank is marginally higher.
        prompt = build(kind=SearchResultKind.PROMPT,
                       rank=0.100004, object_id=1)
        tool = build(kind=SearchResultKind.TOOL, rank=0.100001, object_id=2)
        self.assertEqual(
            sort_search_results([prompt, tool], query=QUERY), (tool, prompt)
        )

    def test_ranks_differing_above_the_precision_still_order_by_rank(self):
        prompt = build(kind=SearchResultKind.PROMPT, rank=0.1235, object_id=1)
        tool = build(kind=SearchResultKind.TOOL, rank=0.1234, object_id=2)
        self.assertEqual(
            sort_search_results([tool, prompt], query=QUERY), (prompt, tool)
        )

    def test_precision_is_the_documented_value(self):
        self.assertEqual(RANK_PRECISION, 4)


class RecencyTests(SimpleTestCase):
    def test_published_at_takes_precedence_over_updated_at(self):
        # The older published_at must lose despite a much newer updated_at.
        old_published = build(
            object_id=1,
            published_at=datetime(2020, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
        new_published = build(
            object_id=2,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        self.assertEqual(
            sort_search_results([old_published, new_published], query=QUERY),
            (new_published, old_published),
        )

    def test_updated_at_is_used_when_published_at_is_missing(self):
        newer = build(object_id=1, updated_at=datetime(2026, 1, 1, tzinfo=UTC))
        older = build(object_id=2, updated_at=datetime(2020, 1, 1, tzinfo=UTC))
        self.assertEqual(
            sort_search_results([older, newer], query=QUERY), (newer, older)
        )

    def test_result_without_any_date_sorts_last(self):
        dated = build(object_id=2, published_at=datetime(
            1900, 1, 1, tzinfo=UTC))
        undated = build(object_id=1)
        self.assertEqual(
            sort_search_results(
                [undated, dated], query=QUERY), (dated, undated)
        )

    def test_two_undated_results_fall_through_to_object_id(self):
        first = build(object_id=1)
        second = build(object_id=2)
        self.assertEqual(
            sort_search_results([second, first], query=QUERY), (first, second)
        )

    def test_naive_and_aware_datetimes_are_comparable(self):
        naive_newer = build(object_id=1, published_at=datetime(2026, 1, 2))
        aware_older = build(
            object_id=2, published_at=datetime(2026, 1, 1, tzinfo=UTC))
        self.assertEqual(
            sort_search_results([aware_older, naive_newer], query=QUERY),
            (naive_newer, aware_older),
        )

    def test_non_utc_aware_datetimes_are_converted(self):
        plus_two = timezone(timedelta(hours=2))
        # 09:00+02:00 is 07:00 UTC, so it is older than 08:00 UTC.
        earlier = build(
            object_id=1, published_at=datetime(2026, 1, 1, 9, 0, tzinfo=plus_two)
        )
        later = build(object_id=2, published_at=datetime(
            2026, 1, 1, 8, 0, tzinfo=UTC))
        self.assertEqual(
            sort_search_results(
                [earlier, later], query=QUERY), (later, earlier)
        )

    def test_extreme_dates_do_not_overflow(self):
        very_old = build(
            object_id=1, published_at=datetime(1, 1, 1, tzinfo=UTC))
        undated = build(object_id=2)
        self.assertEqual(len(sort_search_results(
            [very_old, undated], query=QUERY)), 2)


class DeterminismTests(SimpleTestCase):
    def _mixed_results(self):
        return [
            build(kind=SearchResultKind.TOOL, object_id=3, rank=0.5),
            build(kind=SearchResultKind.GUIDE,
                  title="ai tools", object_id=1, rank=0.1),
            build(kind=SearchResultKind.PROMPT, object_id=2, rank=0.5),
            build(
                kind=SearchResultKind.COMPARISON,
                object_id=4,
                rank=0.5,
                published_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        ]

    def test_repeated_sorting_is_identical(self):
        results = self._mixed_results()
        self.assertEqual(
            sort_search_results(results, query=QUERY),
            sort_search_results(results, query=QUERY),
        )

    def test_input_order_does_not_affect_the_outcome(self):
        results = self._mixed_results()
        forward = sort_search_results(results, query=QUERY)
        backward = sort_search_results(list(reversed(results)), query=QUERY)
        self.assertEqual(forward, backward)

    def test_every_permutation_yields_the_same_order(self):
        from itertools import permutations

        results = self._mixed_results()
        expected = sort_search_results(results, query=QUERY)
        for permutation in permutations(results):
            with self.subTest(order=[r.object_id for r in permutation]):
                self.assertEqual(sort_search_results(
                    permutation, query=QUERY), expected)


class SortApiTests(SimpleTestCase):
    def test_returns_a_tuple(self):
        self.assertIsInstance(sort_search_results(
            [build()], query=QUERY), tuple)

    def test_does_not_mutate_the_input_list(self):
        first = build(object_id=1)
        second = build(object_id=2)
        results = [second, first]
        sort_search_results(results, query=QUERY)
        self.assertEqual(results, [second, first])

    def test_accepts_a_generator(self):
        first = build(object_id=1)
        second = build(object_id=2)
        generator = (result for result in (second, first))
        self.assertEqual(
            sort_search_results(generator, query=QUERY), (first, second)
        )

    def test_empty_input_returns_an_empty_tuple(self):
        self.assertEqual(sort_search_results([], query=QUERY), ())

    def test_unsearchable_query_is_rejected(self):
        query = NormalizedSearchQuery(
            value="a", issue=SearchQueryIssue.TOO_SHORT)
        with self.assertRaisesMessage(ValueError, "unsearchable query"):
            sort_search_results([build()], query=query)
