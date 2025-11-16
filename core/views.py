from core.seo.context import defaults
from core.seo.types import SeoMeta, AltHref


class SeoMixin:
    def build_seo(self, request, *, title, description, canonical, og_image=None, alternates=None, json_ld=None):
        alts = [AltHref(**a) for a in (alternates or [])]
        return SeoMeta(
            title=title, description=description, canonical=canonical,
            og_image=og_image, alternates=alts, json_ld=json_ld
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if "seo" not in ctx:
            ctx["seo"] = defaults(self.request)
        return ctx
