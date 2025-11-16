from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _, get_language
from parler.models import TranslatableModel, TranslatedFields
from parler.utils.context import switch_language

from catalog.models import Category, Tool
from core.models.editorial import EditorialMixin, EditorialWorkflowMixin


class Guide(EditorialMixin, TranslatableModel, EditorialWorkflowMixin):
    live_i18n = models.JSONField(default=dict, blank=True)
    LIVE_SNAPSHOT_FIELDS = ("slug", "public_slug", "title", "intro", "body")
    translations = TranslatedFields(
        title=models.CharField(_("Title"), max_length=200),
        intro=models.TextField(_("Intro"), blank=True),
        body=models.TextField(_("Body"), blank=True),
        slug=models.SlugField(_("Slug"), max_length=220, unique=True),
        public_slug=models.SlugField(_("Public slug"), max_length=220, unique=True, null=True, blank=True),
    )
    categories = models.ManyToManyField(Category, blank=True)
    tools = models.ManyToManyField(Tool, blank=True)

    class Meta:
        verbose_name = _("Guide")
        verbose_name_plural = _("Guides")

    def __str__(self):
        return self.safe_translation_getter("title", any_language=True) or f"Guide #{self.pk}"

    def _current_values_for(self, lang: str) -> dict:
        """Liest die aktuellen (Draft/DB) Werte sicher in einer Sprache aus."""
        with switch_language(self, lang):
            return {
                "slug": self.safe_translation_getter("slug"),
                "public_slug": self.safe_translation_getter("public_slug"),
                "title": self.safe_translation_getter("title"),
                "intro": self.safe_translation_getter("intro"),
                "body": self.safe_translation_getter("body"),
            }

    def get_live_value(self, field: str, language: str | None = None) -> str | None:
        lang = language or get_language()
        return (self.live_i18n or {}).get(lang, {}).get(field)

    def get_display_value(self, field: str, language: str | None = None) -> str | None:
        """
        Bevorzugt Live-Snapshot (wenn vorhanden), sonst aktuelle Draft-Werte.
        So bleibt die Liste stabil während Review.
        """
        lang = language or get_language()
        live = self.get_live_value(field, lang)
        if live:
            return live
        # Fallback auf aktuelle DB/Draft
        return self._current_values_for(lang).get(field)

    def get_absolute_url(self, language: str | None = None):
        lang = language or get_language()
        live_slug = self.get_live_value("public_slug", lang) or self.get_live_value("slug", lang)
        if live_slug:
            return reverse("guides:detail", kwargs={"slug": live_slug})
        curr = self._current_values_for(lang)
        slug = curr.get("public_slug") or curr.get("slug")
        if slug:
            return reverse("guides:detail", kwargs={"slug": slug})
        for lng in self.get_available_languages():
            curr = self._current_values_for(lng)
            slug = curr.get("public_slug") or curr.get("slug")
            if slug:
                return reverse("guides:detail", kwargs={"slug": slug})

        return "#"

    def on_after_publish(self):
        self.is_published = True
        for lang in self.get_available_languages():
            with switch_language(self, lang):
                if self.slug and self.public_slug != self.slug:
                    self.public_slug = self.slug
        try:
            sections = self.sections.all()
        except Exception:
            sections = []

        for section in sections:
            if not hasattr(section, "get_available_languages"):
                continue

            live = {}
            for lang in section.get_available_languages():
                curr = section._current_values_for(lang)
                live[lang] = {fname: curr.get(fname) for fname in getattr(section, "SECTION_LIVE_FIELDS", ())}

            section.live_i18n = live
            try:
                section.save(update_fields=["live_i18n"])
            except Exception:
                pass

    @property
    def display_title(self):
        return self.get_display_value("title")

    @property
    def display_intro(self):
        return self.get_display_value("intro")

    @property
    def display_body(self):
        return self.get_display_value("body")


class GuideSection(TranslatableModel):
    guide = models.ForeignKey(Guide, on_delete=models.CASCADE, related_name="sections")
    order = models.PositiveIntegerField(default=0)
    live_i18n = models.JSONField(default=dict, blank=True)
    SECTION_LIVE_FIELDS = ("title", "body")

    translations = TranslatedFields(
        title=models.CharField(_("Title"), max_length=200),
        body=models.TextField(_("Body"), blank=True),
    )

    class Meta:
        ordering = ["order", "id"]
        verbose_name = _("Guide Section")
        verbose_name_plural = _("Guide Sections")
        constraints = [
            models.UniqueConstraint(fields=["guide", "order"], name="guidesection_order_unique_per_guide")
        ]

    def __str__(self):
        t = getattr(self, "title", "") or "(untitled)"
        return f"{self.guide_id} · {self.order} · {t}"

    def _current_values_for(self, lang: str) -> dict:
        with switch_language(self, lang):
            return {
                "title": self.safe_translation_getter("title"),
                "body": self.safe_translation_getter("body"),
            }

    def get_live_value(self, field: str, language: str | None = None):
        lang = language or get_language()
        return (self.live_i18n or {}).get(lang, {}).get(field)

    def get_display_value(self, field: str, language: str | None = None):
        val = self.get_live_value(field, language)
        if val:
            return val
        lang = language or get_language()
        return self._current_values_for(lang).get(field)

    @property
    def display_title(self):
        return self.get_display_value("title")

    @property
    def display_body(self):
        return self.get_display_value("body")


CONTENT_KIND_CHOICES = (
    ("guide", "Guide"),
    ("prompt", "Prompt"),
    ("usecase", "UseCase"),
    ("tool", "Tool"),
    ("comparison", "Comparison"),
)


class GuideItem(TranslatableModel):
    section = models.ForeignKey(GuideSection, on_delete=models.CASCADE, related_name="items")
    kind = models.CharField(max_length=20, choices=CONTENT_KIND_CHOICES, default="guide")
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to=(
                Q(app_label="guides", model="guide") |
                Q(app_label="prompts", model="prompt") |
                Q(app_label="usecases", model="usecase") |
                Q(app_label="catalog", model="tool") |
                Q(app_label="compare", model="comparison")
        ),
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    translations = TranslatedFields(
        title=models.CharField(_("Title"), max_length=200),
        teaser=models.TextField(_("Teaser"), blank=True),
    )

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]
        ordering = ["order", "id"]
        verbose_name = _("Guide Item")
        verbose_name_plural = _("Guide Items")

    def __str__(self):
        return f"{self.kind} item #{self.pk}"

    def get_title(self):
        if getattr(self, "title", None):
            return self.title
        obj = self.content_object
        return (
                getattr(obj, "title", None)
                or getattr(obj, "name", None)
                or "Item"
        )

    def get_teaser(self):
        if getattr(self, "teaser", None):
            return self.teaser
        obj = self.content_object
        return (
                getattr(obj, "teaser", None)
                or getattr(obj, "body", None)
                or ""
        )

    def get_url(self):
        if self.url:
            return self.url
        obj = self.content_object
        if obj and hasattr(obj, "get_absolute_url"):
            return obj.get_absolute_url()
        return "#"

    def clean(self):
        from django.core.exceptions import ValidationError
        if not (self.content_type and self.object_id) and not self.url:
            raise ValidationError(_("Either content_object (content_type + object_id) OR a URL."))
