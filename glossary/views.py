from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.views.generic import ListView, DetailView, View

from core.seo.utils import absolute_url, localized_alternates
from core.views import SeoMixin
from .models import GlossaryTerm
from django.utils.translation import gettext as _, get_language


class GlossaryListView(ListView, SeoMixin):
    model = GlossaryTerm
    template_name = "glossary/glossary_list.html"
    context_object_name = "terms"
    paginate_by = 30

    def get_queryset(self):
        lang = get_language() or "en"
        q = (self.request.GET.get("q") or "").strip()
        letter = (self.request.GET.get("letter") or "").strip()
        qs = GlossaryTerm.objects.filter(language=lang)
        if letter:
            qs = qs.filter(term__istartswith=letter)

        if q:
            qs = qs.filter(
                Q(term__icontains=q)
                | Q(short_definition__icontains=q)
                | Q(long_definition__icontains=q)
                | Q(category__icontains=q)
            )

        return qs.order_by("term", "pk")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        canonical = absolute_url(self.request.path)
        alts = localized_alternates(self.request, "glossary:list")
        ctx["seo"] = self.build_seo(
            self.request,
            title=_("Glossary · MentoroAI"),
            description=_("AI Glossary – Terms explained simply"),
            canonical=canonical,
            alternates=alts,
            json_ld={
                "@context": "https://schema.org",
                "@type": "CollectionPage",
                "name": "Glossary",
                "url": canonical,
                "inLanguage": get_language(),
            },
        )
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        ctx["letter"] = (self.request.GET.get("letter") or "").strip()
        ctx["letters"] = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
        return ctx


class GlossaryDetailView(DetailView, SeoMixin):
    model = GlossaryTerm
    template_name = "glossary/glossary_detail.html"
    context_object_name = "term"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        lang = get_language() or "en"
        return GlossaryTerm.objects.filter(language=lang)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj: GlossaryTerm = ctx["term"]
        title = f"{obj.term} · MentoroAI"
        desc = (obj.short_definition or obj.long_definition or obj.term)[:155]
        canonical = absolute_url(self.request.path)
        og_img = getattr(obj, "hero_image_url", None)
        alts = localized_alternates(self.request, "glossary:detail", {"slug": obj.slug})
        json_ld = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": obj.term,
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
        term = self.object
        siblings = (
            GlossaryTerm.objects
            .filter(translation_group=term.translation_group)
            .exclude(pk=term.pk).only("language", "slug"))
        ctx["alt_lang_terms"] = siblings
        return ctx


class GlossaryAutocompleteView(View):
    """
    HTMX-Endpoint: liefert nur das Result-Fragment (HTML),
    damit das Suchergebnis live unter dem Input erscheint.
    """
    template_name = "glossary/glossary_results.html"

    def get(self, request, *args, **kwargs):
        lang = get_language() or "en"
        q = (request.GET.get("q") or "").strip()
        letter = (request.GET.get("letter") or "").strip()
        qs = GlossaryTerm.objects.filter(language=lang)
        if letter:
            qs = qs.filter(term__istartswith=letter)
        if q:
            qs = qs.filter(Q(term__icontains=q) | Q(short_definition__icontains=q)).order_by("term")

        html = render_to_string(self.template_name, {"terms": qs[:20], "compact": True}, request=request)
        if (request.GET.get("format") or "").lower() == "json":
            data = [
                {
                    "id": t.id,
                    "term": t.term,
                    "slug": t.slug,
                    "short_definition": t.short_definition,
                    "category": t.category,
                    "language": t.language,
                    "updated_at": t.updated_at.isoformat() if hasattr(t, "updated_at") and t.updated_at else None,
                }
                for t in qs[:50]
            ]
            return JsonResponse({"results": data})
        return HttpResponse(html)


class GlossaryApiView(View):

    def get(self, request):
        lang = get_language() or "en"
        q = (request.GET.get("q") or "").strip()
        letter = (request.GET.get("letter") or "").strip()
        try:
            limit = min(max(int(request.GET.get("limit", 50)), 1), 200)
        except ValueError:
            limit = 50
        try:
            offset = max(int(request.GET.get("offset", 0)), 0)
        except ValueError:
            offset = 0

        qs = GlossaryTerm.objects.filter(language=lang)
        if letter:
            qs = qs.filter(term__istartswith=letter)
        if q:
            qs = qs.filter(
                Q(term__icontains=q)
                | Q(short_definition__icontains=q)
                | Q(long_definition__icontains=q)
                | Q(category__icontains=q)
            )
        total = qs.count()
        rows = qs.order_by("term")[offset: offset + limit]

        data = [
            {
                "term": r.term,
                "slug": r.slug,
                "short_definition": r.short_definition,
                "category": r.category,
                "language": r.language,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rows
        ]

        return JsonResponse(
            {
                "count": total,
                "limit": limit,
                "offset": offset,
                "results": data,
            }
        )
