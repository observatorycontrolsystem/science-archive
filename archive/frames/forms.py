from django import forms

from archive.frames.models import Frame
from archive.frames.utils import get_configuration_type_tuples


class FrameForm(forms.ModelForm):
    ''' Form adds in choices for configuration type from Configdb or env variable '''
    class Meta:
        model = Frame
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['configuration_type'] = forms.ChoiceField(choices=get_configuration_type_tuples())
