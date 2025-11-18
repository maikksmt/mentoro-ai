from django.db.models import Prefetch, Q
from django.http import Http404
from django.urls import reverse
from django.utils.translation import gettext as _, get_language
from django.views.generic import ListView, DetailView

from core.seo.utils import absolute_url, localized_alternates
from core.services import related_guides, to_teaser_item
from core.views import SeoMixin
from .models import Guide, GuideSection, GuideItem


class GuideListView(ListView, SeoMixin):
    paginate_by = 20
    template_name = "guides/guide_list.html"
    context_object_name = "object_list"

    def get_queryset(self):
        lang = get_language()
        return (
            Guide.objects
            .visible_on_site()
            .active_translations(lang)
            .exclude(translations__slug__startswith="start-guide")
            .select_related("author", "reviewed_by")
            .prefetch_related("categories__translations", "tools__translations")
            .distinct()
            .order_by("-published_at", "-updated_at")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        canonical = absolute_url(self.request.path)
        alts = localized_alternates(self.request, "guides:list")
        ctx["seo"] = self.build_seo(
            self.request,
            title=_("Guides · MentoroAI"),
            description=_("Discover AI guides with step-by-step instructions."),
            canonical=canonical,
            alternates=alts,
            json_ld={
                "@context": "https://schema.org",
                "@type": "CollectionPage",
                "name": "Guides",
                "url": canonical,
                "inLanguage": get_language(),
            },
        )
        ctx["crumbs"] = [(_("Guides"), reverse("guides:list"))]
        return ctx


class GuideDetailView(DetailView, SeoMixin):
    model = Guide
    template_name = "guides/guide_detail.html"
    context_object_name = "object"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_object(self, queryset=None):
        slug = self.kwargs["slug"]
        obj = (
            Guide.objects
            .filter(Q(translations__public_slug=slug) | Q(translations__slug=slug))
            .distinct()
            .first()
        )
        if obj:
            return obj

        for g in Guide.objects.all():
            live = g.live_i18n or {}
            for data in live.values():
                if data.get("public_slug") == slug or data.get("slug") == slug:
                    return g
        raise Http404

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj: Guide = ctx["object"]
        title = f"{obj.title} · MentoroAI"
        desc = (obj.intro or obj.body or obj.title)[:155]
        canonical = absolute_url(self.request.path)
        og_img = getattr(obj, "hero_image_url", None)
        alts = localized_alternates(self.request, "guides:detail", {"slug": obj.slug})
        json_ld = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": obj.title,
            "description": desc,
            "inLanguage": get_language(),
            "mainEntityOfPage": canonical,
            "url": canonical,
        }
        if og_img:
            json_ld["image"] = [og_img]

        ctx["seo"] = self.build_seo(
            self.request,
            title=title,
            description=desc,
            canonical=canonical,
            og_image=og_img,
            alternates=alts,
            json_ld=json_ld,
        )
        ctx["display_title"] = obj.display_title
        ctx["display_intro"] = obj.display_intro
        ctx["display_body"] = obj.display_body
        rel_qs = related_guides(obj, limit=3)
        ctx["related_guides"] = [to_teaser_item(g, "guide") for g in rel_qs]
        ctx["crumbs"] = [
            (_("Guides"), reverse("guides:list")),
            (obj.display_title, self.request.path),
        ]
        return ctx

    def get_queryset(self):
        lang = get_language()
        return (
            Guide.objects
            .active_translations(lang)
            .select_related("author")
            .prefetch_related(
                "categories__translations",
                "tools__translations",
                Prefetch(
                    "sections",
                    queryset=(
                        GuideSection.objects
                        .active_translations(lang)
                        .order_by("order")
                        .prefetch_related(
                            Prefetch(
                                "items",
                                queryset=(
                                    GuideItem.objects
                                    .active_translations(lang)
                                    .filter(is_published=True)
                                    .order_by("order")
                                    .distinct()
                                )
                            )
                        )
                        .distinct()
                    )
                )
            )
            .distinct()
        )
