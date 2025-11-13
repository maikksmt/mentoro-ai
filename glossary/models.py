import uuid

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class GlossaryTerm(models.Model):
    term = models.CharField(_("Term"), max_length=250, db_index=True)
    slug = models.SlugField(_("Slug"), max_length=150)  # kein unique!
    translation_group = models.UUIDField(default=uuid.uuid4, db_index=True, editable=True)
    short_definition = models.TextField(_("Short definition"))
    long_definition = models.TextField(_("Long definition"), blank=True)
    category = models.CharField(
        _("Category"), max_length=100, blank=True, db_index=True
    )
    language = models.CharField(
        _("Language"), max_length=50, default="en", db_index=True
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["term"]
        verbose_name = _("Glossary term")
        verbose_name_plural = _("Glossary terms")
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "language"],
                name="uniq_glossary_slug_language",
            ),
            models.UniqueConstraint(
                fields=["translation_group", "language"],
                name="uniq_glossary_group_language",
            ),
        ]

    def __str__(self):
        return self.term

    def get_absolute_url(self):
        return reverse("glossary:detail", kwargs={"slug": self.slug})
