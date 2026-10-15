"""
Beta 11.11B2A: the fail-closed cleanup of historical review/approved rows,
driven through Django's real migration executor.

Every editorial object currently sitting in ``review`` or ``approved`` got
there before any review binding existed. Beta 11.11A established that the
recorded history cannot prove *which* revision a reviewer looked at, so the
migration refuses to guess and instead returns those rows to a state that
requires a fresh, bindable review. The direction depends on one question only:
is there a provable published state to keep serving?

* yes -> ``rework``. The live snapshot stays authoritative and the page stays
  public (``EditorialQuerySet.LIVE_EDITING_STATUSES`` includes ``rework``).
* no  -> ``draft``. Nothing that was never demonstrably published becomes
  visible through a migration.

``last_published_revision_id`` is deliberately not part of that question. It
holds a ``Version.id``, it predates the snapshot mechanism, and a row carrying
it with an empty snapshot has nothing published to render - the public
surfaces would fall back to its *current draft*. Both directions of that
asymmetry are asserted below.

Uses the project's existing executor pattern (``guides/tests/test_migrations``):
``TransactionTestCase``, migrate back, seed through the historical models,
migrate forward, then restore the app to HEAD in ``tearDown`` so later tests in
the same process see the real schema.
"""
from datetime import UTC, datetime
from typing import Any, ClassVar

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase

BEFORE = {
    "guides": "0008_alter_guide_updated_at",
    "prompts": "0006_alter_prompt_updated_at",
    "usecases": "0006_backfill_usecase_live_state",
    "compare": "0007_comparison_live_entries",
}
AFTER = {
    "guides": "0009_guide_approved_revision_and_more",
    "prompts": "0007_prompt_approved_revision_and_more",
    "usecases": "0007_usecase_approved_revision_and_more",
    "compare": "0008_comparison_approved_revision_and_more",
}

#: A fixed instant, so "unchanged" assertions on created_at/updated_at compare
#: against a value the test controls rather than against "roughly now".
FROZEN = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)


class EditorialMigrationTestCase(TransactionTestCase):
    """Executor harness shared by the four per-app matrices."""

    app = None
    model_name = None
    #: Extra kwargs the historical model needs on create() (Comparison only).
    extra_defaults: ClassVar[dict[str, Any]] = {}

    def setUp(self):
        super().setUp()
        migrate_from = [(self.app, BEFORE[self.app])]
        migrate_to = [(self.app, AFTER[self.app])]

        if self.app == "prompts":
            # Beta 11.11C4D added prompts/migrations/0008_prompt_review_payload_v2.py
            # on top of AFTER["prompts"], and it is deliberately irreversible (no
            # reverse_code at all - see its own module docstring). Rolling
            # "prompts" back to BEFORE["prompts"] would otherwise have to unapply
            # 0008 first, which raises IrreversibleError. 0008 has zero schema
            # operations, so there is nothing to actually reverse at the schema
            # level - deleting its own "applied" bookkeeping row (never touching
            # data, never invoking reverse_code) is a fully safe stand-in, and
            # forward `migrate()` calls (including this file's own tearDown) simply
            # re-run it for real afterwards.
            MigrationRecorder(connection).record_unapplied(
                "prompts", "0008_prompt_review_payload_v2"
            )

        executor = MigrationExecutor(connection)
        executor.migrate(migrate_from)
        self.old_apps = executor.loader.project_state(migrate_from).apps

        self.seeded = self.seed(self.old_apps)

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(migrate_to)

        self.new_apps = executor.loader.project_state(migrate_to).apps

    def tearDown(self):
        call_command("migrate", self.app, verbosity=0)
        super().tearDown()

    # -- helpers -------------------------------------------------------

    def historical(self, apps):
        return apps.get_model(self.app, self.model_name)

    def make_row(self, apps, **kwargs):
        """
        Create one row through the *historical* model, with the workflow
        metadata a real review/approved record would carry, so the cleanup has
        something to actually clear.
        """
        defaults = dict(
            created_at=FROZEN,
            updated_at=FROZEN,
            submitted_for_review_at=FROZEN,
            reviewed_at=FROZEN,
            review_note="feedback that must survive",
            live_i18n={},
            **self.extra_defaults,
        )
        defaults.update(kwargs)
        model = self.historical(apps)
        row = model.objects.create(**defaults)
        # created_at/updated_at have default=timezone.now / auto_now, so pin
        # them with an UPDATE that bypasses both.
        model.objects.filter(pk=row.pk).update(created_at=FROZEN, updated_at=FROZEN)
        return row.pk

    def reload(self, pk):
        return self.historical(self.new_apps).objects.get(pk=pk)

    def seed(self, apps):
        raise NotImplementedError

    # -- shared assertions ---------------------------------------------

    def assert_unbound(self, row):
        self.assertIsNone(row.review_revision_id)
        self.assertIsNone(row.approved_revision_id)
        self.assertEqual(row.review_payload_fingerprint, "")

    def assert_workflow_metadata_cleared(self, row):
        self.assertIsNone(row.reviewed_by_id)
        self.assertIsNone(row.reviewed_at)
        self.assertIsNone(row.submitted_for_review_at)

    def assert_workflow_metadata_kept(self, row):
        self.assertIsNotNone(row.reviewed_at)
        self.assertIsNotNone(row.submitted_for_review_at)

    def assert_content_preserved(self, row, *, live_i18n, marker):
        self.assertEqual(row.review_note, "feedback that must survive")
        self.assertEqual(row.created_at, FROZEN)
        self.assertEqual(row.updated_at, FROZEN, "bulk update must not fire auto_now")
        self.assertEqual(row.live_i18n, live_i18n)
        self.assertEqual(row.last_published_revision_id, marker)


