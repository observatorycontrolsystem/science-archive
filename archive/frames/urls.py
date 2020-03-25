from django.conf.urls import url
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from archive.frames import views

router = DefaultRouter()
router.register(r'frames', views.FrameViewSet, base_name='frame')
router.register(r'versions', views.VersionViewSet, base_name='version')

urlpatterns = [
    url(r'^', include(router.urls)),
    path('s3-download/<int:version_id>/', views.s3_download, name='s3-download'),
]
