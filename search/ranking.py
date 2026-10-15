"""
Deterministic, type-neutral ordering of search results.

Pure Python: no database, no ``timezone.now()``, no ambient state. The same
input always yields the same order, whenever it runs.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from enum import IntEnum

from search.query import NormalizedSearchQuery, normalize_text
from search.result_types import SearchMatchedField, SearchResult, SearchResultKind

#: Decimal places the database rank is rounded to before results are compared.
#: Without this, two equally relevant hits could be separated by float noise
#: and change places between runs.
RANK_PRECISION = 4

#: Final business tie-breaker, applied only when tier, rank and recency are all
#: equal. This is a stable presentation order, NOT a relevance weighting - no
#: content type is ever preferred over another on relevance grounds.
CONTENT_KIND_ORDER: tuple[SearchResultKind, ...] = (
    SearchResultKind.TOOL,
    SearchResultKind.GUIDE,
    SearchResultKind.USE_CASE,
    SearchResultKind.COMPARISON,
    SearchResultKind.PROMPT,
)

_KIND_POSITION = {kind: index for index, kind in enumerate(CONTENT_KIND_ORDER)}

# Aware UTC bounds used to order results by recency without ever calling
# datetime.min.timestamp(), which overflows on some platforms.
_OLDEST = datetime.min.replace(tzinfo=UTC)
_NEWEST = datetime.max.replace(tzinfo=UTC)


class SearchMatchTier(IntEnum):
    """How directly a result answers the query. Higher wins."""

    FULL_TEXT = 1
    METADATA = 2
    TITLE_CONTAINS = 3
    TITLE_PREFIX = 4
    TITLE_EXACT = 5


def determine_match_tier(
    result: SearchResult,
    query: NormalizedSearchQuery,
) -> SearchMatchTier:
    """
    Classifies how `result` matched `query`.

    Title comparison runs on NFKC-normalized, whitespace-collapsed, casefolded
    text, so casing and equivalent Unicode spellings cannot change the tier.
    A title hit outranks the reported ``matched_field``: an exact title match
    is an exact title match even when the adapter matched the body as well.

    Raises ValueError for an unsearchable query - ranking results for a query
    that must never have reached an adapter is a programming error, not a case
    to paper over with a default tier.
    """
    if not query.is_searchable:
        raise ValueError(
            f"cannot determine a match tier for an unsearchable query "
            f"(issue={query.issue!r})"
        )

    title = normalize_text(result.title).casefold()
    needle = normalize_text(query.value).casefold()

    if title == needle:
        return SearchMatchTier.TITLE_EXACT
    if title.startswith(needle):
        return SearchMatchTier.TITLE_PREFIX
    if needle in title:
        return SearchMatchTier.TITLE_CONTAINS
    if result.matched_field is SearchMatchedField.METADATA:
        return SearchMatchTier.METADATA
    return SearchMatchTier.FULL_TEXT


def _recency(result: SearchResult) -> datetime:
    """
    The date a result is ordered by: ``published_at``, else ``updated_at``,
    else the oldest representable moment.

    Naive datetimes are read as UTC and aware ones converted to UTC, so mixed
    inputs stay comparable instead of raising.
    """
    value = result.published_at or result.updated_at
    if value is None:
        return _OLDEST
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _sort_key(
    result: SearchResult,
    query: NormalizedSearchQuery,
) -> tuple[int, float, timedelta, int, int]:
    """
    Ascending sort key mirroring the documented precedence.

    Tier and rank are negated to sort descending; recency is expressed as the
    distance from the newest representable moment, so a smaller value means a
    more recent result and the whole key stays ascending in one pass.
    """
    return (
        -int(determine_match_tier(result, query)),
        -round(result.rank, RANK_PRECISION),
        _NEWEST - _recency(result),
        _KIND_POSITION[result.kind],
        result.object_id,
    )


def sort_search_results(
    results: Iterable[SearchResult],
    *,
    query: NormalizedSearchQuery,
) -> tuple[SearchResult, ...]:
    """
    Orders results by match tier, then database rank, then recency, then
    content kind, then object id.

    Recency and content kind are tie-breakers only: a newer weak hit never
    displaces an older strong one, and no content type outranks another on
    relevance. Returns a tuple so the ordered result cannot be mutated after
    the fact; the input is never modified and may be any iterable.
    """
    return tuple(sorted(results, key=lambda result: _sort_key(result, query)))