class _SimpleEditorialMatrixMixin:
    """
    The Guide/Prompt/UseCase matrix - identical because all three decide on
    ``bool(live_i18n)`` alone.
    """

    SNAPSHOT: ClassVar[dict[str, Any]] = {"en": {"title": "Published title", "slug": "published-slug"}}

    def seed(self, apps):
        return {
            # (status, snapshot, legacy marker)
            "review_no_snapshot": self.make_row(apps, status="review"),
            "approved_no_snapshot": self.make_row(apps, status="approved"),
            "review_with_snapshot": self.make_row(
                apps, status="review", live_i18n=self.SNAPSHOT,
                last_published_revision_id=101,
            ),
            "approved_with_snapshot": self.make_row(
                apps, status="approved", live_i18n=self.SNAPSHOT,
                last_published_revision_id=102,
            ),
            # Live-proof asymmetry
            "review_snapshot_without_marker": self.make_row(
                apps, status="review", live_i18n=self.SNAPSHOT,
                last_published_revision_id=None,
            ),
            "review_marker_without_snapshot": self.make_row(
                apps, status="review", live_i18n={}, last_published_revision_id=999,
            ),
            # Untouched statuses
            "draft": self.make_row(apps, status="draft"),
            "rework": self.make_row(apps, status="rework", live_i18n=self.SNAPSHOT),
            "published": self.make_row(
                apps, status="published", live_i18n=self.SNAPSHOT,
                last_published_revision_id=103, is_published=True,
            ),
            "archived": self.make_row(apps, status="archived", live_i18n=self.SNAPSHOT),
        }

    # -- Zielstatusmatrix ----------------------------------------------

    def test_review_without_live_snapshot_becomes_draft(self):
        row = self.reload(self.seeded["review_no_snapshot"])
        self.assertEqual(row.status, "draft")

    def test_approved_without_live_snapshot_becomes_draft(self):
        row = self.reload(self.seeded["approved_no_snapshot"])
        self.assertEqual(row.status, "draft")

    def test_review_with_live_snapshot_becomes_rework(self):
        row = self.reload(self.seeded["review_with_snapshot"])
        self.assertEqual(row.status, "rework")

    def test_approved_with_live_snapshot_becomes_rework(self):
        row = self.reload(self.seeded["approved_with_snapshot"])
        self.assertEqual(row.status, "rework")

    def test_every_other_status_is_left_alone(self):
        for key, expected in (
            ("draft", "draft"),
            ("rework", "rework"),
            ("published", "published"),
            ("archived", "archived"),
        ):
            with self.subTest(status=key):
                self.assertEqual(self.reload(self.seeded[key]).status, expected)

    # -- Live-Beweis-Asymmetrie ----------------------------------------

    def test_snapshot_without_legacy_marker_still_counts_as_live(self):
        """The snapshot is the proof; the marker is not required."""
        row = self.reload(self.seeded["review_snapshot_without_marker"])
        self.assertEqual(row.status, "rework")
        self.assertIsNone(row.last_published_revision_id)

    def test_legacy_marker_without_snapshot_does_not_count_as_live(self):
        """
        The marker alone proves nothing renderable: with an empty
        ``live_i18n`` the public surfaces fall back to the *current draft*, so
        keeping such a row online would publish unreviewed text. Fail closed.
        """
        row = self.reload(self.seeded["review_marker_without_snapshot"])
        self.assertEqual(row.status, "draft")
        self.assertEqual(row.last_published_revision_id, 999)

    # -- Bindingfelder --------------------------------------------------

    def test_no_historical_row_gets_a_binding_invented_for_it(self):
        for key in self.seeded:
            with self.subTest(row=key):
                self.assert_unbound(self.reload(self.seeded[key]))

    # -- Workflow-Metadaten ---------------------------------------------

    def test_downgraded_rows_lose_their_review_metadata(self):
        for key in (
            "review_no_snapshot",
            "approved_no_snapshot",
            "review_with_snapshot",
            "approved_with_snapshot",
        ):
            with self.subTest(row=key):
                self.assert_workflow_metadata_cleared(self.reload(self.seeded[key]))

    def test_untouched_rows_keep_their_review_metadata(self):
        for key in ("draft", "rework", "published", "archived"):
            with self.subTest(row=key):
                self.assert_workflow_metadata_kept(self.reload(self.seeded[key]))

    def test_review_note_survives_on_downgraded_rows(self):
        for key in ("review_no_snapshot", "review_with_snapshot"):
            with self.subTest(row=key):
                self.assertEqual(
                    self.reload(self.seeded[key]).review_note,
                    "feedback that must survive",
                )

    # -- Unveränderte Daten ----------------------------------------------

    def test_content_snapshots_timestamps_and_legacy_marker_are_preserved(self):
        for key, snapshot, marker in (
            ("review_no_snapshot", {}, None),
            ("review_with_snapshot", self.SNAPSHOT, 101),
            ("approved_with_snapshot", self.SNAPSHOT, 102),
            ("published", self.SNAPSHOT, 103),
        ):
            with self.subTest(row=key):
                self.assert_content_preserved(
                    self.reload(self.seeded[key]), live_i18n=snapshot, marker=marker
                )

    def test_is_published_flag_is_not_rewritten(self):
        self.assertTrue(self.reload(self.seeded["published"]).is_published)
        self.assertFalse(self.reload(self.seeded["review_with_snapshot"]).is_published)


