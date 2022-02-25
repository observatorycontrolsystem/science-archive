from django.conf.urls import url
from django.urls import include
from rest_framework.routers import DefaultRouter
from archive.frames import views

router = DefaultRouter()
router.register(r'frames', views.FrameViewSet, basename='frame')
router.register(r'versions', views.VersionViewSet, basename='version')
router.register(r'frame-funpack', views.FunpackViewSet, basename='frame-funpack')

urlpatterns = [
    url(r'^', include(router.urls)),
]
