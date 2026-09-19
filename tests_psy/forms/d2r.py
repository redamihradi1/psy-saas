from django import forms
from tests_psy.models import TestD2R
from cabinet.models import Patient

class TestD2RForm(forms.ModelForm):
    class Meta:
        model = TestD2R
        fields = [
            'patient',
            'code', 
            'date', 
            'age', 
            'sexe',
            'type_ecole',
            'etudes',
            'profession', 
            'correction_vue',
            'lateralite'
        ]
        widgets = {
            'patient': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent',
                'data-searchable': '1',
                'data-placeholder': 'Rechercher un patient...',
            }),
            'code': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent',
                'placeholder': 'Code du test (optionnel)'
            }),
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent'
            }),
            'age': forms.NumberInput(attrs={
                'min': 0,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent',
                'placeholder': 'Âge'
            }),
            'sexe': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent'
            }),
            'type_ecole': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent',
                'placeholder': "Type d'école ou classe"
            }),
            'etudes': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent',
                'placeholder': "Niveau d'études"
            }),
            'profession': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent',
                'placeholder': 'Profession actuelle'
            }),
            'correction_vue': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent'
            }),
            'lateralite': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent'
            }),
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
        self.fields['code'].required = False


class TestD2RResponseForm(forms.Form):
    """Formulaire pour soumettre les réponses du test"""
    selected_symbols = forms.CharField(widget=forms.HiddenInput())
    temps_total = forms.IntegerField(widget=forms.HiddenInput())