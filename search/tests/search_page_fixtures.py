"""Shared helpers for the search page tests."""
from __future__ import annotations

from datetime import UTC, datetime

from search.query import NormalizedSearchQuery, SearchQueryIssue
from search.responses import SearchResponse, build_counts
from search.result_types import SearchMatchedField, SearchResult, SearchResultKind

# UTC = UTC


def make_result(kind, object_id, *, title=None, summary="A short summary.", url=None):
    return SearchResult(
        kind=kind,
        object_id=object_id,
        title=title or f"{kind} result {object_id}",
        summary=summary,
        url=url or f"/en/{kind}/{object_id}/",
        language_code="en",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=None,
        rank=0.5,
        matched_field=SearchMatchedField.TITLE,
    )


def make_response(*, value="ai tools", issue=None, results=(), language_code="en"):
    ordered = tuple(results)
    return SearchResponse(
        query=NormalizedSearchQuery(value=value, issue=issue),
        language_code=language_code,
        results=ordered,
        counts=build_counts(ordered),
    )


def empty_query_response(issue: SearchQueryIssue, value: str = ""):
    return make_response(value=value, issue=issue)


def mixed_results():
    """Deliberately not in registry order, to prove the page does not re-sort."""
    return (
        make_result(SearchResultKind.PROMPT, 1),
        make_result(SearchResultKind.TOOL, 2),
        make_result(SearchResultKind.COMPARISON, 3),
        make_result(SearchResultKind.GUIDE, 4),
        make_result(SearchResultKind.USE_CASE, 5),
    )
