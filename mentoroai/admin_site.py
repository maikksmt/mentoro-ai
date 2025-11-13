from django.contrib import admin


class MentoroAdminSite(admin.AdminSite):
    site_header = "MentoroAI Admin"
    site_title = "MentoroAI"
    index_title = "Administration"

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request)
        app_order = [
            "glossary",
            "guides",
            "prompts",
            "usecases",
            "catalog",
            "compare",
            "ops",
            "accounts",
            "newsletter",
        ]
        app_list.sort(key=lambda x: app_order.index(x["app_label"]) if x["app_label"] in app_order else 999)
        return app_list
