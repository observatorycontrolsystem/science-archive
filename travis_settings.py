from archive.settings import *
DEBUG = False
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'archive',
        'USER': 'postgres',
        'PASSWORD': '',
        # 'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        # 'PORT': '5432',
        'ATOMIC_REQUESTS': True,
    }
}
