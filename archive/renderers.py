from rest_framework.renderers import BrowsableAPIRenderer
from django.conf import settings

# This overrides the default browsable api renderer so that we can pass custom values
# into the template (eg. users might want to configure the title text)
class CustomBrowsableAPIRenderer(BrowsableAPIRenderer):
    def get_rendered_html_form(self, data, view, method, request):
        return None

    def show_form_for_method(self, view, method, request, obj):
        return False

    def get_context(self, *args, **kwargs):
        context = super().get_context(*args, **kwargs)
        context["navbar_title_text"] = settings.NAVBAR_TITLE_TEXT
        context["navbar_title_url"] = settings.NAVBAR_TITLE_URL
        context["documentation_url"] = settings.DOCUMENTATION_URL
        context['display_edit_forms'] = False
        return context
