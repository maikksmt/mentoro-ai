# content/views/home.py
from django.utils.translation import gettext as _, get_language
from django.views.generic import TemplateView

from catalog.models import Tool
from core.seo.utils import absolute_url, localized_alternates
from core.services import (
    get_latest_items,
    related_guides,
    to_teaser_item,
)
from core.views import SeoMixin
from guides.models import Guide
from mentoroai import settings


def resolve_starter_guide_url(lang: str) -> str | None:
    slugs = getattr(settings, "START_GUIDE_PUBLIC_SLUGS", {
        "de": "start-guide-de",
        "en": "start-guide-en",
    })
    want = slugs.get(lang) or slugs.get("en")

    if not want:
        return None

    qs = Guide.objects.active_translations(lang)
    g = qs.filter(translations__public_slug=want).first()
    if not g:
        g = qs.filter(translations__slug=want).first()
    if not g or g.status == g.STATUS_ARCHIVED:
        return None

    return g.get_absolute_url(language=lang)


class HomePageView(TemplateView, SeoMixin):
    template_name = "content/home.html"

    def get_context_data(self, **kwargs):
        lang = (get_language() or "en")[:2]
        ctx = super().get_context_data(**kwargs)
        canonical = absolute_url(self.request.path)
        alts = localized_alternates(self.request, "guides:list")
        ctx["seo"] = self.build_seo(
            self.request,
            title=_("AI tools, guides & usecases for beginners and professionals · MentoroAI"),
            description=_("Understand AI tools and use them effectively"),
            canonical=canonical,
            alternates=alts,
            json_ld={
                "@context": "https://schema.org",
                "@type": "CollectionPage",
                "name": "Home",
                "url": canonical,
                "inLanguage": get_language(),
            },
        )
        ctx["start_guide_url"] = resolve_starter_guide_url(lang)
        ctx["latest_items"] = get_latest_items(limit=6)
        ctx["featured_tools"] = Tool.objects.filter(is_featured=True).order_by(
            "-published_at"
        )[:6]
        anchor = Guide.published.order_by("-published_at").first()
        ctx["recommended_items"] = (
            [to_teaser_item(g, "guide") for g in related_guides(anchor, limit=3)]
            if anchor
            else []
        )
        return ctx
