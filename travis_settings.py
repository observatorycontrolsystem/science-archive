from archive.settings import *
DEBUG = False
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'archive',
        'USER': 'postgres',
        'PASSWORD': '',
        'ATOMIC_REQUESTS': True,
    }
}
