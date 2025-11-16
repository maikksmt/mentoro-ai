import json

from django import template

register = template.Library()


@register.filter
def jsonld(value):
    """
    Serialisiert ein Python-Dict für JSON-LD.
    - Kompakte Ausgabe (separators)
    - Unicode erhalten (ensure_ascii=False)
    - Fällt bei Fehlern auf {} zurück
    """
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return "{}"
