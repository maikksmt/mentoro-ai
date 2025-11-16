from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, get_language
from parler.models import TranslatableModel, TranslatedFields
from parler.utils.context import switch_language
from taggit.managers import TaggableManager

from catalog.models import Tool
from core.models.editorial import (
    EditorialMixin,
    EditorialWorkflowMixin,
)


class Prompt(EditorialMixin, TranslatableModel, EditorialWorkflowMixin):
    LIVE_SNAPSHOT_FIELDS = ("slug", "public_slug", "title", "intro", "body", "outro")
    live_i18n = models.JSONField(default=dict, blank=True)
    translations = TranslatedFields(
        title=models.CharField(_("Title"), max_length=200),
        intro=models.TextField(_("Intro"), blank=True),
        body=models.TextField(_("Body"), blank=True),
        outro=models.TextField(_("Outro"), blank=True),
        slug=models.SlugField(_("Slug"), max_length=220, unique=True),
        public_slug=models.SlugField(_("Public slug"), max_length=220, unique=True, null=True, blank=True),
    )
    tools = models.ManyToManyField(Tool, related_name="prompts", blank=True)
    tags = TaggableManager(blank=True)

    class Meta:
        verbose_name = _("Prompt")
        verbose_name_plural = _("Prompts")

    def __str__(self):
        return self.safe_translation_getter("title", any_language=True) or f"Prompt #{self.pk}"

    def _current_values_for(self, lang: str) -> dict:
        with switch_language(self, lang):
            get = self.safe_translation_getter
            return {
                "slug": get("slug"),
                "public_slug": get("public_slug"),
                "title": get("title"),
                "intro": get("intro"),
                "body": get("body"),
                "outro": get("outro"),
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
    def display_intro(self):
        return self.get_display_value("intro")

    @property
    def display_body(self):
        return self.get_display_value("body")

    @property
    def display_outro(self):
        return self.get_display_value("outro")

    def get_absolute_url(self, language: str | None = None):
        lang = language or get_language()
        live_slug = self.get_live_value("public_slug", lang) or self.get_live_value("slug", lang)
        if live_slug:
            return reverse("prompts:detail", kwargs={"slug": live_slug})

        curr = self._current_values_for(lang)
        slug = curr.get("public_slug") or curr.get("slug")
        if slug:
            return reverse("prompts:detail", kwargs={"slug": slug})

        for lng in getattr(self, "get_available_languages", lambda: [])():
            curr = self._current_values_for(lng)
            slug = curr.get("public_slug") or curr.get("slug")
            if slug:
                return reverse("prompts:detail", kwargs={"slug": slug})
        return "#"

    def on_after_publish(self):
        self.is_published = True
        if not self.published_at:
            self.published_at = timezone.now()
        for lang in self.get_available_languages():
            with switch_language(self, lang):
                if self.slug and self.public_slug != self.slug:
                    self.public_slug = self.slug
