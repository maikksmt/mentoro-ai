"""
Beta 11.11B2B1: pure, read-only review-binding primitives.

Everything in ``core/review_binding.py`` is a function of its arguments (or,
for :func:`revision_contains_object`, of one targeted read query) with no
side effects. These tests hold it to that: canonical fingerprints, real
``reversion.Revision``/``reversion.Version`` rows, and a full before/after
comparison proving nothing was written anywhere.

Beta 11.11B2B1A hardened :func:`revision_contains_object` itself: it used to
resolve the ``ContentType`` via the private ``reversion.revisions.
_get_content_type`` helper, which in turn calls ``ContentType.objects.
get_for_model()`` - a process-global-cache-backed lookup that costs an extra
``django_content_type`` query on a cold cache. The
``RevisionContainsObjectColdContentTypeCacheTests``,
``RevisionContainsObjectCacheIndependenceTests``,
``RevisionContainsObjectProxyModelTests`` and ``NoPrivateReversionApiTests``
classes below pin the replacement: a single query joined against
``django_content_type`` through the public ``content_type__app_label``/
``content_type__model`` filter fields, independent of cache state.
"""
import math
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import reversion
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import DEFAULT_DB_ALIAS, connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from reversion.models import Revision, Version

import core.review_binding as review_binding_module
from catalog.models import Tool
from compare.models import Comparison
from core.models.editorial import EditorialWorkflowMixin as Workflow
from core.review_binding import (
    BindingFailureReason,
    BindingValidationResult,
    ReviewFingerprintErrorCode,
    ReviewPayloadFingerprintError,
    _is_valid_sha256_hexdigest,
    fingerprint_review_payload,
    has_provable_live_snapshot,
    revision_contains_object,
    target_status_after_review_invalidation,
    validate_approved_binding,
    validate_review_binding,
)
from guides.models import Guide
from prompts.models import Prompt
from usecases.models import UseCase

User = get_user_model()

EDITORIAL_TYPES = (Guide, Prompt, UseCase, Comparison)


class GuideProxy(Guide):
    """
    Test-local proxy model for the ``for_concrete_model=True`` contract: a
    proxy instance's reversion ``Version`` is written under the *concrete*
    model's content type (Beta 11.11B1's active registration), so
    :func:`revision_contains_object` must resolve a ``GuideProxy`` instance
    the same way it resolves a plain ``Guide`` - via
    ``obj._meta.concrete_model``, not ``type(obj)``.
    """

    class Meta:
        proxy = True
        app_label = "guides"


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def create_with_revision(model, **kwargs):
    """Creates ``model(**kwargs)`` inside a real ``reversion.create_revision()``
    block, producing a genuine root Version (and, per the Beta 11.11B1
    manifest, any already-existing followed children - there are none yet at
    creation time)."""
    with reversion.create_revision():
        obj = model.objects.create(**kwargs)
    return obj


def revision_containing_only(obj):
    """
    A Revision whose only Version is ``obj``'s own, via the public
    ``reversion.add_to_revision()`` - which adds exactly the given object and,
    unlike a plain ``.save()``, does not walk that object's ``follow`` graph.

    Used to build the "child/translation version present, but not the root"
    negative case for a *translation* object without ever creating a Version
    for its parent.
    """
    with reversion.create_revision():
        reversion.add_to_revision(obj)
    return Revision.objects.latest("pk")


def version_query_count(ctx: CaptureQueriesContext) -> int:
    table = Version._meta.db_table
    return sum(1 for q in ctx.captured_queries if table in q["sql"])


# ======================================================================
# 1. Fingerprint: stability
# ======================================================================


class FingerprintStabilityTests(TestCase):
    def test_dict_insertion_order_does_not_affect_the_digest(self):
        a = fingerprint_review_payload({"title": "T", "body": "B", "slug": "s"})
        b = fingerprint_review_payload({"slug": "s", "body": "B", "title": "T"})
        self.assertEqual(a, b)

    def test_nested_dict_order_does_not_affect_the_digest(self):
        a = fingerprint_review_payload({"en": {"title": "T", "body": "B"}, "de": {"title": "X"}})
        b = fingerprint_review_payload({"de": {"title": "X"}, "en": {"body": "B", "title": "T"}})
        self.assertEqual(a, b)

    def test_identical_payload_is_deterministic(self):
        payload = {"a": [1, 2, {"b": "c"}], "d": None}
        self.assertEqual(fingerprint_review_payload(payload), fingerprint_review_payload(payload))

    def test_digest_is_exactly_64_lowercase_hex_characters(self):
        digest = fingerprint_review_payload({"a": 1})
        self.assertEqual(len(digest), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in digest))

    def test_empty_payload_shapes_are_stable(self):
        self.assertEqual(fingerprint_review_payload({}), fingerprint_review_payload({}))
        self.assertEqual(fingerprint_review_payload([]), fingerprint_review_payload([]))


# ======================================================================
# 1. Fingerprint: sensitivity
# ======================================================================


