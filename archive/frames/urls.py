from django.conf.urls import url, include
from rest_framework.routers import DefaultRouter
from archive.frames import views

router = DefaultRouter()
router.register(r'frames', views.FrameViewSet, base_name='frame')
router.register(r'versions', views.VersionViewSet, base_name='version')

urlpatterns = [
    url(r'^', include(router.urls)),
]
