from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.translation import gettext as _, get_language
from django.urls import reverse
from django.views.generic import ListView, DetailView

from core.seo.utils import absolute_url, localized_alternates
from core.views import SeoMixin
from .models import Comparison
from catalog.models import Category


class ComparisonListView(ListView, SeoMixin):
    model = Comparison
    template_name = "compare/index.html"
    context_object_name = "objects"
    paginate_by = 12

    def get_queryset(self):
        qs = Comparison.published.language().prefetch_related("tools", "tools__categories")
        cat = self.request.GET.get("category") or self.request.GET.get("cat")
        if cat:
            qs = qs.filter(
                Q(tools__categories__translations__slug=cat)
                | Q(tools__categories__pk__iexact=cat)
            ).distinct()

        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(
                Q(translations__title__icontains=q)
                | Q(translations__slug__icontains=q)
                | Q(translations__public_slug__icontains=q)
                | Q(tools__translations__name__icontains=q)
            ).distinct()

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        lang = get_language()
        q = self.request.GET.get("q", "").strip()
        category = self.request.GET.get("category")
        available_categories = (
            Category.objects.filter(
                tools__comparisons__in=ctx["object_list"]
            )
            .active_translations(lang)
            .distinct()
            .order_by("translations__name")
        )

        canonical = absolute_url(self.request.path)
        alts = localized_alternates(self.request, "compare:index")
        ctx["seo"] = self.build_seo(
            self.request,
            title=_("Comparisons · MentoroAI"),
            description=_("Comparisons of AI tools based on criteria such as price, functionality, and quality."),
            canonical=canonical,
            alternates=alts,
            json_ld={
                "@context": "https://schema.org",
                "@type": "CollectionPage",
                "name": "Comparison",
                "url": canonical,
                "inLanguage": get_language(),
            },
        )
        ctx.update({
            "crumbs": [
                (_("Comparisons"), self.request.path),
            ],
            "q": q or "",
            "category": category or "",
            "available_categories": available_categories,
        })
        return ctx


class ComparisonDetailView(DetailView, SeoMixin):
    model = Comparison
    template_name = "compare/detail.html"
    context_object_name = "object"

    def get_queryset(self):
        return Comparison.objects.language().prefetch_related("tools", "tools__categories")

    def get_object(self, queryset=None):
        slug = self.kwargs.get("slug")
        qs = queryset or self.get_queryset()

        obj = qs.filter(Q(translations__slug=slug)).distinct().first()

        if not obj:
            obj = get_object_or_404(
                Comparison.objects.prefetch_related("tools", "tools__categories"),
                Q(translations__slug=slug)
            )
        return obj

    def _build_score_rows(self, obj):
        sb = getattr(obj, "score_breakdown", None)
        if not sb:
            return []

        if isinstance(sb, dict):
            return [{"key": k, "value": v} for k, v in sb.items()]
        if isinstance(sb, list):
            rows = []
            for item in sb:
                if isinstance(item, dict):
                    key = item.get("key") or item.get("name") or item.get("title")
                    value = item.get("value") or item.get("score")
                    rows.append({"key": key, "value": value})
                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    rows.append({"key": item[0], "value": item[1]})
            return rows
        return []

    def _related(self, obj):
        tools = getattr(obj, "tools", None)
        if not tools:
            return []
        tool_ids = list(tools.values_list("pk", flat=True))
        if not tool_ids:
            return []
        return (
            self.get_queryset()
            .filter(tools__in=tool_ids)
            .exclude(pk=obj.pk)
            .distinct()[:3]
        )

    def _categories_for_object(self, obj):
        try:
            return (
                Category.objects.language()
                .filter(tools__in=obj.tools.all())
                .distinct()
                .order_by("translations__name")
            )
        except Exception:
            return (
                Category.objects.filter(tools__in=obj.tools.all())
                .distinct()
                .order_by("name")
            )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj: Comparison = ctx["object"]
        title = f"{obj.title} · MentoroAI"
        desc = (obj.intro or obj.title)[:155]
        canonical = absolute_url(self.request.path)
        og_img = getattr(obj, "hero_image_url", None)
        alts = localized_alternates(self.request, "compare:detail", {"slug": obj.slug})
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

        ctx.update({
            "categories": self._categories_for_object(obj),
            "tools_list": list(getattr(obj, "tools").all()) if getattr(obj, "tools", None) else [],
            "score_rows": self._build_score_rows(obj),
            "related": self._related(obj),

            "crumbs": [
                (_("Comparisons"), reverse("compare:index")),
                (title, self.request.path),
            ],
        })
        return ctx


def index(request):
    """
    Displays all published comparisons, optionally filtered by category or search query;
    provides pagination and language-specific context.
    """
    qs = Comparison.objects.language().prefetch_related("tools", "tools__categories")

    q = request.GET.get("q", "").strip()
    category = request.GET.get("category")

    if q:
        qs = qs.filter(Q(translations__title__icontains=q) | Q(translations__intro__icontains=q))
    if category:
        qs = qs.filter(tools__categories__slug=category)

    paginator = Paginator(qs.order_by("-id"), 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    lang = get_language()
    available_categories = Category.objects.all().active_translations(lang).order_by('translations__name')

    context = {
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "q": q or "",
        "category": category or "",
        "available_categories": available_categories,
        "seo_title": _("Tool comparisons"),
        "seo_description": _(
            "Comparisons of AI tools based on criteria such as price, functionality, and quality."
        ),
        "crumbs": [
            (_("Comparisons"), request.path),
        ],
    }
    return render(request, "compare/index.html", context)


def detail(request, slug):
    """
    Retrieves a single comparison by slug, prefetches related tools, features, and entries,
    and builds a feature-tool matrix for rendering.
    """
    lang = get_language()
    qs = Comparison.objects.prefetch_related("tools", "tools__categories")
    obj = get_object_or_404(qs, translations__slug=slug)
    categories = (
        Category.objects.filter(tools__comparisons=obj).distinct().order_by("translations__name"))
    tools_list = list(obj.tools.all())
    score_rows = []

    if obj.score_breakdown:
        for criterion, per_tool in obj.score_breakdown.items():
            row = [per_tool.get(t.name) for t in tools_list]
            score_rows.append((criterion, row))
    related = (Comparison.objects.language(lang).exclude(pk=obj.pk).order_by("-created_at")[:6])

    context = {
        "object": obj,
        "categories": categories,
        "tools_list": tools_list,
        "score_rows": score_rows,
        "related": related,
        "seo_title": _("Comparisons"),
        "seo_description": _("Discover side-by-side tool comparisons."),
        "crumbs": [
            (_("Comparisons"), reverse("compare:index")),
            (obj.safe_translation_getter("title", any_language=True), request.path),
        ],
    }
    return render(request, "compare/detail.html", context)
