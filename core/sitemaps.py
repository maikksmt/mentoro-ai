# core/sitemaps.py (Pfad an dein Projekt anpassen)

from django.contrib.sitemaps import Sitemap
from django.utils import timezone
from django.utils.translation import get_language

from catalog.models import Tool
from compare.models import Comparison
from glossary.models import GlossaryTerm
from guides.models import Guide
from prompts.models import Prompt
from usecases.models import UseCase

DEFAULT_LANG = "de"


class BasePublishableSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def lastmod(self, obj):
        for field in (
                "last_published_at",
                "updated_at",
                "modified",
                "created",
                "created_at",
        ):
            value = getattr(obj, field, None)
            if value:
                return value
        return timezone.now()

    def location(self, obj):
        return obj.get_absolute_url()


class GuideSitemap(BasePublishableSitemap):
    def items(self):
        manager = getattr(Guide, "published", None)
        return (manager or Guide.objects).all()


class PromptSitemap(BasePublishableSitemap):
    def items(self):
        manager = getattr(Prompt, "published", None)
        return (manager or Prompt.objects).all()


class UseCaseSitemap(BasePublishableSitemap):
    def items(self):
        manager = getattr(UseCase, "published", None)
        return (manager or UseCase.objects).all()


class ComparisonSitemap(BasePublishableSitemap):
    def items(self):
        manager = getattr(Comparison, "published", None)
        return (manager or Comparison.objects).all()


class ToolSitemap(BasePublishableSitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        manager = getattr(Tool, "published", None)
        return (manager or Tool.objects).all()


class GlossaryIndexSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.6

    def items(self):
        # Dummy-Item, URL wird nur aus Sprache gebaut
        return ["index"]

    def location(self, item):
        lang = get_language() or DEFAULT_LANG
        return f"/{lang}/glossary/"


class GlossaryTermSitemap(BasePublishableSitemap):
    priority = 0.7

    def items(self):
        lang = get_language() or DEFAULT_LANG
        manager = getattr(GlossaryTerm, "published", None)
        qs = (manager or GlossaryTerm.objects).filter(language=lang)
        return qs


class LegalSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.3

    def items(self):
        # Suffixe relativ zu /<lang>/legal/
        return ["legal", "privacy", "cookies", "terms", "copyright"]

    def location(self, item):
        lang = get_language() or DEFAULT_LANG
        # -> /en/legal/privacy/, /de/legal/privacy/ etc.
        return f"/{lang}/legal/{item}/"
