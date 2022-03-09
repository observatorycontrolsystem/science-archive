from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    name = 'archive.authentication'

    def ready(self):
        import archive.authentication.signals.handlers  # noqa
        super().ready()
