from dataclasses import dataclass, field


@dataclass
class AltHref:
    lang: str
    url: str


@dataclass
class SeoMeta:
    title: str
    description: str
    canonical: str
    robots: str = "index,follow"
    og_image: str | None = None
    alternates: list[AltHref] = field(default_factory=list)
    json_ld: dict | None = None
