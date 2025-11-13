# content/views/seo_check.py
from __future__ import annotations
import re
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import List, Dict, Any

from django.contrib.auth.decorators import user_passes_test, login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.test import Client
from django.utils.html import strip_spaces_between_tags

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
META_DESC_RE = re.compile(
    r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL,
)
META_ROBOTS_RE = re.compile(
    r'<meta\s+name=["\']robots["\']\s+content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL,
)
CANONICAL_RE = re.compile(
    r'<link\s+rel=["\']canonical["\']\s+href=["\'](.*?)["\']', re.IGNORECASE | re.DOTALL
)
OG_IMAGE_RE = re.compile(
    r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL,
)
HREFLANG_RE = re.compile(
    r'<link\s+rel=["\']alternate["\']\s+hreflang=["\'](.*?)["\']\s+href=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class SeoIssue:
    level: str  # "ok" | "warn" | "error"
    field: str
    msg: str


@dataclass
class SeoResult:
    path: str
    status_code: int
    issues: List[SeoIssue]
    extracted: Dict[str, Any]


def _abbrev(text: str, n: int = 120) -> str:
    return (text[:n] + "…") if text and len(text) > n else (text or "")


def _is_absolute(url: str) -> bool:
    try:
        p = urlparse(url)
        return bool(p.scheme) and bool(p.netloc)
    except Exception:
        return False


def run_checks(request: HttpRequest, path: str) -> SeoResult:
    base = request.build_absolute_uri("/")  # z. B. https://example.com/
    client = Client()
    resp = client.get(path, follow=True)
    status = getattr(resp, "status_code", 0)
    html = strip_spaces_between_tags((resp.content or b"").decode("utf-8", "ignore"))

    issues: List[SeoIssue] = []
    extracted: Dict[str, Any] = {
        "title": "",
        "description": "",
        "canonical": "",
        "og_image": "",
        "hreflang": [],
    }

    # Status
    if status != 200:
        issues.append(SeoIssue("error", "status", f"HTTP {status} (erwartet 200)"))
        return SeoResult(path, status, issues, extracted)

    # <title>
    m = TITLE_RE.search(html)
    if not m:
        issues.append(SeoIssue("error", "title", "<title> fehlt"))
    else:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
        extracted["title"] = title
        if len(title) < 10:
            issues.append(SeoIssue("warn", "title", f"zu kurz ({len(title)})"))
        if len(title) > 60:
            issues.append(SeoIssue("warn", "title", f"zu lang ({len(title)})"))

    m = META_DESC_RE.search(html)
    if not m:
        issues.append(SeoIssue("error", "description", "meta description fehlt"))
    else:
        desc = re.sub(r"\s+", " ", m.group(1)).strip()
        extracted["description"] = _abbrev(desc, 200)
        if len(desc) > 160:
            issues.append(
                SeoIssue("warn", "description", f"länger als 160 ({len(desc)})")
            )

    m = META_ROBOTS_RE.search(html)
    if m:
        robots = m.group(1).lower().strip()
        extracted["robots"] = robots
        if "noindex" in robots:
            issues.append(SeoIssue("warn", "robots", f"noindex set ({robots})"))
    else:
        extracted["robots"] = "—"

    # canonical
    m = CANONICAL_RE.search(html)
    if not m:
        issues.append(SeoIssue("error", "canonical", "<link rel='canonical'> fehlt"))
    else:
        canonical = m.group(1).strip()
        extracted["canonical"] = canonical
        if not _is_absolute(canonical):
            issues.append(SeoIssue("warn", "canonical", "Canonical ist bot absolute"))
        if _is_absolute(canonical) and not canonical.startswith(base):
            issues.append(
                SeoIssue("warn", "canonical", "Canonical points to a foreign domain")
            )

    m = OG_IMAGE_RE.search(html)
    if not m:
        issues.append(
            SeoIssue(
                "warn",
                "og:image",
                "og:image not set (fallback may be from base.html)",
            )
        )
    else:
        og = m.group(1).strip()
        extracted["og_image"] = og
        if not _is_absolute(og):
            issues.append(SeoIssue("warn", "og:image", "og:image is bot absolutw"))

    # hreflang
    alts = HREFLANG_RE.findall(html)
    extracted["hreflang"] = [{"lang": a[0], "href": a[1]} for a in alts]
    langs = {a[0].lower() for a in alts}
    if alts and not ({"de", "en"} & langs):
        issues.append(
            SeoIssue(
                "warn",
                "hreflang",
                "hreflang vorhanden, aber weder 'de' noch 'en' gefunden",
            )
        )

    return SeoResult(path, status, issues, extracted)


@login_required
@user_passes_test(lambda u: u.is_staff)
def seo_check_view(request: HttpRequest) -> HttpResponse:
    default_paths = [
        "/",
        "/de/",
        "/en/",
        "/de/glossary/",
        "/de/guides/",
        "/de/prompts/",
        "/de/usecases/",
        "/de/tools/",
        "/de/compare/",
        "/de/starter-guide/",
        "/de/newsletter/",
        "/de/accounts/login/",
        "/de/accounts/signup/",
        "/de/accounts/apple/login/",
        "/de/accounts/github/login/",
        "/de/accounts/google/login/",
        "/en/glossary/",
        "/en/guides/",
        "/en/prompts/",
        "/en/usecases/",
        "/en/tools/",
        "/en/compare/",
        "/en/starter-guide/",
        "/en/newsletter/",
        "/en/accounts/login/",
        "/en/accounts/signup/",
        "/en/accounts/apple/login/",
        "/en/accounts/github/login/",
        "/en/accounts/google/login/",
    ]

    results: List[SeoResult] = []
    raw = (request.POST.get("paths") or "").strip()
    if request.method == "POST" and raw:
        paths = [p.strip() for p in raw.splitlines() if p.strip()]
        for p in paths:
            if p.startswith("http://") or p.startswith("https://"):
                p = urlparse(p).path or "/"
            try:
                results.append(run_checks(request, p))
            except Exception as exc:
                results.append(
                    SeoResult(p, 0, [SeoIssue("error", "exception", str(exc))], {})
                )

    ctx = {
        "default_paths": "\n".join(default_paths),
        "raw_paths": raw or "\n".join(default_paths),
        "results": results,
    }
    return render(request, "ops/seo_check.html", ctx)
