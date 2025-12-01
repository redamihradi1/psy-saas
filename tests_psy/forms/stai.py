from django import forms
from tests_psy.models import TestSTAI
from cabinet.models import Patient


class TestSTAIForm(forms.ModelForm):
    """Formulaire pour créer un nouveau test STAI"""

    class Meta:
        model = TestSTAI
        fields = ['patient']
        widgets = {
            'patient': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary focus:ring-opacity-50'
            })
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

        if organization:
            self.fields['patient'].queryset = Patient.objects.filter(
                organization=organization
            ).order_by('nom', 'prenom')

        self.fields['patient'].label = "Patient"
        self.fields['patient'].empty_label = "Sélectionnez un patient"
