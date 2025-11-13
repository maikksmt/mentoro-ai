from django.apps import AppConfig


class UsecasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "usecases"

    def ready(self):
        import reversion
        from reversion.revisions import RegistrationError
        from django.apps import apps

        UseCase = apps.get_model("usecases", "UseCase")
        translations_field = UseCase._meta.get_field("translations")
        TranslationModel = translations_field.related_model

        try:
            reversion.register(UseCase, follow=("translations",))
        except RegistrationError:
            pass
        try:
            reversion.register(TranslationModel)
        except RegistrationError:
            pass
