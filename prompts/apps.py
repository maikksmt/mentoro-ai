from django.apps import AppConfig


class PromptsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "prompts"

    def ready(self):
        import reversion
        from reversion.revisions import RegistrationError
        from django.apps import apps

        Prompt = apps.get_model("prompts", "Prompt")
        translations_field = Prompt._meta.get_field("translations")
        TranslationModel = translations_field.related_model

        try:
            reversion.register(Prompt, follow=("translations",))
        except RegistrationError:
            pass
        try:
            reversion.register(TranslationModel)
        except RegistrationError:
            pass
