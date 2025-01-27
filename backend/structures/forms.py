from django import forms

from .models import EveStructureTimer


class EveStructureTimerForm(forms.ModelForm):
    name = forms.CharField(max_length=255)

    class Meta:
        model = EveStructureTimer
        fields = [
            "name",
        ]
