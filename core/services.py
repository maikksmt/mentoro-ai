from __future__ import annotations

import re
from html import escape
from typing import Any, Dict, List, Tuple, Optional, Iterable
from django.db.models import Count, Q, QuerySet
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.translation import get_language
from parler.utils.context import switch_language
from guides.models import Guide
from prompts.models import Prompt
from usecases.models import UseCase
import difflib
from reversion.models import Version


def get_latest_items(limit: int = 6, mix: Tuple[int, int, int] = (3, 2, 1)) -> List[Dict[str, Any]]:
    """
    Returns a balanced, recency-sorted mix of Guides/Prompts/UseCases based on mix;
    includes robust fallbacks when a type has too few items.
    """
    g_need, p_need, u_need = mix

    # Base-Querysets – robust sortiert
    g_qs: QuerySet = _safe_order_by_published(Guide.published)
    p_qs: QuerySet = _safe_order_by_published(Prompt.published)
    u_qs: QuerySet = _safe_order_by_published(UseCase.published)

    items: List[Dict[str, Any]] = []

    # Primärbedarf decken
    g_pick = list(g_qs[:g_need])
    p_pick = list(p_qs[:p_need])
    u_pick = list(u_qs[:u_need])

    items.extend([to_teaser_item(g, "guide") for g in g_pick])
    items.extend([to_teaser_item(p, "prompt") for p in p_pick])
    items.extend([to_teaser_item(u, "usecase") for u in u_pick])

    # Fill remaining slots with the most recent leftover items (all types together)
    deficit = max(0, limit - len(items))
    if deficit:
        # IDs ausschließen, die schon drin sind
        taken_ids = {
            *[("guide", g.pk) for g in g_pick],
            *[("prompt", p.pk) for p in p_pick],
            *[("usecase", u.pk) for u in u_pick],
        }

        def rest(qs, kind):
            for obj in qs:
                key = (kind, obj.pk)
                if key not in taken_ids:
                    yield to_teaser_item(obj, kind)

        merged = []
        merged.extend(list(rest(g_qs[g_need: g_need + limit * 2], "guide")))
        merged.extend(list(rest(p_qs[p_need: p_need + limit * 2], "prompt")))
        merged.extend(list(rest(u_qs[u_need: u_need + limit * 2], "usecase")))
        merged.sort(key=lambda x: (x.get("date") or 0), reverse=True)
        items.extend(merged[:deficit])

    items.sort(key=lambda x: (x.get("date") or 0), reverse=True)
    return items[:limit]


def related_guides(guide, limit=6):
    """
    Finds relevant Guides by shared categories and tools;
    falls back to temporally close Guides when metadata is sparse;
    excludes the current item.
    """

    if guide is None:
        return Guide.objects.none()
    cat_ids = _ids(guide.categories.all()) if hasattr(guide, "categories") else []
    tool_ids = (
        _ids(guide.tools.all()) if hasattr(guide, "tools") else []
    )

    qs = Guide.published.exclude(pk=guide.pk).prefetch_related(
        "categories", "tools__translations"
    )

    qs = (
        qs.filter(Q(categories__in=cat_ids) | Q(tools__in=tool_ids))
        .annotate(
            cat_matches=Count(
                "categories", filter=Q(categories__in=cat_ids), distinct=True
            ),
            tool_matches=Count(
                "tools", filter=Q(tools__in=tool_ids), distinct=True
            ),
        )
        .annotate(score=Count("id"))
        .order_by("-cat_matches", "-tool_matches", "-published_at")
    )

    items = list(qs[:limit])
    if len(items) < limit:
        fallback = Guide.published.exclude(
            pk__in=[g.pk for g in items] + [guide.pk]
        ).order_by("-published_at")[: limit - len(items)]
        items.extend(fallback)
    return items[:limit]


