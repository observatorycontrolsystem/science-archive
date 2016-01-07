"""archive URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Import the include() function: from django.conf.urls import url, include
    3. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf.urls import url, include
from django.contrib import admin
from rest_framework import routers
from archive.frames import views


class DocumentedRootRouter(routers.DefaultRouter):
    def get_api_root_view(self):
        api_root_view = super().get_api_root_view()
        ApiRootClass = api_root_view.cls

        class APIRoot(ApiRootClass):
            """
            This is the top level of the LCOGT archive api.

            This website is a self documented HTML interface to the actual api.
            The path in the URL bar of your browser reflects the same
            path you would call in software using the api.

            Calling endpoints outside of a browser will return data in JSON format.
            You can also view json in the browser by appending the `format=json` query
            paramter to any call, or adding the `.json` suffix to any url.

            Some resources allow you to create or update data using POST or PUT.
            These resources will provide a form at the bottom of the page in this
            browseable api.

            Some resources accept query parameters as well as pagination and sorting.
            These resources will have controls in the top right. For example, this
            resource allows the OPTIONS and GET http methods.

            **This endpoint returns a list of available resources. Click on the link
            to navigate to that resource.**

            """
            pass

        return APIRoot.as_view()

router = DocumentedRootRouter()
router.register(r'frames', views.FrameViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^admin/', admin.site.urls),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]
