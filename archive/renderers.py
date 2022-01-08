from rest_framework.renderers import BrowsableAPIRenderer
from django.conf import settings

# This overrides the default browsable api renderer so that we can pass custom values
# into the template (eg. users might want to configure the title text)
class CustomBrowsableAPIRenderer(BrowsableAPIRenderer):
    def get_context(self, *args, **kwargs):
        context = super(CustomBrowsableAPIRenderer, self).get_context(*args, **kwargs)
        context["navbar_title_text"] = settings.NAVBAR_TITLE_TEXT
        context["navbar_title_url"] = settings.NAVBAR_TITLE_URL
        context["documentation_url"] = settings.DOCUMENTATION_URL
        return context
