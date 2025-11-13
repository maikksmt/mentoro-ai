from django.conf import settings
from django.urls import reverse


def absolute_url(path_or_url: str) -> str:
    if path_or_url.startswith("http"):
        return path_or_url
    base = getattr(settings, "SITE_URL", "").rstrip("/")
    return f"{base}/{path_or_url.lstrip('/')}"


def localized_alternates(request, url_name: str, kwargs: dict | None = None) -> list[dict]:
    from django.utils.translation import override
    alts = []
    for code, _ in settings.LANGUAGES:
        with override(code):
            path = reverse(url_name, kwargs=kwargs or {})
            alts.append({"lang": code, "url": absolute_url(path)})
    alts.append({"lang": "x-default", "url": absolute_url(request.path)})
    return alts
