from django.apps import AppConfig


class GuidesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "guides"

    def ready(self):
        import reversion
        from reversion.revisions import RegistrationError
        from django.apps import apps
        from . import signals  # noqa: F401

        Guide = apps.get_model("guides", "Guide")
        translations_field = Guide._meta.get_field("translations")
        TranslationModel = translations_field.related_model

        try:
            reversion.register(Guide, follow=("translations",))
        except RegistrationError:
            pass

        try:
            reversion.register(TranslationModel)
        except RegistrationError:
            pass
