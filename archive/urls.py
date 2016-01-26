from django.conf.urls import url, include
from django.contrib import admin
from rest_framework.authtoken import views as apiviews
from archive.frames import urls as frame_urls
from archive.authentication import urls as auth_urls

urlpatterns = [
    url(r'^', include(frame_urls)),
    url(r'^', include(auth_urls)),
    url(r'^admin/', admin.site.urls),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^api-token-auth/', apiviews.obtain_auth_token),
]
