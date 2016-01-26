from django.conf.urls import url
from archive.authentication import views

urlpatterns = [
    url(r'^profile/$', views.UserView.as_view(), name='profile'),
]
