from django.conf.urls import url
from django.urls import include
from rest_framework.routers import DefaultRouter
from archive.frames import views

router = DefaultRouter()
router.register(r'frames', views.FrameViewSet, base_name='frame')
router.register(r'versions', views.VersionViewSet, base_name='version')
router.register(r's3-funpack', views.S3ViewSet, base_name='s3-funpack')

urlpatterns = [
    url(r'^', include(router.urls)),
]
