from django.apps import AppConfig

class HarvesterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "harvester"
    verbose_name = "Data Harvester"

    def ready(self):
        try:
            import harvester.signals  # noqa: F401
        except ImportError:
            import backend.harvester.signals  # noqa: F401