class GuideReviewBindingMigrationTests(
    _SimpleEditorialMatrixMixin, EditorialMigrationTestCase
):
    app = "guides"
    model_name = "Guide"

    def seed(self, apps):
        seeded = super().seed(apps)
        # Translations and a child section, to prove the data migration touches
        # neither content nor structure.
        Guide = self.historical(apps)
        GuideTranslation = apps.get_model("guides", "GuideTranslation")
        GuideSection = apps.get_model("guides", "GuideSection")
        guide = Guide.objects.get(pk=seeded["review_with_snapshot"])
        GuideTranslation.objects.create(
            master=guide, language_code="en", title="EN title",
            intro="i", body="b", slug="b2a-guide-en",
        )
        GuideTranslation.objects.create(
            master=guide, language_code="de", title="DE title",
            intro="i", body="b", slug="b2a-guide-de",
        )
        GuideSection.objects.create(guide=guide, order=0)
        return seeded

    def test_translations_and_child_rows_are_untouched(self):
        GuideTranslation = self.new_apps.get_model("guides", "GuideTranslation")
        GuideSection = self.new_apps.get_model("guides", "GuideSection")
        pk = self.seeded["review_with_snapshot"]

        titles = sorted(
            GuideTranslation.objects.filter(master_id=pk).values_list(
                "language_code", "title"
            )
        )
        self.assertEqual(titles, [("de", "DE title"), ("en", "EN title")])
        self.assertEqual(GuideSection.objects.filter(guide_id=pk).count(), 1)


class PromptReviewBindingMigrationTests(
    _SimpleEditorialMatrixMixin, EditorialMigrationTestCase
):
    app = "prompts"
    model_name = "Prompt"

    def seed(self, apps):
        seeded = super().seed(apps)
        Prompt = self.historical(apps)
        PromptTranslation = apps.get_model("prompts", "PromptTranslation")
        prompt = Prompt.objects.get(pk=seeded["review_with_snapshot"])
        PromptTranslation.objects.create(
            master=prompt, language_code="en", title="EN title",
            intro="i", body="b", outro="o", slug="b2a-prompt-en",
        )
        return seeded

    def test_translations_are_untouched(self):
        PromptTranslation = self.new_apps.get_model("prompts", "PromptTranslation")
        pk = self.seeded["review_with_snapshot"]
        self.assertEqual(
            list(
                PromptTranslation.objects.filter(master_id=pk).values_list(
                    "title", flat=True
                )
            ),
            ["EN title"],
        )