def related_prompts(prompt, limit=8):
    """
    Like related_guides but for Prompts: ranks by overlapping categories/tools;
    uses a time-based fallback if relations are missing.
    """
    tag_ids = _ids(prompt.tags.all()) if hasattr(prompt, "tags") else []
    tool_ids = _ids(prompt.tools.all()) if hasattr(prompt, "tools") else []

    qs = Prompt.published.exclude(pk=prompt.pk).prefetch_related("tags", "tools__translations")

    if tag_ids or tool_ids:
        qs = (
            qs.filter(Q(tags__in=tag_ids) | Q(tools__in=tool_ids))
            .annotate(
                tag_matches=Count("tags", filter=Q(tags__in=tag_ids), distinct=True),
                tool_matches=Count(
                    "tools", filter=Q(tools__in=tool_ids), distinct=True
                ),
            )
            .order_by("-tag_matches", "-tool_matches", "-published_at")
        )
    else:
        qs = qs.order_by("-published_at")

    items = list(qs[:limit])
    if len(items) < limit:
        fallback = Prompt.published.exclude(
            pk__in=[p.pk for p in items] + [prompt.pk]
        ).order_by("-published_at")[: limit - len(items)]
        items.extend(fallback)
    return items[:limit]


def related_usecases(usecase, limit=6):
    """
    Like above for UseCases;
    ensures “something useful” is returned even for fresh entries with little metadata.
    """
    lang = get_language() or "en"
    persona = usecase.safe_translation_getter("persona", any_language=False)
    tool_ids = _ids(usecase.tools.all()) if hasattr(usecase, "tools") else []

    qs = UseCase.published.exclude(pk=usecase.pk).prefetch_related("tools")

    persona_q = Q()
    if persona:
        persona_q = Q(persona__iexact=persona)

    if persona or tool_ids:
        qs = (
            qs.filter(persona_q | Q(tools__in=tool_ids))
            .annotate(
                persona_match=Count("id", filter=Q(translations__language_code=lang, translations__persona=persona)),
                tool_matches=Count("tools", filter=Q(tools__in=tool_ids), distinct=True),
            )
            .order_by("-persona_match", "-tool_matches", "-published_at")
        )
    else:
        qs = qs.order_by("-published_at")

    items = list(qs[:limit])
    if len(items) < limit:
        fallback = UseCase.published.exclude(
            pk__in=[u.pk for u in items] + [usecase.pk]
        ).order_by("-published_at")[: limit - len(items)]
        items.extend(fallback)
    return items[:limit]


# ---------- Helpers ----------


def _safe_order_by_published(qs):
    try:
        str(qs.order_by("-published_at").query)
        return qs.order_by("-published_at")
    except Exception:
        return qs.order_by("-id")


def _first(seq):
    try:
        return next(iter(seq)) if seq else ""
    except Exception:
        return ""


def teaser_for_guide(g: Guide, limit: int = 160) -> str:
    """
    Builds a compact teaser dict (title, short text, URL, date, meta) for a Guide;
    normalizes text (strip HTML) for consistent list UIs.
    """
    getter = getattr(g, "safe_translation_getter", None)
    if callable(getter):
        src = getter("intro", any_language=True) or getter("body", any_language=True) or ""
    else:
        src = getattr(g, "intro", None) or getattr(g, "body", "") or ""
    return (strip_tags(src) or "")[:limit]


def teaser_for_prompt(p: Prompt, limit: int = 160) -> str:
    """
    Teaser builder for a Prompt;
    generates a concise, HTML-safe summary suitable for cards and feeds.
    """
    ex = ""
    examples = getattr(p, "examples", None)
    if isinstance(examples, (list, tuple)):
        ex = _first(examples)
    elif isinstance(examples, str):
        ex = examples

    getter = getattr(p, "safe_translation_getter", None)
    if callable(getter):
        body = getter("intro", any_language=True) or getattr(p, "body", "") or ""
    else:
        body = getattr(p, "intro", None) or getattr(p, "body", "") or ""

    src = ex or body
    return (strip_tags(src) or "")[:limit]


def teaser_for_usecase(u: UseCase, limit: int = 160) -> str:
    """
    Teaser builder for a UseCase;
    aligns the structure with Guides/Prompts so frontends can render all three uniformly.
    """
    intro = getattr(u, "safe_translation_getter", None)
    if callable(intro):
        src = u.safe_translation_getter("intro", any_language=True) or ""
    else:
        src = getattr(u, "intro", "") or ""

    if not src:
        steps = getattr(u, "workflow_steps", None)
        step0 = _first(steps) if isinstance(steps, (list, tuple)) else ""
        src = step0 or ""

    return (strip_tags(src) or "")[:limit]


