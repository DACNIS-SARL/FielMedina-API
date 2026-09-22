from django.apps import AppConfig


class SharedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shared"

    def ready(self):
        from django.apps import apps

        from .revalidate import connect

        connect([*apps.get_app_config("guard").get_models(), apps.get_model("shared", "Page")])
