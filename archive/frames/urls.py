from django.conf.urls import url
from archive.frames.views import FrameListView

urlpatterns = [
    url(r'^', FrameListView.as_view(), name='frames'),
]
