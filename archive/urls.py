from django.conf.urls import url, include
from django.contrib import admin
from django.urls import path
from django.http import HttpResponse
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
      title="Science Archive API",
      default_version='v1',
      description="API documentation for the OCS Science Archive",
      terms_of_service="https://lco.global/policies/terms/",
      contact=openapi.Contact(email="ocs@lco.global"),
      license=openapi.License(name="GPL 3.0 License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
   generator_class=ScienceArchiveSchemaGenerator)

urlpatterns = [
    url(r'^robots.txt$', lambda r: HttpResponse("User-agent: *\nDisallow: /", content_type='text/plain')),
    url(r'^', include(frame_urls)),
    url(r'^', include(auth_urls)),
    url(r'^admin/', admin.site.urls),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^api-token-auth/', ObtainAuthTokenWithHeaders.as_view()),
    url(r'^revoke_token/', RevokeApiTokenApiView.as_view(), name='revoke_api_token'),
    url(r'^health/', HealthCheckView.as_view()),
    path('openapi/', schema_view.as_view(), name='openapi-schema'),
    path('redoc/', TemplateView.as_view(
        template_name='redoc.html',
        extra_context={'schema_url':'openapi-schema'}
    ), name='redoc')
]
