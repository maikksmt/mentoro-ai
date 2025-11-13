from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import get_language
from django_fsm import transition, FSMField
from parler.managers import TranslatableManager, TranslatableQuerySet
from parler.utils.context import switch_language


# -------- Manager --------

class EditorialQuerySet(TranslatableQuerySet):
    """
    Parler-aware queryset with convenience filters for every workflow state (drafts, in_review, rework, published)
    and a visible_on_site scope that exposes published plus review only if a live revision exists.
    """

    def drafts(self):
        return self.filter(status=EditorialWorkflowMixin.STATUS_DRAFT)

    def in_review(self):
        return self.filter(status=EditorialWorkflowMixin.STATUS_REVIEW)

    def rework(self):
        return self.filter(status=EditorialWorkflowMixin.STATUS_REWORK)

    def published(self):
        return self.filter(status=EditorialWorkflowMixin.STATUS_PUBLISHED)

    def visible_on_site(self):
        """
        Public visibility filter:
        includes published items and review items that already have a last_published_at/live revision,
        preventing premature exposure.
        """
        return self.filter(
            Q(status=EditorialWorkflowMixin.STATUS_PUBLISHED)
            | Q(
                status=EditorialWorkflowMixin.STATUS_REVIEW,
                last_published_revision_id__isnull=False,
            )
        )


class EditorialManager(TranslatableManager.from_queryset(EditorialQuerySet)):  # type: ignore
    """
    Translatable manager that exposes EditorialQuerySet; centralizes editorial filters for all content models.
    """
    pass


class PublishedOnlyManager(EditorialManager):
    """
    Manager that restricts queries to published items and to the active language;
    ideal for public pages where drafts must never leak.
    """

    def get_queryset(self):
        qs = super().get_queryset().published()
        # Parler: only active translations for actual language
        lang = get_language()
        qs = qs.active_translations(lang)
        return qs


# -------- Basemixin --------

class EditorialMixin(models.Model):
    """
    Abstract base with common editorial fields (author/reviewer, timestamps) shared by content models;
    keeps audit info consistent.
    """
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="%(class)s_authored",
        on_delete=models.SET_NULL, null=True, blank=True
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="%(class)s_reviewed",
        on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    objects = EditorialManager()
    published = PublishedOnlyManager()

    class Meta:
        abstract = True


# -------- Workflow --------

class EditorialWorkflowMixin(models.Model):
    """
    Abstract base implementing the finite-state machine (via django-fsm-2)
    for draft → review → (rework|published) plus archival;
    encapsulates transitions and side effects like snapshot updates.
    """
    STATUS_DRAFT = "draft"
    STATUS_REVIEW = "review"
    STATUS_REWORK = "rework"
    STATUS_PUBLISHED = "published"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_REVIEW, "Review"),
        (STATUS_REWORK, "Rework"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_ARCHIVED, "Archived"),
    ]
    LIVE_SNAPSHOT_FIELDS = ("slug", "public_slug", "title")

    status = FSMField(default=STATUS_DRAFT, choices=STATUS_CHOICES, protected=True)

    submitted_for_review_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    review_note = models.TextField(blank=True)

    last_published_revision_id = models.IntegerField(null=True, blank=True)

    def _update_live_snapshot(self) -> None:
        if not hasattr(self, "live_i18n"):
            return

        if not hasattr(self, "get_available_languages"):
            return

        live = {}
        for lang in self.get_available_languages():
            with switch_language(self, lang):
                entry = {}
                for fname in getattr(self, "LIVE_SNAPSHOT_FIELDS", ()):
                    if hasattr(self, "safe_translation_getter"):
                        entry[fname] = self.safe_translation_getter(fname)
                    else:
                        entry[fname] = None
                live[lang] = entry

        self.live_i18n = live
        try:
            self.save(update_fields=["live_i18n"])
        except Exception:
            pass

    class Meta:
        abstract = True

    # --- Transitions ---

    @transition(field='status', source=[STATUS_PUBLISHED], target=STATUS_REVIEW)
    def move_to_review(self, *, by=None, note: str | None = None):
        if note:
            try:
                self.review_note = note
            except Exception:
                pass

    @transition(field=status, source=[STATUS_DRAFT, STATUS_REWORK, STATUS_PUBLISHED], target=STATUS_REVIEW)
    def submit_for_review(self, *, by):
        self.submitted_for_review_at = timezone.now()

    @transition(field=status, source=STATUS_REVIEW, target=STATUS_REWORK)
    def request_rework(self, *, by, note=""):
        self.reviewed_at = timezone.now()
        self.reviewed_by = by
        self.review_note = note

    @transition(field=status, source=STATUS_REVIEW, target=STATUS_PUBLISHED)
    def publish(self, *, by, note=""):
        self.reviewed_at = timezone.now()
        self.published_at = timezone.now()
        self.reviewed_by = by
        if note:
            self.review_note = note
        self._update_live_snapshot()
        try:
            self.on_after_publish()
        except Exception:
            pass

    def on_after_publish(self) -> None:
        """
        Post-publish extension point for subclasses (e.g., cache busting, search indexing).
        """
        pass

    @transition(field=status, source="*", target=STATUS_ARCHIVED)
    def archive(self, *, by, note=""):
        """
        Soft-delete: marks content as archived without destroying history;
        excluded from public queries.
        """
        if note:
            self.review_note = note

    @transition(field=status, source=STATUS_ARCHIVED, target=STATUS_DRAFT)
    def restore(self, *, by, note=""):
        """
        Reverses archive to make content available to the workflow again.
        """
        if note:
            self.review_note = note
