from django.conf.urls import url, include
from django.contrib import admin
from django.http import HttpResponse
from archive.frames import urls as frame_urls
from archive.authentication import urls as auth_urls
from archive.authentication.views import ObtainAuthTokenWithHeaders, HealthCheckView

urlpatterns = [
    url(r'^robots.txt$', lambda r: HttpResponse("User-agent: *\nDisallow: /", content_type='text/plain')),
    url(r'^', include(frame_urls)),
    url(r'^', include(auth_urls)),
    url(r'^admin/', admin.site.urls),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^api-token-auth/', ObtainAuthTokenWithHeaders.as_view()),
    url(r'^health/', HealthCheckView.as_view())
]
