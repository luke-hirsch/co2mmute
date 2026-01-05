from django.apps import AppConfig


class MapsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "maps"

    def ready(self):
        """Register signals when the app is ready."""
        import maps.signals  # noqa: F401
