import os

DEBUG = False

SECRET_KEY = 'dyy%o7xo7xttxwiml2wscx2xjv(r8iqd6ve%uai=joe=r2b(^@'

ALLOWED_HOSTS = ['*']

STATIC_ROOT = '/var/www/static/'
MEDIA_ROOT = '/var/www/media/'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': os.getenv('CACHE_LOC', 'memcached.archivebackend:11211'),
    }
}