def _t(obj, field):
    """
    Returns a translated attribute using Parler’s safe_translation_getter with any_language=True fallback,
    else reads the attribute directly; avoids None/missing values.
    """
    getter = getattr(obj, "safe_translation_getter", None)
    if callable(getter):
        return getter(field, any_language=True) or ""
    return getattr(obj, field, "") or ""


def to_teaser_item(obj, kind: str) -> Dict[str, Any]:
    """
    Factory that converts any supported object into the unified teaser dict
    based on kind to simplify front-end consumption.
    """
    if kind == "guide":
        return {
            "title": _t(obj, "title"),
            "teaser": teaser_for_guide(obj),
            "url": reverse("guides:detail", kwargs={"slug": obj.slug}),
            "date": getattr(obj, "published_at", None),
            "badge": "Guide",
        }
    if kind == "prompt":
        return {
            "title": _t(obj, "title"),
            "teaser": teaser_for_prompt(obj),
            "url": reverse("prompts:detail", kwargs={"slug": obj.slug}),
            "date": getattr(obj, "published_at", None),
            "badge": "Prompt",
        }
    if kind == "usecase":
        return {
            "title": _t(obj, "title"),
            "teaser": teaser_for_usecase(obj),
            "url": reverse("usecases:detail", kwargs={"slug": obj.slug}),
            "date": getattr(obj, "published_at", None),
            "badge": "Usecase",
        }
    return {
        "title": str(obj),
        "teaser": "",
        "url": "#",
        "date": None,
        "badge": kind.title(),
    }


def _ids(qs, field="id"):
    return list(qs.values_list(field, flat=True))


TEXT_FIELDS = ("title", "intro", "body")
LIVE_FIELDS = ("slug", "public_slug", "title", "intro", "body")


def get_live_version_instance(obj):
    """
    Fetches the latest reversion Version marked as “live” to compare against the working copy;
    returns None if no live version exists.
    """
    rev_id = getattr(obj, "last_published_revision_id", None)
    if not rev_id:
        return None
    try:
        v = Version.objects.get(id=rev_id)
        live = v._object_version.object
        if hasattr(live, "set_current_language") and hasattr(obj, "get_current_language"):
            live.set_current_language(obj.get_current_language())
        return live
    except Version.DoesNotExist:
        return None


class _LiveSnapshotProxy:
    """
    Lightweight proxy that exposes translated “live” values (from live_i18n[lang])
    of a content object with safe fallbacks;
    used to render historical/live variants without mutating the real instance.
    """

    def __init__(self, obj, lang: str):
        self._obj = obj
        self._lang = lang
        self._data = (obj.live_i18n or {}).get(lang, {}) if hasattr(obj, "live_i18n") else {}

    def __getattr__(self, name):
        if name in LIVE_FIELDS:
            val = self._data.get(name)
            if val:
                return val
            with switch_language(self._obj, self._lang):
                return getattr(self._obj, "safe_translation_getter")(name)
        return getattr(self._obj, name)

    @property
    def title(self):
        return self.__getattr__("title")

    @property
    def intro(self):
        return self.__getattr__("intro")

    @property
    def body(self):
        return self.__getattr__("body")

    @property
    def slug(self):
        return self.__getattr__("slug")

    @property
    def public_slug(self):
        return self.__getattr__("public_slug")


def get_live_display_instance(obj, language: Optional[str] = None):
    """
    Builds a display-only proxy for the live snapshot in the requested (or current) language;
    safe to pass into templates/serializers.
    """
    lang = language or get_language()

    if hasattr(obj, "live_i18n") and (obj.live_i18n or {}).get(lang):
        return _LiveSnapshotProxy(obj, lang)

    try:
        live = get_live_version_instance(obj)
        if live:
            return live
    except Exception:
        pass

    return obj


_DIFF_HTML_FIELDS = ("intro", "body")
_SECTION_FIELDS = ("title", "body")
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str | None) -> str:
    """
    Removes HTML tags and collapses whitespace to make diffs and teasers readable;
    prevents script/style leakage into comparisons.
    """
    return _TAG_RE.sub("", s or "")


