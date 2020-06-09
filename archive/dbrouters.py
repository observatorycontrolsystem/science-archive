from datetime import timedelta

from django.utils import timezone

from archive.frames.models import Frame, Version


class DBClusterRouter:
    """
    Database router that splits queries between reader and writer endpoints.
    """
    def db_for_read(self, model, **hints):
        """
        Reads for the archive frames models go to the reader endpoint.

        Reads for certain frames models are directed to the writer endpoint if the
        instance was recently created in order to prevent a race condition. This
        could happen if, for example, data that has been committed has not been
        replicated fast enough. This is an issue specifically in the frame
        creation view.
        """
        new_instance_delay_minutes = 10
        new_instance_delay_models = (Frame, Version,)
        instance = hints.get('instance')
        created = getattr(instance, 'created', None)

        if isinstance(instance, new_instance_delay_models) and created is not None:
            if created > timezone.now() - timedelta(minutes=new_instance_delay_minutes):
                return 'default'

        if 'archive.frames.models' in str(model):
            return 'replica'

        return 'default'

    def db_for_write(self, model, **hints):
        """
        Writes go the the writer endpoint.
        """
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between objects for both databases since
        they are replica and writer endpoints pointing at the same data.
        """
        db_list = ('default', 'replica')
        if obj1._state.db in db_list and obj2._state.db in db_list:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        All models should appear in both databases
        """
        return True
