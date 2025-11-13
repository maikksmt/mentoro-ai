from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from django.views.i18n import JavaScriptCatalog
from core.sitemaps import (
    GlossaryDetailSitemap,
    GlossaryIndexSitemap,
    GuideSitemap,
    PromptSitemap,
    UseCaseSitemap,
    ToolSitemap,
    ComparisonSitemap,
    LegalStaticSitemap,
)
from content.views.seo_check import seo_check_view
from content.views.uploads import tinymce_image_list, tinymce_upload
from core.views_i18n import set_language_smart

sitemaps = {
    "guides": GuideSitemap,
    "prompts": PromptSitemap,
    "usecases": UseCaseSitemap,
    "tools": ToolSitemap,
    "comparisons": ComparisonSitemap,
    "glossary-index": GlossaryIndexSitemap,
    "glossary-terms": GlossaryDetailSitemap,
    "legal-static": LegalStaticSitemap,
}

urlpatterns = [
    path("i18n/setlang/", set_language_smart, name="set_language"),
    path("jsi18n/", JavaScriptCatalog.as_view(packages=["content", ]), name="javascript-catalog", ),
    path("tinymce/", include("tinymce.urls")),
    path("filer/", include("filer.urls")),
    path("admin/tinymce/upload/", tinymce_upload, name="tinymce_upload"),
    path("admin/tinymce/image-list/", tinymce_image_list, name="tinymce_image_list"),
    path("admin/", admin.site.urls),
    path("ops/seo-check/", seo_check_view, name="ops_seo_check"),
    path("health/", lambda request: HttpResponse("OK"), name="healthcheck"),
]

urlpatterns += i18n_patterns(
    path("", include(("content.urls", "content"), namespace="content")),
    path("guides/", include("guides.urls", namespace="guides")),
    path("glossary/", include("glossary.urls", namespace="glossary")),
    path("prompts/", include("prompts.urls", namespace="prompts")),
    path("usecases/", include("usecases.urls", namespace="usecases")),
    path("catalog/", include("catalog.urls")),
    path("compare/", include("compare.urls")),
    path("what-to-find/", TemplateView.as_view(template_name="content/what-to-find.html"), name="what-to-find"),
    path("newsletter/", include("newsletter.urls")),
    path("accounts/", include("allauth.urls")),
    # path("api/", include("api.urls")),
    path("legal/", include("content.urls_legal")),
)

urlpatterns += [
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap", ),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain", ),
         name="robots", ),
]

if "rosetta" in settings.INSTALLED_APPS:
    urlpatterns += [re_path(r"^rosetta/", include("rosetta.urls"))]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
