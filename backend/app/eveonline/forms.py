from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django.forms import ModelForm

from .models import EveCorporationApplication


class EveCorporationApplicationForm(ModelForm):
    """Form for creating a new EveCorporationApplication"""

    class Meta:
        model = EveCorporationApplication
        fields = [
            "description",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Submit"))
