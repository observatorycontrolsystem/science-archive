from django.conf.urls import url
from archive.frames.views import FrameListView, FrameView

urlpatterns = [
    url(r'^$', FrameListView.as_view(), name='frames'),
    url(r'^(?P<pk>\d+)/$', FrameView.as_view(), name='frame'),
]
