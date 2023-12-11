from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout
from .models import EveCorporationApplication
from django.forms import ModelForm


class EveCorporationApplicationForm(ModelForm):
    class Meta:
        model = EveCorporationApplication
        fields = [
            "description",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Submit"))
