from typing import Any, Dict, Optional

from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse, Http404
from django.urls import reverse
from django.utils.translation import gettext as _, get_language
from django.views.generic import DetailView, ListView

from core.seo.utils import absolute_url, localized_alternates
from core.services import to_teaser_item, related_prompts
from core.views import SeoMixin
from .models import Prompt


def _resolve_by_slug(qs: QuerySet[Prompt], slug: str) -> Optional[Prompt]:
    obj = (
        qs.filter(Q(translations__public_slug=slug) | Q(translations__slug=slug))
        .distinct()
        .first()
    )
    if obj:
        return obj

    live_keysets = (p for p in qs)
    for p in live_keysets:
        live = getattr(p, "live_i18n", None) or {}
        for data in live.values():
            if data.get("public_slug") == slug or data.get("slug") == slug:
                return p
    return None


class PromptListView(ListView, SeoMixin):
    model = Prompt
    template_name = "prompts/prompt_list.html"
    context_object_name = "object_list"
    paginate_by = 20

    def get_queryset(self) -> QuerySet[Prompt]:
        qs = (
            Prompt.objects
            .visible_on_site()
            .select_related("author", "reviewer")
        )
        if not qs.ordered:
            qs = qs.order_by("-published_at", "-updated_at")
        return qs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        canonical = absolute_url(self.request.path)
        alts = localized_alternates(self.request, "guides:list")
        ctx["seo"] = self.build_seo(
            self.request,
            title=_("Prompts · MentoroAI"),
            description=_("Curated AI prompts with review/publish workflow."),
            canonical=canonical,
            alternates=alts,
            json_ld={
                "@context": "https://schema.org",
                "@type": "CollectionPage",
                "name": "Prompts",
                "url": canonical,
                "inLanguage": get_language(),
            },
        )
        ctx["crumbs"] = [
            (_("Prompts"), self.request.path),
        ]
        return ctx


class PromptDetailView(DetailView, SeoMixin):
    model = Prompt
    template_name = "prompts/prompt_detail.html"
    context_object_name = "object"

    def get_queryset(self) -> QuerySet[Prompt]:
        return Prompt.objects.all().select_related("author", "reviewer")

    def get_object(self, queryset: Optional[QuerySet[Prompt]] = None) -> Prompt:
        slug = self.kwargs.get("slug")
        if not slug:
            raise Http404("Missing slug.")
        qs = queryset or self.get_queryset()
        obj = _resolve_by_slug(qs, slug)
        if not obj:
            raise Http404("Prompt not found.")
        return obj

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        obj: Prompt = ctx["object"]
        title = f"{obj.title} · MentoroAI"
        desc = (obj.intro or obj.body or obj.title)[:155]
        canonical = absolute_url(self.request.path)
        og_img = getattr(obj, "hero_image_url", None)
        alts = localized_alternates(self.request, "prompts:detail", {"slug": obj.slug})
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
        ctx.setdefault("display_title", obj.display_title)
        ctx.setdefault("display_intro", obj.display_intro)
        ctx.setdefault("display_body", obj.display_body)
        ctx.setdefault("display_outro", obj.display_outro)

        rel_qs = related_prompts(obj, limit=3)
        ctx["more"] = [to_teaser_item(p, "prompt") for p in rel_qs]

        ctx["crumbs"] = [
            (_("Prompts"), reverse("prompts:list")),
            (obj.display_title or _("Prompt"), self.request.path),
        ]
        return ctx


def prompt_list(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
    return PromptListView.as_view()(request, *args, **kwargs)


def prompt_detail(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
    return PromptDetailView.as_view()(request, *args, **kwargs)
