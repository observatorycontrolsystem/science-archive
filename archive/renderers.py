from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from archive.settings import NAVBAR_TITLE_TEXT, NAVBAR_TITLE_URL

# This overrides the default browsable api renderer so that we can pass custom values 
# into the template (eg. users might want to configure the title text)
class CustomBrowsableAPIRenderer(BrowsableAPIRenderer):
    def get_context(self, *args, **kwargs):
        context = super(CustomBrowsableAPIRenderer, self).get_context(*args, **kwargs)
        context["navbar_title_text"] = NAVBAR_TITLE_TEXT
        context["navbar_title_url"] = NAVBAR_TITLE_URL
        return context
