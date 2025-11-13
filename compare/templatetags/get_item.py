from django import template

register = template.Library()


@register.filter(name="get_item")
def get_item(value, arg):
    try:
        if isinstance(value, dict):
            return value.get(arg, "")
        if isinstance(value, (list, tuple)):
            try:
                idx = int(arg)
            except (TypeError, ValueError):
                return ""
            return value[idx] if 0 <= idx < len(value) else ""
        return ""
    except Exception:
        return ""
