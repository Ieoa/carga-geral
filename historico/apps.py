from django.apps import AppConfig


class HistoricoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'historico'

    def ready(self):
        from . import signals  # noqa: F401
