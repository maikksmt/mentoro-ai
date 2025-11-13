from django.apps import AppConfig
from django.contrib.admin.apps import AdminConfig


class MentoroAdminConfig(AdminConfig):
    default_site = "mentoroai.admin_site.MentoroAdminSite"


class MentoroAIConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mentoroai"
