from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, get_language
from parler.models import TranslatableModel, TranslatedFields
from parler.utils.context import switch_language

from catalog.models import Tool
from core.models.editorial import (
    EditorialMixin,
    EditorialManager,
    PublishedOnlyManager, EditorialWorkflowMixin,
)


class UseCase(EditorialMixin, TranslatableModel, EditorialWorkflowMixin):
    LIVE_SNAPSHOT_FIELDS = ("slug", "public_slug", "title", "intro", "body", "outro")
    live_i18n = models.JSONField(default=dict, blank=True)
    translations = TranslatedFields(
        title=models.CharField(_("Title"), max_length=200),
        intro=models.TextField(_("Intro"), blank=True),
        body=models.TextField(_("Body"), blank=True),
        outro=models.TextField(_("Outro"), blank=True),
        slug=models.SlugField(_("Slug"), max_length=220, unique=True),
        public_slug=models.SlugField(_("Public slug"), max_length=220, unique=True, null=True, blank=True),
        persona=models.CharField(_("Persona"), max_length=100),
    )

    tools = models.ManyToManyField(Tool, related_name="usecases", blank=True)
    objects = EditorialManager()
    published = PublishedOnlyManager()

    class Meta:
        verbose_name = _("Usecase")
        verbose_name_plural = _("Usecases")

    def __str__(self) -> str:
        return self.safe_translation_getter("title", any_language=True) or f"UseCase #{self.pk}"

    def get_live_value(self, field: str, language: str | None = None):
        """Liest den Wert aus dem Live-Snapshot (live_i18n) für die angegebene Sprache."""
        lang = language or get_language()
        return (self.live_i18n or {}).get(lang, {}).get(field)

    def _current_values_for(self, language: str):
        """Gibt die aktuellen Übersetzungswerte (Draft) für eine Sprache zurück."""
        with switch_language(self, language):
            get = self.safe_translation_getter
            return {
                "slug": get("slug"),
                "public_slug": get("public_slug"),
                "title": get("title"),
                "intro": get("intro"),
                "body": get("body"),
                "outro": get("outro"),
                "persona": get("persona"),
            }

    def get_display_value(self, field: str, language: str | None = None):
        lang = language or get_language()
        val = self.get_live_value(field, lang)
        if val:
            return val
        return self._current_values_for(lang).get(field)

    @property
    def display_title(self):
        return self.get_display_value("title")

    @property
    def display_intro(self):
        return self.get_display_value("intro")

    @property
    def display_body(self):
        return self.get_display_value("body")

    @property
    def display_outro(self):
        return self.get_display_value("outro")

    @property
    def display_persona(self):
        return self.get_display_value("persona")

    def on_after_publish(self):
        self.is_published = True
        if not self.published_at:
            self.published_at = timezone.now()

        live = dict(self.live_i18n or {})

        for lang in self.get_available_languages():
            with switch_language(self, lang):
                if self.slug and self.public_slug != self.slug:
                    self.public_slug = self.slug

                snap = live.get(lang, {})
                for f in self.LIVE_SNAPSHOT_FIELDS:
                    snap[f] = getattr(self, f, None)
                live[lang] = snap

        self.live_i18n = live

    def get_absolute_url(self, language: str | None = None):
        lang = language or get_language()
        live = (self.live_i18n or {}).get(lang or "", {})
        slug = live.get("public_slug") or live.get("slug")
        if not slug:
            from parler.utils.context import switch_language
            with switch_language(self, lang):
                slug = self.safe_translation_getter("public_slug") or self.safe_translation_getter("slug")
        return reverse("usecases:detail", kwargs={"slug": slug})
