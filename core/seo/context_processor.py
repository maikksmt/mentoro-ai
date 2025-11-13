from django.conf import settings

from .context import defaults


def context_processor(request):
    return {
        "seo": defaults(request),
        "SITE_NAME": getattr(settings, "SITE_NAME", "MentoroAI"),
        "SITE_URL": getattr(settings, "SITE_URL", "").rstrip("/"),
    }