class UseCaseReviewBindingMigrationTests(
    _SimpleEditorialMatrixMixin, EditorialMigrationTestCase
):
    app = "usecases"
    model_name = "UseCase"

    def seed(self, apps):
        seeded = super().seed(apps)
        UseCase = self.historical(apps)
        UseCaseTranslation = apps.get_model("usecases", "UseCaseTranslation")
        usecase = UseCase.objects.get(pk=seeded["review_with_snapshot"])
        UseCaseTranslation.objects.create(
            master=usecase, language_code="en", title="EN title",
            intro="i", body="b", outro="o", persona="Persona EN",
            slug="b2a-uc-en",
        )
        return seeded

    def test_translations_including_persona_are_untouched(self):
        UseCaseTranslation = self.new_apps.get_model("usecases", "UseCaseTranslation")
        pk = self.seeded["review_with_snapshot"]
        translation = UseCaseTranslation.objects.get(master_id=pk, language_code="en")
        self.assertEqual(translation.title, "EN title")
        self.assertEqual(translation.persona, "Persona EN")


class ComparisonReviewBindingMigrationTests(EditorialMigrationTestCase):
    """
    Comparison's stricter contract::

        has_live_snapshot = bool(live_i18n) and live_entries is not None

    ``live_entries`` is three-state (Beta 11.9): ``None`` = published before the
    entry snapshot existed, ``[]`` = published with zero entries, list = the
    ordinary case. Only the last two are a complete published state.
    """

    app = "compare"
    model_name = "Comparison"
    extra_defaults: ClassVar[dict[str, Any]] = {"live_entries": None}

    SNAPSHOT: ClassVar[dict[str, Any]] = {"en": {"title": "Published title", "slug": "published-slug"}}
    ENTRIES: ClassVar[list[dict[str, Any]]] = [{"tool_id": 1, "position": 0, "translations": {"en": {"label": "A"}}}]

    def seed(self, apps):
        return {
            # --- the four-cell base matrix (with a usable entry snapshot) ---
            "review_no_snapshot": self.make_row(apps, status="review"),
            "approved_no_snapshot": self.make_row(apps, status="approved"),
            "review_with_snapshot": self.make_row(
                apps, status="review", live_i18n=self.SNAPSHOT,
                live_entries=self.ENTRIES, last_published_revision_id=101,
            ),
            "approved_with_snapshot": self.make_row(
                apps, status="approved", live_i18n=self.SNAPSHOT,
                live_entries=self.ENTRIES, last_published_revision_id=102,
            ),
            # --- the live_entries three-state contract -------------------
            "i18n_empty_entries_null": self.make_row(
                apps, status="review", live_i18n={}, live_entries=None,
            ),
            "i18n_empty_entries_empty_list": self.make_row(
                apps, status="review", live_i18n={}, live_entries=[],
            ),
            "i18n_set_entries_null": self.make_row(
                apps, status="review", live_i18n=self.SNAPSHOT, live_entries=None,
                last_published_revision_id=201,
            ),
            "i18n_set_entries_empty_list": self.make_row(
                apps, status="review", live_i18n=self.SNAPSHOT, live_entries=[],
                last_published_revision_id=202,
            ),
            "i18n_set_entries_filled": self.make_row(
                apps, status="approved", live_i18n=self.SNAPSHOT,
                live_entries=self.ENTRIES, last_published_revision_id=203,
            ),
            # --- live-proof asymmetry ------------------------------------
            "snapshot_without_marker": self.make_row(
                apps, status="review", live_i18n=self.SNAPSHOT,
                live_entries=self.ENTRIES, last_published_revision_id=None,
            ),
            "marker_without_snapshot": self.make_row(
                apps, status="review", live_i18n={}, live_entries=None,
                last_published_revision_id=999,
            ),
            # --- untouched statuses --------------------------------------
            "draft": self.make_row(apps, status="draft"),
            "rework": self.make_row(
                apps, status="rework", live_i18n=self.SNAPSHOT, live_entries=self.ENTRIES
            ),
            "published": self.make_row(
                apps, status="published", live_i18n=self.SNAPSHOT,
                live_entries=self.ENTRIES, last_published_revision_id=103,
                is_published=True,
            ),
            "archived": self.make_row(
                apps, status="archived", live_i18n=self.SNAPSHOT, live_entries=self.ENTRIES
            ),
        }

    # -- Zielstatusmatrix ------------------------------------------------

    def test_review_without_live_snapshot_becomes_draft(self):
        self.assertEqual(self.reload(self.seeded["review_no_snapshot"]).status, "draft")

    def test_approved_without_live_snapshot_becomes_draft(self):
        self.assertEqual(self.reload(self.seeded["approved_no_snapshot"]).status, "draft")

    def test_review_with_live_snapshot_becomes_rework(self):
        self.assertEqual(self.reload(self.seeded["review_with_snapshot"]).status, "rework")

    def test_approved_with_live_snapshot_becomes_rework(self):
        self.assertEqual(
            self.reload(self.seeded["approved_with_snapshot"]).status, "rework"
        )

    def test_every_other_status_is_left_alone(self):
        for key, expected in (
            ("draft", "draft"),
            ("rework", "rework"),
            ("published", "published"),
            ("archived", "archived"),
        ):
            with self.subTest(status=key):
                self.assertEqual(self.reload(self.seeded[key]).status, expected)

    # -- live_entries Dreistufenvertrag ----------------------------------

    def test_the_full_live_entries_matrix(self):
        """The table from the slice contract, asserted cell by cell."""
        for key, expected, why in (
            ("i18n_empty_entries_null", "draft", "no parent snapshot, no entry snapshot"),
            ("i18n_empty_entries_empty_list", "draft", "no parent snapshot"),
            ("i18n_set_entries_null", "draft", "legacy: entries still read from live rows"),
            ("i18n_set_entries_empty_list", "rework", "published with zero entries"),
            ("i18n_set_entries_filled", "rework", "ordinary published state"),
        ):
            with self.subTest(case=key, why=why):
                self.assertEqual(self.reload(self.seeded[key]).status, expected)

    def test_empty_entry_list_is_a_published_snapshot_not_a_missing_one(self):
        """
        The single most dangerous cell: a truthiness check instead of
        ``is not None`` would send a genuinely published comparison to
        ``draft`` and take it offline.
        """
        row = self.reload(self.seeded["i18n_set_entries_empty_list"])
        self.assertEqual(row.status, "rework")
        self.assertEqual(row.live_entries, [])

    def test_null_entries_do_not_count_even_with_a_parent_snapshot(self):
        row = self.reload(self.seeded["i18n_set_entries_null"])
        self.assertEqual(row.status, "draft")
        self.assertIsNone(row.live_entries)

    # -- Live-Beweis-Asymmetrie ------------------------------------------

    def test_snapshot_without_legacy_marker_still_counts_as_live(self):
        row = self.reload(self.seeded["snapshot_without_marker"])
        self.assertEqual(row.status, "rework")
        self.assertIsNone(row.last_published_revision_id)

    def test_legacy_marker_without_snapshot_does_not_count_as_live(self):
        row = self.reload(self.seeded["marker_without_snapshot"])
        self.assertEqual(row.status, "draft")
        self.assertEqual(row.last_published_revision_id, 999)

    # -- Bindingfelder und Metadaten -------------------------------------

    def test_no_historical_row_gets_a_binding_invented_for_it(self):
        for key in self.seeded:
            with self.subTest(row=key):
                self.assert_unbound(self.reload(self.seeded[key]))

    def test_downgraded_rows_lose_their_review_metadata(self):
        for key in (
            "review_no_snapshot",
            "approved_no_snapshot",
            "review_with_snapshot",
            "approved_with_snapshot",
        ):
            with self.subTest(row=key):
                self.assert_workflow_metadata_cleared(self.reload(self.seeded[key]))

    def test_untouched_rows_keep_their_review_metadata(self):
        for key in ("draft", "rework", "published", "archived"):
            with self.subTest(row=key):
                self.assert_workflow_metadata_kept(self.reload(self.seeded[key]))

    # -- Unveränderte Daten ------------------------------------------------

    def test_snapshots_timestamps_and_legacy_marker_are_preserved(self):
        row = self.reload(self.seeded["review_with_snapshot"])
        self.assert_content_preserved(row, live_i18n=self.SNAPSHOT, marker=101)
        self.assertEqual(row.live_entries, self.ENTRIES)

    def test_entry_rows_are_untouched(self):
        """Seeded after the base rows so the entry FK exists; asserts the data
        migration never reaches into the child table."""
        ComparisonToolEntry = self.new_apps.get_model("compare", "ComparisonToolEntry")
        self.assertEqual(ComparisonToolEntry.objects.count(), 0)
