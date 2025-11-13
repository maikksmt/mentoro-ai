from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self) -> None:  # pragma: no cover - signal registration
        from .signals import ensure_editorial_groups

        post_migrate.connect(
            ensure_editorial_groups,
            dispatch_uid="accounts.ensure_editorial_groups",
        )
