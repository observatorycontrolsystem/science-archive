class DBClusterRouter:
    """
    Database router that sends read operations to one endpoint 
    and write operations to another.
    """
    def db_for_read(self, model, **hints):
        """
        Reads go to the reader endpoint.
        """
        return 'reader'

    def db_for_write(self, model, **hints):
        """
        Writes go the the writer endpoint, which is the default database.
        """
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between objects for both databases since 
        they are reader and writer endpoints pointing at the same data.
        """
        db_list = ('default', 'reader')
        if obj1._state.db in db_list and obj2._state.db in db_list:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        All models should appear in both databases
        """
        return True
