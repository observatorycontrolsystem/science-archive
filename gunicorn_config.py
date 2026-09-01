import os

# Access log format. %({remote_user}e)s reads the WSGI environ's REMOTE_USER,
# which RemoteUserLogMiddleware sets to the authenticated username (or 'anonymous').
access_log_format = '%(h)s %(l)s %({remote_user}e)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Cap how many requests each worker handles at once. Gevent otherwise allows 1000 per worker.
worker_connections = int(os.getenv('GUNICORN_WORKER_CONNECTIONS', '12'))


def post_worker_init(worker):
    # Warm botocore's S3 service model cache before this worker accepts requests.
    # This runs after gevent's monkey.patch_all(), so the SSL context created here
    # uses the patched ssl module — same as all subsequent request-handling clients.
    # Botocore reads gzipped JSON service model files from disk when first creating
    # a client; doing it here prevents that file I/O from blocking the event loop.
    from ocs_archive.settings import settings as archive_settings
    if archive_settings.FILESTORE_TYPE == 's3':
        from ocs_archive.storage.s3store import S3Store
        try:
            S3Store.get_s3_client()
        except Exception:
            pass
