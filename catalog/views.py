from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, get_language
from django.views.generic import ListView, DetailView

from core.seo.utils import absolute_url, localized_alternates
from core.views import SeoMixin
from .models import Tool


class ToolListView(ListView, SeoMixin):
    model = Tool
    template_name = "catalog/tool_list.html"
    context_object_name = "object_list"
    paginate_by = 20

    def get_queryset(self):
        q = self.request.GET.get("q") or ""
        lang = get_language()
        free = self.request.GET.get("free") or ""

        qs = (
            Tool.objects.all().language(lang)
            .prefetch_related("categories", "translations", "categories__translations")
            .filter(published_at__isnull=False, published_at__lte=timezone.now())
        )

        if q:
            qs = qs.filter(
                Q(translations__name__icontains=q)
                | Q(translations__short_description__icontains=q)
                | Q(translations__long_description__icontains=q)
            )

        if free == "1":
            if hasattr(Tool, "free_tier"):
                qs = qs.filter(free_tier=True)
        qs = qs.distinct()
        if hasattr(Tool, "updated_at"):
            qs = qs.order_by("-updated_at")
        elif hasattr(Tool, "created_at"):
            qs = qs.order_by("-created_at")
        else:
            qs = qs.order_by("pk")

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = self.request.GET.get("q") or ""
        free = self.request.GET.get("free") == "1"
        canonical = absolute_url(self.request.path)
        alts = localized_alternates(self.request, "catalog:list")
        ctx["seo"] = self.build_seo(
            self.request,
            title=_("Tools · MentoroAI"),
            description=_("Filter, compare and discover AI tools."),
            canonical=canonical,
            alternates=alts,
            json_ld={
                "@context": "https://schema.org",
                "@type": "CollectionPage",
                "name": "Tools",
                "url": canonical,
                "inLanguage": get_language(),
            },
        )

        ctx.update(
            {
                "q": q,
                "free": free,
                "crumbs": [
                    (_("Catalog"), reverse("catalog:list")),
                    (_("All tools"), self.request.path),
                ],
            }
        )
        return ctx


class ToolDetailView(DetailView, SeoMixin):
    model = Tool
    template_name = "catalog/tool_detail.html"
    context_object_name = "object"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def _related_tools(self, obj: Tool):
        lang = get_language()
        qs = Tool.objects.language(lang).exclude(pk=obj.pk)
        qs = qs.filter(
            published_at__isnull=False,
            published_at__lte=timezone.now(),
            categories__in=obj.categories.all(),
        )
        return qs.distinct()[:3]

    def get_object(self, queryset=None):
        slug = self.kwargs["slug"]
        lang = get_language()
        obj = (
            Tool.objects
            .language(lang)
            .filter(Q(translations__slug=slug))
            .distinct()
            .first()
        )
        if obj:
            return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj: Tool = ctx["object"]

        title = f"{obj.name} · MentoroAI"
        desc = (obj.short_description or obj.long_description or obj.name)[:155]
        canonical = absolute_url(self.request.path)
        og_img = getattr(obj, "hero_image_url", None)
        alts = localized_alternates(self.request, "catalog:detail", {"slug": obj.slug})
        json_ld = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": obj.name,
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

        ctx.update(
            {
                "related_tools": self._related_tools(obj),
                "crumbs": [
                    (_("Catalog"), reverse("catalog:list")),
                    (_("All tools"), reverse("catalog:list")),
                    (obj.safe_translation_getter("name", any_language=True), self.request.path),
                ],
            }
        )
        return ctx


# TODO: remove old unused function based views
def tool_list(request):
    lang = get_language()
    q = request.GET.get("q") or ""
    free = request.GET.get("free") or ""
    qs = (
        Tool.objects.all().language(lang)
        .prefetch_related("categories", "translations", "categories__translations")
        .filter(published_at__isnull=False, published_at__lte=timezone.now())
    )

    if q:
        qs = qs.filter(
            Q(translations__slug__icontains=q) |
            Q(translations__name__icontains=q) |
            Q(translations__short_description__icontains=q) |
            Q(translations__long_description__icontains=q)
        )

    if free == "1":
        qs = qs.filter(free_tier=True)

    qs = qs.order_by("-is_featured", "translations__name")
    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "q": q or "",
        "free": free == "1",
        "seo_title": _("AI tools at a glance"),
        "seo_description": _("All AI tools at a glance – filterable and sortable."),
        "crumbs": [
            (_("Catalog"),
             reverse("catalog:list") if "catalog:list" in request.resolver_match.namespaces else "/",),
            (_("All tools"), request.path),
        ],
    }
    return render(request, "catalog/tool_list.html", context)


def tool_detail(request, slug):
    lang = get_language() or "en"
    qs = (Tool.objects.language(lang)
          .prefetch_related("translations", "categories", "categories__translations", "pricing", "affiliates", )
          .filter(published_at__isnull=False, published_at__lte=timezone.now()))
    obj = get_object_or_404(qs, translations__slug=slug)

    related_tools = (
        Tool.objects
        .language(lang)
        .filter(
            published_at__isnull=False,
            published_at__lte=timezone.now(),
            categories__in=obj.categories.all(),
        )
        .exclude(pk=obj.pk)
        .distinct()
        .order_by("-is_featured", "translations__name")[:6]
    )

    title = obj.short_description or _("Overview of features, prices and alternatives")

    context = {
        "object": obj,
        "related_tools": related_tools,
        "seo_title": title,
        "seo_description": title,
        "crumbs": [
            (_("Catalog"), reverse("catalog:list")),
            (_("All tools"), reverse("catalog:list")),
            (obj.safe_translation_getter("name", any_language=True), request.path),
        ],
    }
    return render(request, "catalog/tool_detail.html", context)
