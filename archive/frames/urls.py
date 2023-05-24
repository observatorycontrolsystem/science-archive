from django.conf.urls import url
from django.urls import include
from rest_framework.routers import DefaultRouter
from archive.frames import views

import ocs_authentication.auth_profile.urls as authprofile_urls


router = DefaultRouter()
router.register(r'frames', views.FrameViewSet, basename='frame')
router.register(r'versions', views.VersionViewSet, basename='version')
router.register(r'frame-funpack', views.FunpackViewSet, basename='frame-funpack')
router.register(r'frame-catalog', views.CatalogViewSet, basename='frame-catalog')

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^authprofile/', include(authprofile_urls))
]
