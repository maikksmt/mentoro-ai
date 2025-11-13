from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language

from catalog.models import Tool
from compare.models import Comparison
from guides.models import Guide
from prompts.models import Prompt
from usecases.models import UseCase
from glossary.models import GlossaryTerm

DEFAULT_LANG = "de"


class _BasePublishableSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or getattr(obj, "published_at", None) or timezone.now()


class GuideSitemap(_BasePublishableSitemap):
    def items(self):
        return Guide.published.all()

    def location(self, obj):
        return obj.get_absolute_url()


class PromptSitemap(_BasePublishableSitemap):
    def items(self):
        return Prompt.published.all().order_by("pk")

    def location(self, obj):
        return obj.get_absolute_url()


class UseCaseSitemap(_BasePublishableSitemap):
    def items(self):
        return UseCase.published.all().order_by("pk")

    def location(self, obj):
        return obj.get_absolute_url()


class ComparisonSitemap(_BasePublishableSitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return Comparison.published.all().order_by("pk")

    def location(self, obj):
        return f"/compare/{obj.slug}/"


class ToolSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        lang = get_language()
        return (Tool.objects.language(lang)
                .filter(published_at__isnull=False, published_at__lte=timezone.now(), )
                .translated(lang)
                )

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None)

    def location(self, obj):
        return obj.get_absolute_url()


class GlossaryIndexSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.6

    def items(self):
        return ["glossary:list"]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        latest = GlossaryTerm.objects.order_by("-updated_at").first()
        return latest.updated_at if latest else None


class GlossaryDetailSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return GlossaryTerm.objects.all().only("slug", "language", "updated_at")

    def location(self, obj: GlossaryTerm):
        base = reverse("glossary:detail", kwargs={"slug": obj.slug})
        if obj.language and obj.language.lower() != DEFAULT_LANG:
            return f"{base}?lang={obj.language.lower()}"
        return base

    def lastmod(self, obj: GlossaryTerm):
        return obj.updated_at


class LegalStaticSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.3

    def items(self):
        return [
            "/en/legal/legal/",
            "/en/legal/privacy/",
            "/en/legal/cookies/",
            "/en/legal/terms/",
            "/en/legal/copyright/",
        ]

    def location(self, item):
        return item
