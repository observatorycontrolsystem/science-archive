from django.conf.urls import url, include
from django.contrib import admin
from rest_framework import routers
from rest_framework.authtoken import views as apiviews
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
router.register(r'frames', views.FrameViewSet, base_name="frame")

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^admin/', admin.site.urls),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^api-token-auth/', apiviews.obtain_auth_token),
]