class FingerprintSensitivityTests(TestCase):
    def test_changed_string_value_changes_the_digest(self):
        self.assertNotEqual(
            fingerprint_review_payload({"title": "A"}),
            fingerprint_review_payload({"title": "B"}),
        )

    def test_list_order_changes_the_digest(self):
        self.assertNotEqual(
            fingerprint_review_payload({"items": [1, 2, 3]}),
            fingerprint_review_payload({"items": [3, 2, 1]}),
        )

    def test_int_value_and_string_value_differ(self):
        """The value ``1`` and the value ``"1"`` - not colliding dict keys,
        which Python would silently merge before this function ever runs."""
        self.assertNotEqual(
            fingerprint_review_payload({"count": 1}),
            fingerprint_review_payload({"count": "1"}),
        )

    def test_bool_value_and_equal_int_value_differ(self):
        """``True == 1`` in Python, but JSON has no such collapse: ``true`` and
        ``1`` are different tokens."""
        self.assertNotEqual(
            fingerprint_review_payload({"flag": True}),
            fingerprint_review_payload({"flag": 1}),
        )

    def test_empty_dict_and_empty_list_differ(self):
        self.assertNotEqual(
            fingerprint_review_payload({"entries": {}}),
            fingerprint_review_payload({"entries": []}),
        )

    def test_missing_key_and_explicit_none_differ(self):
        self.assertNotEqual(
            fingerprint_review_payload({}),
            fingerprint_review_payload({"title": None}),
        )

    def test_unicode_change_changes_the_digest(self):
        self.assertNotEqual(
            fingerprint_review_payload({"title": "café"}),
            fingerprint_review_payload({"title": "cafe"}),
        )

    def test_trailing_whitespace_is_significant(self):
        self.assertNotEqual(
            fingerprint_review_payload({"title": "Title"}),
            fingerprint_review_payload({"title": "Title "}),
        )

    def test_unicode_is_hashed_losslessly_not_as_escape_sequences(self):
        """Two different non-ASCII strings that would both survive an
        ensure_ascii=True round trip must still produce different digests -
        proving the function does not collapse them via escaping."""
        self.assertNotEqual(
            fingerprint_review_payload({"title": "日本語"}),
            fingerprint_review_payload({"title": "中文"}),
        )


# ======================================================================
# 1. Fingerprint: invalid payloads
# ======================================================================


class FingerprintInvalidPayloadTests(TestCase):
    def _assert_rejected(self, payload, code):
        with self.assertRaises(ReviewPayloadFingerprintError) as ctx:
            fingerprint_review_payload(payload)
        self.assertEqual(ctx.exception.code, code)

    def test_set_is_rejected(self):
        self._assert_rejected({"a": {1, 2}}, ReviewFingerprintErrorCode.UNSUPPORTED_TYPE)

    def test_bytes_is_rejected(self):
        self._assert_rejected({"a": b"raw"}, ReviewFingerprintErrorCode.UNSUPPORTED_TYPE)

    def test_datetime_is_rejected(self):
        self._assert_rejected(
            {"a": datetime(2026, 1, 1, tzinfo=UTC)},
            ReviewFingerprintErrorCode.UNSUPPORTED_TYPE,
        )

    def test_decimal_is_rejected(self):
        self._assert_rejected({"a": Decimal("1.5")}, ReviewFingerprintErrorCode.UNSUPPORTED_TYPE)

    def test_uuid_is_rejected(self):
        self._assert_rejected({"a": uuid4()}, ReviewFingerprintErrorCode.UNSUPPORTED_TYPE)

    def test_model_instance_is_rejected(self):
        tool = Tool.objects.create(slug="b2b1-tool")
        self._assert_rejected({"a": tool}, ReviewFingerprintErrorCode.UNSUPPORTED_TYPE)

    def test_queryset_is_rejected(self):
        self._assert_rejected({"a": Tool.objects.all()}, ReviewFingerprintErrorCode.UNSUPPORTED_TYPE)

    def test_custom_object_is_rejected(self):
        class Custom:
            pass

        self._assert_rejected({"a": Custom()}, ReviewFingerprintErrorCode.UNSUPPORTED_TYPE)

    def test_nan_is_rejected(self):
        self._assert_rejected({"a": math.nan}, ReviewFingerprintErrorCode.NON_FINITE_FLOAT)

    def test_infinity_is_rejected(self):
        self._assert_rejected({"a": math.inf}, ReviewFingerprintErrorCode.NON_FINITE_FLOAT)
        self._assert_rejected({"a": -math.inf}, ReviewFingerprintErrorCode.NON_FINITE_FLOAT)

    def test_non_string_dict_key_is_rejected(self):
        self._assert_rejected({1: "a"}, ReviewFingerprintErrorCode.NON_STRING_DICT_KEY)

    def test_non_string_dict_key_is_rejected_when_nested(self):
        self._assert_rejected({"en": {2: "a"}}, ReviewFingerprintErrorCode.NON_STRING_DICT_KEY)

    def test_rejection_raises_before_any_database_access(self):
        with self.assertNumQueries(0), self.assertRaises(ReviewPayloadFingerprintError):
            fingerprint_review_payload({"a": {1, 2}})

    def test_error_is_a_value_error_with_a_stable_code_not_just_a_message(self):
        try:
            fingerprint_review_payload({"a": b"x"})
        except ReviewPayloadFingerprintError as exc:
            self.assertIsInstance(exc, ValueError)
            self.assertIsInstance(exc.code, ReviewFingerprintErrorCode)
        else:
            self.fail("expected ReviewPayloadFingerprintError")


# ======================================================================
# Fingerprint syntax helper
# ======================================================================


class Sha256HexdigestSyntaxTests(TestCase):
    def test_a_real_sha256_digest_is_valid(self):
        self.assertTrue(_is_valid_sha256_hexdigest(fingerprint_review_payload({"a": 1})))

    def test_64_lowercase_hex_characters_are_valid(self):
        self.assertTrue(_is_valid_sha256_hexdigest("a" * 64))
        self.assertTrue(_is_valid_sha256_hexdigest("0123456789abcdef" * 4))

    def test_empty_string_is_invalid(self):
        self.assertFalse(_is_valid_sha256_hexdigest(""))

    def test_none_is_invalid(self):
        self.assertFalse(_is_valid_sha256_hexdigest(None))

    def test_63_characters_is_invalid(self):
        self.assertFalse(_is_valid_sha256_hexdigest("a" * 63))

    def test_65_characters_is_invalid(self):
        self.assertFalse(_is_valid_sha256_hexdigest("a" * 65))

    def test_uppercase_is_invalid(self):
        self.assertFalse(_is_valid_sha256_hexdigest("A" * 64))

    def test_mixed_case_is_invalid(self):
        self.assertFalse(_is_valid_sha256_hexdigest("aA" * 32))

    def test_leading_whitespace_is_invalid(self):
        self.assertFalse(_is_valid_sha256_hexdigest(" " + "a" * 63))

    def test_trailing_whitespace_is_invalid(self):
        self.assertFalse(_is_valid_sha256_hexdigest("a" * 63 + " "))

    def test_0x_prefix_is_invalid(self):
        self.assertFalse(_is_valid_sha256_hexdigest("0x" + "a" * 62))

    def test_hyphens_are_invalid(self):
        self.assertFalse(_is_valid_sha256_hexdigest("a" * 8 + "-" + "a" * 55))

    def test_a_uuid_is_invalid(self):
        self.assertFalse(_is_valid_sha256_hexdigest(str(uuid4())))

    def test_non_string_is_invalid(self):
        self.assertFalse(_is_valid_sha256_hexdigest(12345))
        self.assertFalse(_is_valid_sha256_hexdigest(b"a" * 64))


