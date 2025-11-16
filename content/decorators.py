# content/decorators.py
from functools import wraps

from django.core.exceptions import PermissionDenied


def require_group(*group_names):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            u = request.user
            if not u.is_authenticated:
                raise PermissionDenied
            if u.is_superuser:
                return view_func(request, *args, **kwargs)
            if u.is_staff:
                return view_func(request, *args, **kwargs)
            if group_names:
                if u.groups.filter(name__in=group_names).exists():
                    return view_func(request, *args, **kwargs)
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
