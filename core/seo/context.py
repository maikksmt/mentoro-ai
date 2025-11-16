from django.conf import settings

from .types import SeoMeta
from .utils import absolute_url


def defaults(request) -> SeoMeta:
    canonical = absolute_url(request.path)
    return SeoMeta(
        title=getattr(settings, "SITE_NAME", "Site"),
        description="Curated guides, prompts and AI tool knowledge base.",
        canonical=canonical,
        robots="index,follow",
        og_image=None,
        alternates=[],
        json_ld={
            "@context": "https://schema.org",
            "@type": "WebSite",
            "url": getattr(settings, "SITE_URL", ""),
            "name": getattr(settings, "SITE_NAME", "Site"),
            "inLanguage": getattr(request, "LANGUAGE_CODE", "en")
        }
    )
