# core/views_i18n.py
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import resolve, Resolver404, reverse
from django.utils import translation
from django.utils.translation import check_for_language
from django.views.decorators.http import require_POST


def _persist_language(request, lang_code: str):
    """
    Persistiert die Sprache wie die offizielle Django-View:
    - aktiviert die Sprache für die aktuelle Response
    - speichert sie in der Session (Schlüssel = LANGUAGE_COOKIE_NAME)
      oder alternativ als Cookie auf der Response
    """
    translation.activate(lang_code)
    # Session: gleiche Key-Namensgebung wie Cookie (Django macht das so)
    if hasattr(request, "session"):
        request.session[settings.LANGUAGE_COOKIE_NAME] = lang_code


def _attach_language_cookie(response, lang_code: str):
    """
    Hängt das Sprach-Cookie an die Response (Fallback/zusätzlich zur Session).
    Respektiert alle relevanten Settings.
    """
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        lang_code,
        max_age=getattr(settings, "LANGUAGE_COOKIE_AGE", None),
        path=getattr(settings, "LANGUAGE_COOKIE_PATH", "/"),
        domain=getattr(settings, "LANGUAGE_COOKIE_DOMAIN", None),
        secure=getattr(settings, "LANGUAGE_COOKIE_SECURE", False),
        httponly=getattr(settings, "LANGUAGE_COOKIE_HTTPONLY", False),
        samesite=getattr(settings, "LANGUAGE_COOKIE_SAMESITE", "Lax"),
    )


@require_POST
def set_language_smart(request):
    """
    Sprachwechsel mit intelligentem Redirect:
      - Sprache setzen (Session/Cookie)
      - Wenn 'next' Glossary-Detail ist:
          (1) gleicher slug in Ziel-Sprache
          (2) sonst via translation_group passende Übersetzung
          (3) sonst Fallback: Glossary-Liste
      - Alle anderen Pfade: normaler Redirect auf 'next'
    """
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    lang_code = (request.POST.get("language") or "").split("-", 1)[0]

    if not (lang_code and check_for_language(lang_code)):
        # Ungültiger Code -> normaler Redirect
        return HttpResponseRedirect(next_url)

    # Sprache für diese Request/Session aktivieren & persistieren
    _persist_language(request, lang_code)

    # Zielpfad aus 'next' auflösen
    path = urlparse(next_url).path
    try:
        match = resolve(path)
    except Resolver404:
        # Nicht auflösbar -> normal zurück
        resp = HttpResponseRedirect(next_url)
        _attach_language_cookie(resp, lang_code)
        return resp

    # Nur bei Glossary-Detail aktiv eingreifen
    if match.app_name == "glossary" and match.url_name == "detail":
        slug = match.kwargs.get("slug")

        from glossary.models import GlossaryTerm

        # (1) gleicher Slug in Zielsprache?
        target = GlossaryTerm.objects.filter(language=lang_code, slug=slug).first()

        # (2) via translation_group mappen, falls nötig
        if not target:
            current = (
                GlossaryTerm.objects
                .filter(slug=slug)
                .only("translation_group")
                .first()
            )
            if current and current.translation_group:
                target = GlossaryTerm.objects.filter(
                    translation_group=current.translation_group,
                    language=lang_code,
                ).first()

        # Redirect bauen
        if target:
            with translation.override(lang_code):
                resp = HttpResponseRedirect(target.get_absolute_url())
                _attach_language_cookie(resp, lang_code)
                return resp

        # (3) Fallback: Liste in Zielsprache
        with translation.override(lang_code):
            resp = HttpResponseRedirect(reverse("glossary:list"))
            _attach_language_cookie(resp, lang_code)
            return resp

    # Alle anderen Seiten: normal weiter
    resp = HttpResponseRedirect(next_url)
    _attach_language_cookie(resp, lang_code)
    return resp
