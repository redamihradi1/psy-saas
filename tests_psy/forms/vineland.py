from django import forms

from tests_psy.models import TestVineland, SousDomain
from cabinet.models import Patient

TEXT_INPUT_CLASS = 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary focus:ring-opacity-50'

DUREE_LIEN_CHOICES = [
    (3, '3 jours'),
    (7, '7 jours'),
    (14, '14 jours'),
    (30, '30 jours'),
]


class TestVinelandModeForm(forms.Form):
    """Étape 1 de 'Nouveau test Vineland' : patient + mode de passation."""

    patient = forms.ModelChoiceField(
        queryset=Patient.objects.none(),
        empty_label="Sélectionnez un patient",
        widget=forms.Select(attrs={
            'class': TEXT_INPUT_CLASS,
            'data-searchable': '1',
            'data-placeholder': 'Rechercher un patient...',
        }),
    )
    mode = forms.ChoiceField(
        choices=TestVineland.MODE_CHOICES,
        initial='cabinet',
        widget=forms.RadioSelect,
    )
    duree_jours = forms.ChoiceField(
        choices=DUREE_LIEN_CHOICES, required=False, initial=7,
        widget=forms.Select(attrs={'class': TEXT_INPUT_CLASS}),
    )

    def __init__(self, *args, organization=None, all_patients=False, **kwargs):
        super().__init__(*args, **kwargs)
        if all_patients:
            self.fields['patient'].queryset = Patient.all_objects.order_by('nom', 'prenom')
            recent_ids = Patient.all_objects.order_by('-date_creation').values_list('id', flat=True)[:5]
        elif organization:
            self.fields['patient'].queryset = Patient.objects.filter(
                organization=organization
            ).order_by('nom', 'prenom')
            recent_ids = Patient.objects.filter(
                organization=organization
            ).order_by('-date_creation').values_list('id', flat=True)[:5]
        else:
            recent_ids = []
        self.fields['patient'].widget.attrs['data-recent-ids'] = ','.join(str(pk) for pk in recent_ids)
        self.fields['patient'].label = "Patient"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('mode') == 'lien_public' and not cleaned.get('duree_jours'):
            self.add_error('duree_jours', "Choisissez une durée de validité pour le lien.")
        return cleaned


class NoteBruteImporteeVinelandForm(forms.Form):
    """Formulaire dynamique : un champ note brute par sous-domaine, style
    ReponseItemBeckForm (un champ par PhraseBeck, généré dans __init__)."""

    def __init__(self, *args, initial_notes=None, **kwargs):
        super().__init__(*args, **kwargs)
        initial_notes = initial_notes or {}

        for sous_domaine in SousDomain.objects.select_related('domain').order_by('domain__ordre', 'ordre'):
            field_name = f'sous_domaine_{sous_domaine.id}'
            field = forms.IntegerField(
                required=True,
                min_value=0,
                label=sous_domaine.name,
                initial=initial_notes.get(sous_domaine.id),
                widget=forms.NumberInput(attrs={'class': TEXT_INPUT_CLASS}),
            )
            field.sous_domaine = sous_domaine
            self.fields[field_name] = field
