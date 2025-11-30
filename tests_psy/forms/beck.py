from django import forms
from tests_psy.models import TestBeck, ItemBeck, PhraseBeck, ReponseItemBeck
from cabinet.models import Patient


class TestBeckForm(forms.ModelForm):
    """Formulaire pour créer un nouveau test Beck"""

    class Meta:
        model = TestBeck
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


class ReponseItemBeckForm(forms.Form):
    """
    Formulaire dynamique pour un item Beck.
    Génère des checkboxes pour chaque phrase de l'item.
    """

    def __init__(self, item, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.item = item

        # Récupérer toutes les phrases de cet item
        phrases = PhraseBeck.objects.filter(item=item).order_by('ordre')

        # Créer un checkbox pour chaque phrase
        for phrase in phrases:
            field_name = f'phrase_{phrase.id}'
            self.fields[field_name] = forms.BooleanField(
                required=False,
                label=phrase.texte,
                widget=forms.CheckboxInput(attrs={
                    'class': 'rounded border-gray-300 text-primary focus:ring-primary',
                    'data-score': phrase.score_valeur,
                    'data-phrase-id': phrase.id
                })
            )
