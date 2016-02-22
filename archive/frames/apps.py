from django.apps import AppConfig


class FramesConfig(AppConfig):
    name = 'archive.frames'
    verbose_name = 'Frames'

    def ready(self):
        import archive.frames.signals.handlers  # noqa
        super().ready()