def _inline_diff(a: str, b: str) -> tuple[str, str]:
    """
    Creates a compact inline word-level diff (using difflib) with HTML escapes;
    truncates long outputs for UI friendliness.
    """
    sm = difflib.SequenceMatcher(a=a or "", b=b or "")
    out_a, out_b = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            eq_a = escape((a or "")[i1:i2])
            eq_b = escape((b or "")[j1:j2])
            out_a.append(eq_a)
            out_b.append(eq_b)
        elif tag == "replace":
            out_a.append(f"<del class='diff-del'>{escape((a or '')[i1:i2])}</del>")
            out_b.append(f"<ins class='diff-ins'>{escape((b or '')[j1:j2])}</ins>")
        elif tag == "delete":
            out_a.append(f"<del class='diff-del'>{escape((a or '')[i1:i2])}</del>")
        elif tag == "insert":
            out_b.append(f"<ins class='diff-ins'>{escape((b or '')[j1:j2])}</ins>")
    return ("".join(out_a), "".join(out_b))


def build_field_diffs(left: dict, right: dict) -> list[dict]:
    """
    Generates human-readable diffs for selected scalar/text fields between the working copy and the live snapshot;
    returns a dict keyed by field name.
    """
    diffs = []
    keys = {"slug", "public_slug", "title", "intro", "body"}
    for field in keys:
        lv = left.get(field) or ""
        rv = right.get(field) or ""
        if lv == rv:
            continue

        if field in _DIFF_HTML_FIELDS:
            la, rb = _inline_diff(_strip_html(lv), _strip_html(rv))
        else:
            la, rb = _inline_diff(str(lv), str(rv))

        diffs.append({"field": field, "left": la, "right": rb})
    return diffs


def _section_current_values(section, lang: str) -> dict:
    """
    Extracts the “current” values of a Guide/Prompt/UseCase section (title/body/items) in the active language;
    used for structured diffs.
    """
    if switch_language:
        with switch_language(section, lang):
            get = getattr(section, "safe_translation_getter", lambda n: None)
            return {f: get(f) for f in _SECTION_FIELDS}
    # Fallback ohne parler
    get = getattr(section, "safe_translation_getter", lambda n: None)
    return {f: get(f) for f in _SECTION_FIELDS}


def _section_live_values(section, lang: str) -> dict:
    """
    Reads the “live” values for the same section via the snapshot proxy;
    mirrors _section_current_values for apples-to-apples comparison.
    """
    data = (getattr(section, "live_i18n", None) or {}).get(lang, {})
    return {f: data.get(f) for f in _SECTION_FIELDS}


def build_section_diffs(guide, lang: str) -> list[dict]:
    """
    Produces per-field diffs for a section (title/body/items) using _inline_diff;
    enables precise review in editorial UIs.
    """
    diffs: list[dict] = []

    # actual Sections (Draft) – keep order
    sections: Iterable = getattr(guide, "sections", None)
    if hasattr(sections, "all"):
        sections = sections.all()
    if not sections:
        return diffs

    def _label(sec) -> str:
        left = _section_current_values(sec, lang).get("title")
        if left:
            return left
        right = _section_live_values(sec, lang).get("title")
        if right:
            return right
        return f"Section #{getattr(sec, 'pk', '—')}"

    for sec in sections:
        left_vals = _section_current_values(sec, lang)
        right_vals = _section_live_values(sec, lang)
        has_live = any(bool(v) for v in right_vals.values())
        has_draft = any(bool(v) for v in left_vals.values())
        if not has_live and not has_draft:
            continue
        if has_draft and not has_live:
            fields = []
            for f in _SECTION_FIELDS:
                lv = left_vals.get(f) or ""
                la, rb = _inline_diff(_strip_html(lv), "")
                fields.append({"field": f, "left": la, "right": rb})
            diffs.append({
                "id": getattr(sec, "pk", None),
                "label": _label(sec),
                "kind": "added",
                "fields": fields,
            })
            continue

        changed_fields: list[dict] = []
        for f in _SECTION_FIELDS:
            lv = left_vals.get(f) or ""
            rv = right_vals.get(f) or ""
            if lv == rv:
                continue
            la, rb = _inline_diff(_strip_html(lv), _strip_html(rv))
            changed_fields.append({"field": f, "left": la, "right": rb})

        if changed_fields:
            diffs.append({
                "id": getattr(sec, "pk", None),
                "label": _label(sec),
                "kind": "changed",
                "fields": changed_fields,
            })

    return diffs
