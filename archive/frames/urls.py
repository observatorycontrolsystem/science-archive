from django.conf.urls import url, include
from rest_framework.routers import DefaultRouter
from archive.frames import views

router = DefaultRouter()
router.register(r'frames', views.FrameViewSet, base_name="frame")

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^aggregate/$', views.AggregateFrameView.as_view(), name='frame-aggregate'),
]
