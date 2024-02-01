from django.urls import re_path, path, include
from django.contrib import admin
from django.http import HttpResponse
from django.conf import settings
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from drf_yasg import openapi
from django.views.generic import TemplateView

from archive.frames import urls as frame_urls
from archive.authentication import urls as auth_urls
from archive.authentication.views import ObtainAuthTokenWithHeaders, HealthCheckView, RevokeApiTokenApiView
from archive.schema import ScienceArchiveSchemaGenerator

schema_view = get_schema_view(
   openapi.Info(
      title=settings.NAVBAR_TITLE_TEXT,
      default_version='v1',
      description="API documentation for the OCS Science Archive",
      terms_of_service=settings.TERMS_OF_SERVICE_URL,
      contact=openapi.Contact(email="ocs@lco.global"),
      license=openapi.License(name="GPL 3.0 License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
   generator_class=ScienceArchiveSchemaGenerator)

urlpatterns = [
    re_path(r'^robots.txt$', lambda r: HttpResponse("User-agent: *\nDisallow: /", content_type='text/plain')),
    re_path(r'^', include(frame_urls)),
    re_path(r'^', include(auth_urls)),
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    re_path(r'^api-token-auth/', ObtainAuthTokenWithHeaders.as_view()),
    re_path(r'^revoke_token/', RevokeApiTokenApiView.as_view(), name='revoke_api_token'),
    re_path(r'^health/', HealthCheckView.as_view()),
    path('openapi/', schema_view.as_view(), name='openapi-schema'),
    path('redoc/', TemplateView.as_view(
        template_name='redoc.html',
        extra_context={'schema_url':'openapi-schema'}
    ), name='redoc')
]
