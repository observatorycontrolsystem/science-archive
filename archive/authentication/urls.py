from django.urls import re_path
from archive.authentication import views

urlpatterns = [
    re_path(r'^profile/$', views.UserView.as_view(), name='profile'),
]