# ======================================================================
# 2. Revision <-> root-object membership
# ======================================================================


class RevisionContainsObjectPositiveTests(TestCase):
    def test_revision_containing_the_guide_root_version_is_recognised(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(version__object_id=str(guide.pk))
        self.assertTrue(revision_contains_object(revision, guide))

    def test_revision_containing_the_prompt_root_version_is_recognised(self):
        prompt = create_with_revision(Prompt)
        revision = Revision.objects.get(version__object_id=str(prompt.pk))
        self.assertTrue(revision_contains_object(revision, prompt))

    def test_revision_containing_the_usecase_root_version_is_recognised(self):
        usecase = create_with_revision(UseCase)
        revision = Revision.objects.get(version__object_id=str(usecase.pk))
        self.assertTrue(revision_contains_object(revision, usecase))

    def test_revision_containing_the_comparison_root_version_is_recognised(self):
        comparison = create_with_revision(Comparison)
        revision = Revision.objects.get(version__object_id=str(comparison.pk))
        self.assertTrue(revision_contains_object(revision, comparison))

    def test_explicit_using_matching_the_real_alias_still_matches(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(version__object_id=str(guide.pk))
        self.assertTrue(revision_contains_object(revision, guide, using=DEFAULT_DB_ALIAS))


class RevisionContainsObjectNegativeTests(TestCase):
    def test_none_revision_is_false(self):
        guide = create_with_revision(Guide)
        self.assertFalse(revision_contains_object(None, guide))

    def test_none_object_is_false(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(version__object_id=str(guide.pk))
        self.assertFalse(revision_contains_object(revision, None))

    def test_unsaved_object_is_false(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(version__object_id=str(guide.pk))
        self.assertFalse(revision_contains_object(revision, Guide()))

    def test_revision_of_a_different_object_of_the_same_model_is_false(self):
        guide_a = create_with_revision(Guide)
        guide_b = create_with_revision(Guide)
        revision_for_b = Revision.objects.get(version__object_id=str(guide_b.pk))
        self.assertFalse(revision_contains_object(revision_for_b, guide_a))

    def test_revision_of_a_different_editorial_type_with_the_same_numeric_pk_is_false(self):
        guide = create_with_revision(Guide)
        revision_for_guide = Revision.objects.get(
            version__object_id=str(guide.pk), version__content_type__model="guide"
        )
        prompt = create_with_revision(Prompt)
        # Force the prompt onto the guide's numeric pk - object_id alone would
        # now collide between the two rows, so this only stays correct if
        # revision_contains_object also compares content_type.
        Prompt.objects.filter(pk=prompt.pk).update(id=guide.pk)
        prompt = Prompt.objects.get(pk=guide.pk)

        self.assertFalse(revision_contains_object(revision_for_guide, prompt))

    def test_revision_containing_only_a_translation_version_is_not_the_root(self):
        guide = Guide.objects.create()
        guide.create_translation("en", title="T", intro="i", body="b", slug="b2b1-only-child")
        translation = guide.translations.get(language_code="en")
        revision = revision_containing_only(translation)
        self.assertFalse(revision_contains_object(revision, guide))

    def test_wrong_database_alias_is_false(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(version__object_id=str(guide.pk))
        Version.objects.filter(revision=revision, object_id=str(guide.pk)).update(db="not-a-real-alias")
        self.assertFalse(revision_contains_object(revision, guide, using=DEFAULT_DB_ALIAS))

    def test_deleted_revision_is_false(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(version__object_id=str(guide.pk))
        revision_pk = revision.pk
        revision.delete()
        stale_revision = Revision(pk=revision_pk)
        self.assertFalse(revision_contains_object(stale_revision, guide))

    def test_unsaved_revision_is_false(self):
        guide = create_with_revision(Guide)
        self.assertFalse(revision_contains_object(Revision(), guide))

    def test_invalid_using_type_raises_type_error(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(version__object_id=str(guide.pk))
        with self.assertRaises(TypeError):
            revision_contains_object(revision, guide, using=123)


class RevisionContainsObjectQueryBudgetTests(TestCase):
    """
    Beta 11.11B2B1A: the join-based lookup makes the query count exact rather
    than a best case - a positive or a relationally-real-but-non-matching
    negative result costs precisely one query against ``reversion_version``,
    never a separate ``ContentType`` lookup beforehand. Tightened from
    ``assertLessEqual`` to ``assertEqual`` accordingly; see
    ``RevisionContainsObjectColdContentTypeCacheTests`` for the same guarantee
    proven with the ContentType cache explicitly cleared first.
    """

    def test_positive_case_is_exactly_one_version_query(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(version__object_id=str(guide.pk))
        with CaptureQueriesContext(connection) as ctx:
            self.assertTrue(revision_contains_object(revision, guide))
        self.assertEqual(version_query_count(ctx), 1)
        self.assertEqual(len(ctx.captured_queries), 1)

    def test_negative_case_with_a_real_revision_is_exactly_one_version_query(self):
        guide_a = create_with_revision(Guide)
        guide_b = create_with_revision(Guide)
        revision_for_b = Revision.objects.get(version__object_id=str(guide_b.pk))
        with CaptureQueriesContext(connection) as ctx:
            self.assertFalse(revision_contains_object(revision_for_b, guide_a))
        self.assertEqual(version_query_count(ctx), 1)
        self.assertEqual(len(ctx.captured_queries), 1)

    def test_none_revision_performs_zero_queries(self):
        guide = create_with_revision(Guide)
        with self.assertNumQueries(0):
            revision_contains_object(None, guide)

    def test_none_object_performs_zero_queries(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(version__object_id=str(guide.pk))
        with self.assertNumQueries(0):
            revision_contains_object(revision, None)

    def test_unsaved_object_performs_zero_queries(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(version__object_id=str(guide.pk))
        with self.assertNumQueries(0):
            revision_contains_object(revision, Guide())

    def test_no_query_touches_child_or_translation_tables(self):
        guide = Guide.objects.create()
        guide.create_translation("en", title="T", intro="i", body="b", slug="b2b1-query-budget")
        with reversion.create_revision():
            guide.save()
        revision = Revision.objects.get(
            version__object_id=str(guide.pk), version__content_type__model="guide"
        )
        with CaptureQueriesContext(connection) as ctx:
            revision_contains_object(revision, guide)
        translation_table = guide.translations.model._meta.db_table
        touched_translation_table = any(translation_table in q["sql"] for q in ctx.captured_queries)
        self.assertFalse(touched_translation_table)


class RevisionContainsObjectColdContentTypeCacheTests(TestCase):
    """
    Beta 11.11B2B1A. Every case here clears Django's process-global
    ``ContentType`` cache (``ContentTypeManager._cache``) immediately before
    the call under test, so a resurrected dependency on
    ``ContentType.objects.get_for_model()`` - or any other path that would
    warm that cache as a side effect - shows up immediately as a second query.
    """

    def _cold_call(self, revision, obj, **kwargs):
        ContentType.objects.clear_cache()
        with CaptureQueriesContext(connection) as ctx:
            result = revision_contains_object(revision, obj, **kwargs)
        return result, ctx

    def test_positive_case_is_exactly_one_query_per_type_with_a_cold_cache(self):
        for model in (Guide, Prompt, UseCase, Comparison):
            with self.subTest(model=model._meta.label):
                obj = create_with_revision(model)
                revision = Revision.objects.get(
                    version__object_id=str(obj.pk),
                    version__content_type__model=model._meta.model_name,
                )
                result, ctx = self._cold_call(revision, obj)
                self.assertTrue(result)
                self.assertEqual(len(ctx.captured_queries), 1)
                sql = ctx.captured_queries[0]["sql"]
                self.assertIn(Version._meta.db_table, sql)
                self.assertIn(ContentType._meta.db_table, sql)

    def test_different_object_same_model_is_one_query_with_a_cold_cache(self):
        guide_a = create_with_revision(Guide)
        guide_b = create_with_revision(Guide)
        revision_for_b = Revision.objects.get(
            version__object_id=str(guide_b.pk), version__content_type__model="guide"
        )
        result, ctx = self._cold_call(revision_for_b, guide_a)
        self.assertFalse(result)
        self.assertEqual(len(ctx.captured_queries), 1)

    def test_different_type_same_numeric_pk_is_one_query_with_a_cold_cache(self):
        guide = create_with_revision(Guide)
        revision_for_guide = Revision.objects.get(
            version__object_id=str(guide.pk), version__content_type__model="guide"
        )
        prompt = create_with_revision(Prompt)
        Prompt.objects.filter(pk=prompt.pk).update(id=guide.pk)
        prompt = Prompt.objects.get(pk=guide.pk)

        result, ctx = self._cold_call(revision_for_guide, prompt)
        self.assertFalse(result)
        self.assertEqual(len(ctx.captured_queries), 1)

    def test_translation_only_revision_is_one_query_with_a_cold_cache(self):
        guide = Guide.objects.create()
        guide.create_translation("en", title="T", intro="i", body="b", slug="b2b1a-cold-child-only")
        translation = guide.translations.get(language_code="en")
        revision = revision_containing_only(translation)

        result, ctx = self._cold_call(revision, guide)
        self.assertFalse(result)
        self.assertEqual(len(ctx.captured_queries), 1)

    def test_wrong_database_alias_is_one_query_with_a_cold_cache(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(
            version__object_id=str(guide.pk), version__content_type__model="guide"
        )
        Version.objects.filter(revision=revision, object_id=str(guide.pk)).update(db="not-a-real-alias")

        result, ctx = self._cold_call(revision, guide, using=DEFAULT_DB_ALIAS)
        self.assertFalse(result)
        self.assertEqual(len(ctx.captured_queries), 1)

    def test_revision_without_any_root_version_is_one_query_with_a_cold_cache(self):
        other_guide = create_with_revision(Guide)
        empty_revision = Revision.objects.create(date_created=timezone.now(), comment="empty")

        result, ctx = self._cold_call(empty_revision, other_guide)
        self.assertFalse(result)
        self.assertEqual(len(ctx.captured_queries), 1)

    def test_early_negative_cases_perform_zero_queries_with_a_cold_cache(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(
            version__object_id=str(guide.pk), version__content_type__model="guide"
        )

        ContentType.objects.clear_cache()
        with self.assertNumQueries(0):
            revision_contains_object(None, guide)

        ContentType.objects.clear_cache()
        with self.assertNumQueries(0):
            revision_contains_object(revision, None)

        ContentType.objects.clear_cache()
        with self.assertNumQueries(0):
            revision_contains_object(revision, Guide())

        ContentType.objects.clear_cache()
        with self.assertNumQueries(0):
            revision_contains_object(Revision(), guide)


class RevisionContainsObjectCacheIndependenceTests(TestCase):
    """No behavior - result, query count, or query class - depends on
    whether Django's ContentType cache happens to be warm."""

    def test_cold_and_warm_produce_the_identical_result_and_query_count(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(
            version__object_id=str(guide.pk), version__content_type__model="guide"
        )

        ContentType.objects.clear_cache()
        with CaptureQueriesContext(connection) as cold_ctx:
            cold_result = revision_contains_object(revision, guide)

        with CaptureQueriesContext(connection) as warm_ctx:
            warm_result = revision_contains_object(revision, guide)

        self.assertTrue(cold_result)
        self.assertEqual(cold_result, warm_result)
        self.assertEqual(len(cold_ctx.captured_queries), 1)
        self.assertEqual(len(cold_ctx.captured_queries), len(warm_ctx.captured_queries))

        cold_sql = cold_ctx.captured_queries[0]["sql"]
        warm_sql = warm_ctx.captured_queries[0]["sql"]
        for sql in (cold_sql, warm_sql):
            self.assertIn(Version._meta.db_table, sql)
            self.assertIn(ContentType._meta.db_table, sql)

    def test_a_pre_warmed_django_contenttype_cache_does_not_change_the_query_count(self):
        """Even if some unrelated caller already resolved this ContentType
        elsewhere in the same process, this function's own query count is
        unaffected - it never reads or benefits from that cache."""
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(
            version__object_id=str(guide.pk), version__content_type__model="guide"
        )
        ContentType.objects.get_for_model(Guide)  # warms Django's own cache

        with CaptureQueriesContext(connection) as ctx:
            result = revision_contains_object(revision, guide)
        self.assertTrue(result)
        self.assertEqual(len(ctx.captured_queries), 1)


class RevisionContainsObjectProxyModelTests(TestCase):
    def test_a_proxy_instance_is_recognised_against_the_concrete_models_revision(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(
            version__object_id=str(guide.pk), version__content_type__model="guide"
        )
        proxy_guide = GuideProxy.objects.get(pk=guide.pk)
        self.assertIsNot(type(proxy_guide), Guide)
        self.assertIs(proxy_guide._meta.concrete_model, Guide)

        self.assertTrue(revision_contains_object(revision, proxy_guide))

    def test_a_proxy_instance_lookup_is_exactly_one_query_with_a_cold_cache(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(
            version__object_id=str(guide.pk), version__content_type__model="guide"
        )
        proxy_guide = GuideProxy.objects.get(pk=guide.pk)

        ContentType.objects.clear_cache()
        with CaptureQueriesContext(connection) as ctx:
            result = revision_contains_object(revision, proxy_guide)
        self.assertTrue(result)
        self.assertEqual(len(ctx.captured_queries), 1)


class NoPrivateReversionApiTests(TestCase):
    """
    Beta 11.11B2B1A removed the only production dependency on a private
    django-reversion symbol (``reversion.revisions._get_content_type``).
    Checked on the parsed source rather than with a blanket underscore-name
    scan, which would also flag this module's own legitimate private helpers
    (``_resolve_db_alias``, ``_is_valid_sha256_hexdigest``, ...).
    """

    def _source_tree(self):
        import ast

        source = Path(review_binding_module.__file__).read_text(encoding="utf-8")
        return ast.parse(source)

    def test_no_import_from_reversion_names_a_private_symbol(self):
        import ast

        offending = []
        for node in ast.walk(self._source_tree()):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.split(".")[0] == "reversion"
            ):
                offending.extend(
                    f"{node.module}.{alias.name}"
                    for alias in node.names
                    if alias.name.startswith("_")
                )
        self.assertEqual(offending, [])

    def test_no_attribute_access_reaches_into_a_reversion_private_name(self):
        """Flags any ``reversion...*._something`` attribute chain - e.g. the
        removed ``reversion.revisions._get_content_type(...)`` call - without
        also flagging this module's own private helpers, which are never
        accessed through a name containing "reversion"."""
        import ast

        offending = []
        for node in ast.walk(self._source_tree()):
            if isinstance(node, ast.Attribute) and node.attr.startswith("_") and not node.attr.startswith("__"):
                root = node
                while isinstance(root, ast.Attribute):
                    root = root.value
                if isinstance(root, ast.Name) and "reversion" in root.id.lower():
                    offending.append(ast.dump(node))
        self.assertEqual(offending, [])


# ======================================================================
# Structured failure codes
# ======================================================================


class BindingFailureReasonTests(TestCase):
    def test_all_seven_reason_codes_exist_and_are_distinct(self):
        codes = {
            BindingFailureReason.REVIEW_REVISION_MISSING,
            BindingFailureReason.REVIEW_FINGERPRINT_MISSING,
            BindingFailureReason.REVIEW_FINGERPRINT_INVALID,
            BindingFailureReason.REVIEW_REVISION_NOT_FOR_OBJECT,
            BindingFailureReason.APPROVED_REVISION_MISSING,
            BindingFailureReason.APPROVED_REVISION_MISMATCH,
            BindingFailureReason.APPROVED_REVISION_NOT_FOR_OBJECT,
        }
        self.assertEqual(len(codes), 7)

    def test_valid_result_has_no_reason(self):
        result = BindingValidationResult(is_valid=True, reason=None)
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.reason)

    def test_result_is_immutable(self):
        result = BindingValidationResult(is_valid=True, reason=None)
        with self.assertRaises(AttributeError):
            result.is_valid = False


# ======================================================================
# 4. Review binding validation
# ======================================================================


class ReviewBindingValidationTestCase(TestCase):
    def setUp(self):
        self.guide = create_with_revision(Guide)
        self.revision = Revision.objects.get(version__object_id=str(self.guide.pk))
        self.fingerprint = fingerprint_review_payload({"title": "T"})


class ReviewBindingValidationTests(ReviewBindingValidationTestCase):
    def test_no_review_revision_is_invalid_with_the_right_reason(self):
        result = validate_review_binding(self.guide)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, BindingFailureReason.REVIEW_REVISION_MISSING)

    def test_revision_set_but_fingerprint_empty_is_invalid(self):
        Guide.objects.filter(pk=self.guide.pk).update(review_revision=self.revision)
        guide = Guide.objects.get(pk=self.guide.pk)
        result = validate_review_binding(guide)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, BindingFailureReason.REVIEW_FINGERPRINT_MISSING)

    def test_syntactically_invalid_fingerprint_is_invalid(self):
        Guide.objects.filter(pk=self.guide.pk).update(
            review_revision=self.revision, review_payload_fingerprint="not-a-digest"
        )
        guide = Guide.objects.get(pk=self.guide.pk)
        result = validate_review_binding(guide)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, BindingFailureReason.REVIEW_FINGERPRINT_INVALID)

    def test_revision_of_a_different_object_is_invalid(self):
        other_guide = create_with_revision(Guide)
        other_revision = Revision.objects.get(version__object_id=str(other_guide.pk))
        Guide.objects.filter(pk=self.guide.pk).update(
            review_revision=other_revision, review_payload_fingerprint=self.fingerprint
        )
        guide = Guide.objects.get(pk=self.guide.pk)
        result = validate_review_binding(guide)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, BindingFailureReason.REVIEW_REVISION_NOT_FOR_OBJECT)

    def test_revision_containing_only_a_translation_is_invalid(self):
        guide = Guide.objects.create()
        guide.create_translation("en", title="T", intro="i", body="b", slug="b2b1-review-child-only")
        translation = guide.translations.get(language_code="en")
        translation_only_revision = revision_containing_only(translation)
        Guide.objects.filter(pk=guide.pk).update(
            review_revision=translation_only_revision,
            review_payload_fingerprint=self.fingerprint,
        )
        guide = Guide.objects.get(pk=guide.pk)
        result = validate_review_binding(guide)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, BindingFailureReason.REVIEW_REVISION_NOT_FOR_OBJECT)

    def test_wrong_database_alias_is_invalid(self):
        Version.objects.filter(revision=self.revision, object_id=str(self.guide.pk)).update(
            db="not-a-real-alias"
        )
        Guide.objects.filter(pk=self.guide.pk).update(
            review_revision=self.revision, review_payload_fingerprint=self.fingerprint
        )
        guide = Guide.objects.get(pk=self.guide.pk)
        result = validate_review_binding(guide, using=DEFAULT_DB_ALIAS)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, BindingFailureReason.REVIEW_REVISION_NOT_FOR_OBJECT)

    def test_a_genuinely_valid_binding_is_valid(self):
        Guide.objects.filter(pk=self.guide.pk).update(
            review_revision=self.revision, review_payload_fingerprint=self.fingerprint
        )
        guide = Guide.objects.get(pk=self.guide.pk)
        result = validate_review_binding(guide)
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.reason)

    def test_error_priority_missing_revision_beats_missing_fingerprint(self):
        """Both are wrong; REVIEW_REVISION_MISSING must win (checked first)."""
        result = validate_review_binding(self.guide)
        self.assertEqual(result.reason, BindingFailureReason.REVIEW_REVISION_MISSING)

    def test_error_priority_missing_fingerprint_beats_invalid_fingerprint_shape(self):
        """An empty fingerprint is reported as MISSING, not INVALID, even
        though '' also fails the hexdigest shape check."""
        Guide.objects.filter(pk=self.guide.pk).update(review_revision=self.revision)
        guide = Guide.objects.get(pk=self.guide.pk)
        result = validate_review_binding(guide)
        self.assertEqual(result.reason, BindingFailureReason.REVIEW_FINGERPRINT_MISSING)

    def test_error_priority_invalid_fingerprint_beats_wrong_revision(self):
        other_guide = create_with_revision(Guide)
        other_revision = Revision.objects.get(version__object_id=str(other_guide.pk))
        Guide.objects.filter(pk=self.guide.pk).update(
            review_revision=other_revision, review_payload_fingerprint="short"
        )
        guide = Guide.objects.get(pk=self.guide.pk)
        result = validate_review_binding(guide)
        self.assertEqual(result.reason, BindingFailureReason.REVIEW_FINGERPRINT_INVALID)


# ======================================================================
# 5. Approved binding validation
# ======================================================================


class ApprovedBindingValidationTests(ReviewBindingValidationTestCase):
    def test_invalid_review_binding_is_passed_through_unchanged(self):
        result = validate_approved_binding(self.guide)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, BindingFailureReason.REVIEW_REVISION_MISSING)

    def test_valid_review_but_missing_approved_revision_is_invalid(self):
        Guide.objects.filter(pk=self.guide.pk).update(
            review_revision=self.revision, review_payload_fingerprint=self.fingerprint
        )
        guide = Guide.objects.get(pk=self.guide.pk)
        result = validate_approved_binding(guide)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, BindingFailureReason.APPROVED_REVISION_MISSING)

    def test_approved_revision_different_from_review_revision_is_a_mismatch(self):
        other_guide = create_with_revision(Guide)
        other_revision = Revision.objects.get(version__object_id=str(other_guide.pk))
        Guide.objects.filter(pk=self.guide.pk).update(
            review_revision=self.revision,
            review_payload_fingerprint=self.fingerprint,
            approved_revision=other_revision,
        )
        guide = Guide.objects.get(pk=self.guide.pk)
        result = validate_approved_binding(guide)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, BindingFailureReason.APPROVED_REVISION_MISMATCH)

    def test_same_id_but_approved_revision_does_not_contain_the_object_is_invalid(self):
        """
        Forces review_revision_id == approved_revision_id while the approved
        FK points at a Revision row that (after row surgery) no longer
        contains this object's version - proving the approval check does its
        own membership lookup rather than trusting the equality check alone.
        """
        Guide.objects.filter(pk=self.guide.pk).update(
            review_revision=self.revision,
            review_payload_fingerprint=self.fingerprint,
            approved_revision=self.revision,
        )
        Version.objects.filter(revision=self.revision, object_id=str(self.guide.pk)).update(
            db="not-a-real-alias"
        )
        guide = Guide.objects.get(pk=self.guide.pk)
        review_result = validate_review_binding(guide, using=DEFAULT_DB_ALIAS)
        self.assertFalse(review_result.is_valid)

        approved_result = validate_approved_binding(guide, using=DEFAULT_DB_ALIAS)
        self.assertFalse(approved_result.is_valid)
        self.assertEqual(approved_result.reason, BindingFailureReason.REVIEW_REVISION_NOT_FOR_OBJECT)

    def test_a_genuinely_valid_approval_is_valid(self):
        Guide.objects.filter(pk=self.guide.pk).update(
            review_revision=self.revision,
            review_payload_fingerprint=self.fingerprint,
            approved_revision=self.revision,
        )
        guide = Guide.objects.get(pk=self.guide.pk)
        result = validate_approved_binding(guide)
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.reason)

    def test_no_status_reviewer_or_payload_comparison_is_performed(self):
        """Status stays draft, no reviewer set, fingerprint not compared to
        current content - none of that is part of this slice's contract."""
        Guide.objects.filter(pk=self.guide.pk).update(
            review_revision=self.revision,
            review_payload_fingerprint=self.fingerprint,
            approved_revision=self.revision,
        )
        guide = Guide.objects.get(pk=self.guide.pk)
        self.assertEqual(guide.status, Workflow.STATUS_DRAFT)
        self.assertIsNone(guide.reviewed_by_id)
        result = validate_approved_binding(guide)
        self.assertTrue(result.is_valid)


# ======================================================================
# 6. Live-snapshot detection
# ======================================================================


class LiveSnapshotDetectionSimpleTypesTests(TestCase):
    def test_empty_live_i18n_is_false_for_all_three_simple_types(self):
        for model in (Guide, Prompt, UseCase):
            with self.subTest(model=model._meta.label):
                obj = model.objects.create(live_i18n={})
                self.assertFalse(has_provable_live_snapshot(obj))

    def test_nonempty_live_i18n_is_true_for_all_three_simple_types(self):
        for model in (Guide, Prompt, UseCase):
            with self.subTest(model=model._meta.label):
                obj = model.objects.create(live_i18n={"en": {}})
                self.assertTrue(has_provable_live_snapshot(obj))

    def test_live_i18n_with_empty_string_title_still_counts(self):
        obj = Guide.objects.create(live_i18n={"en": {"title": ""}})
        self.assertTrue(has_provable_live_snapshot(obj))

    def test_status_never_influences_the_result(self):
        for status in Workflow.STATUS_CHOICES:
            status_value = status[0]
            with self.subTest(status=status_value):
                obj = Guide.objects.create(live_i18n={"en": {}})
                Guide.objects.filter(pk=obj.pk).update(status=status_value)
                obj = Guide.objects.get(pk=obj.pk)
                self.assertTrue(has_provable_live_snapshot(obj))

    def test_legacy_marker_never_influences_the_result(self):
        with_marker = Guide.objects.create(live_i18n={}, last_published_revision_id=123)
        self.assertFalse(has_provable_live_snapshot(with_marker))
        without_marker = Guide.objects.create(live_i18n={"en": {}}, last_published_revision_id=None)
        self.assertTrue(has_provable_live_snapshot(without_marker))

    def test_is_published_flag_never_influences_the_result(self):
        published_but_empty = Guide.objects.create(live_i18n={}, is_published=True)
        self.assertFalse(has_provable_live_snapshot(published_but_empty))
        unpublished_but_snapshotted = Guide.objects.create(live_i18n={"en": {}}, is_published=False)
        self.assertTrue(has_provable_live_snapshot(unpublished_but_snapshotted))


class LiveSnapshotDetectionComparisonTests(TestCase):
    def test_empty_i18n_and_null_entries_is_false(self):
        obj = Comparison.objects.create(live_i18n={}, live_entries=None)
        self.assertFalse(has_provable_live_snapshot(obj))

    def test_empty_i18n_and_empty_entries_list_is_false(self):
        obj = Comparison.objects.create(live_i18n={}, live_entries=[])
        self.assertFalse(has_provable_live_snapshot(obj))

    def test_filled_i18n_and_null_entries_is_false(self):
        obj = Comparison.objects.create(live_i18n={"en": {}}, live_entries=None)
        self.assertFalse(has_provable_live_snapshot(obj))

    def test_filled_i18n_and_empty_entries_list_is_true(self):
        obj = Comparison.objects.create(live_i18n={"en": {}}, live_entries=[])
        self.assertTrue(has_provable_live_snapshot(obj))

    def test_filled_i18n_and_filled_entries_list_is_true(self):
        obj = Comparison.objects.create(
            live_i18n={"en": {}}, live_entries=[{"tool_id": 1, "position": 0, "translations": {}}]
        )
        self.assertTrue(has_provable_live_snapshot(obj))


class LiveSnapshotDetectionUnsupportedTypeTests(TestCase):
    def test_an_unrelated_model_raises_instead_of_silently_returning_false(self):
        tool = Tool.objects.create(slug="b2b1-unsupported")
        with self.assertRaises(TypeError):
            has_provable_live_snapshot(tool)

    def test_unsupported_type_check_performs_no_query(self):
        tool = Tool.objects.create(slug="b2b1-unsupported-query")
        with self.assertNumQueries(0), self.assertRaises(TypeError):
            has_provable_live_snapshot(tool)


# ======================================================================
# 7. Invalidation target
# ======================================================================


class InvalidationTargetTests(TestCase):
    def test_every_type_without_a_snapshot_targets_draft(self):
        for model in (Guide, Prompt, UseCase):
            with self.subTest(model=model._meta.label):
                obj = model.objects.create(live_i18n={})
                self.assertEqual(target_status_after_review_invalidation(obj), Workflow.STATUS_DRAFT)
        comparison = Comparison.objects.create(live_i18n={}, live_entries=None)
        self.assertEqual(target_status_after_review_invalidation(comparison), Workflow.STATUS_DRAFT)

    def test_every_type_with_a_snapshot_still_targets_draft(self):
        """
        Beta 11.11D1: a live snapshot no longer redirects the automatic
        target to ``rework`` on any type. Staying publicly visible is decided
        by ``EditorialQuerySet.visible_on_site()`` instead, so the two
        concerns the old rule conflated are now separate.
        """
        for model in (Guide, Prompt, UseCase):
            with self.subTest(model=model._meta.label):
                obj = model.objects.create(live_i18n={"en": {}})
                self.assertEqual(target_status_after_review_invalidation(obj), Workflow.STATUS_DRAFT)
        comparison = Comparison.objects.create(live_i18n={"en": {}}, live_entries=[])
        self.assertEqual(target_status_after_review_invalidation(comparison), Workflow.STATUS_DRAFT)

    def test_comparison_with_empty_entries_list_also_targets_draft(self):
        comparison = Comparison.objects.create(live_i18n={"en": {}}, live_entries=[])
        self.assertEqual(target_status_after_review_invalidation(comparison), Workflow.STATUS_DRAFT)

    def test_comparison_with_null_entries_targets_draft(self):
        comparison = Comparison.objects.create(live_i18n={"en": {}}, live_entries=None)
        self.assertEqual(target_status_after_review_invalidation(comparison), Workflow.STATUS_DRAFT)

    def test_the_function_does_not_change_the_objects_status(self):
        obj = Guide.objects.create(live_i18n={"en": {}}, status=Workflow.STATUS_REVIEW)
        Guide.objects.filter(pk=obj.pk).update(status=Workflow.STATUS_REVIEW)
        before = Guide.objects.get(pk=obj.pk).status
        target_status_after_review_invalidation(Guide.objects.get(pk=obj.pk))
        after = Guide.objects.get(pk=obj.pk).status
        self.assertEqual(before, after)
        self.assertEqual(before, Workflow.STATUS_REVIEW)

    def test_the_function_performs_no_query(self):
        obj = Guide.objects.create(live_i18n={"en": {}})
        obj = Guide.objects.get(pk=obj.pk)
        with self.assertNumQueries(0):
            target_status_after_review_invalidation(obj)


# ======================================================================
# 10. Mutation freedom
# ======================================================================


class MutationFreedomTests(TestCase):
    """
    One fully-populated object per type, every applicable primitive called
    several times, then a full field-by-field before/after comparison plus a
    global Revision/Version row count check.
    """

    TRACKED_FIELDS = (
        "status",
        "review_revision_id",
        "approved_revision_id",
        "review_payload_fingerprint",
        "reviewed_by_id",
        "reviewed_at",
        "submitted_for_review_at",
        "review_note",
        "live_i18n",
        "live_entries",
        "last_published_revision_id",
        "updated_at",
    )

    @classmethod
    def setUpTestData(cls):
        cls.reviewer = User.objects.create_user("b2b1-reviewer", "b2b1r@example.com", "pw")

    def _snapshot(self, obj):
        return {field: getattr(obj, field) for field in self.TRACKED_FIELDS if hasattr(obj, field)}

    def _run_every_primitive(self, obj, revision, fingerprint):
        for _ in range(3):
            revision_contains_object(revision, obj)
            validate_review_binding(obj)
            validate_approved_binding(obj)
            has_provable_live_snapshot(obj)
            target_status_after_review_invalidation(obj)
        fingerprint_review_payload({"a": 1, "b": [1, 2, 3]})

    def test_guide_is_left_completely_unchanged(self):
        self._assert_type_unchanged(Guide, extra={"live_i18n": {"en": {"title": "T"}}})

    def test_prompt_is_left_completely_unchanged(self):
        self._assert_type_unchanged(Prompt, extra={"live_i18n": {"en": {"title": "T"}}})

    def test_usecase_is_left_completely_unchanged(self):
        self._assert_type_unchanged(UseCase, extra={"live_i18n": {"en": {"title": "T"}}})

    def test_comparison_is_left_completely_unchanged(self):
        self._assert_type_unchanged(
            Comparison, extra={"live_i18n": {"en": {"title": "T"}}, "live_entries": []}
        )

    def _assert_type_unchanged(self, model, *, extra):
        guide = create_with_revision(Guide)  # a neutral revision to bind to
        revision = Revision.objects.get(version__object_id=str(guide.pk))
        fingerprint = fingerprint_review_payload({"title": "T"})

        obj = model.objects.create(
            author=self.reviewer,
            reviewed_by=self.reviewer,
            reviewed_at=None,
            submitted_for_review_at=None,
            review_note="keep me exactly as I am",
            review_revision=revision,
            approved_revision=revision,
            review_payload_fingerprint=fingerprint,
            last_published_revision_id=999999,
            **extra,
        )
        obj = model.objects.get(pk=obj.pk)

        revisions_before = Revision.objects.count()
        versions_before = Version.objects.count()
        before = self._snapshot(obj)

        self._run_every_primitive(obj, revision, fingerprint)

        after = self._snapshot(model.objects.get(pk=obj.pk))
        revisions_after = Revision.objects.count()
        versions_after = Version.objects.count()

        self.assertEqual(before, after)
        self.assertEqual(revisions_before, revisions_after)
        self.assertEqual(versions_before, versions_after)

    def test_running_the_primitives_does_not_create_a_new_revision_or_version(self):
        guide = create_with_revision(Guide)
        revision = Revision.objects.get(version__object_id=str(guide.pk))
        revisions_before = Revision.objects.count()
        versions_before = Version.objects.count()

        self._run_every_primitive(guide, revision, fingerprint_review_payload({"a": 1}))

        self.assertEqual(Revision.objects.count(), revisions_before)
        self.assertEqual(Version.objects.count(), versions_before)
