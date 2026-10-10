from django import forms

from tests_psy.models.brief import ECHELLE_CHOICES, SEXE_CHOICES, TestBRIEF
from tests_psy.forms.vineland import DUREE_LIEN_CHOICES, TEXT_INPUT_CLASS
from cabinet.models import Patient


class TestBRIEFNouveauForm(forms.Form):
    """'Nouveau test BRIEF' : patient, sexe (requis pour les normes), répondant et mode."""

    patient = forms.ModelChoiceField(
        queryset=Patient.objects.none(),
        empty_label="Sélectionnez un patient",
        widget=forms.Select(attrs={
            'class': TEXT_INPUT_CLASS,
            'data-searchable': '1',
            'data-placeholder': 'Rechercher un patient...',
        }),
    )
    sexe = forms.ChoiceField(
        choices=SEXE_CHOICES, label="Sexe de l'enfant",
        widget=forms.RadioSelect,
        help_text="Les tables d'étalonnage BRIEF sont distinctes pour les garçons et les filles.",
    )
    repondant = forms.CharField(
        required=False, max_length=50, label="Lien de parenté du répondant",
        widget=forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': 'Ex : Mère, Père, Tuteur'}),
    )
    mode = forms.ChoiceField(choices=TestBRIEF.MODE_CHOICES, initial='cabinet', widget=forms.RadioSelect)
    duree_jours = forms.ChoiceField(
        choices=DUREE_LIEN_CHOICES, required=False, initial=7,
        widget=forms.Select(attrs={'class': TEXT_INPUT_CLASS}),
    )

    def __init__(self, *args, organization=None, all_patients=False, **kwargs):
        super().__init__(*args, **kwargs)
        if all_patients:
            patients = Patient.all_objects.all()
        elif organization:
            patients = Patient.objects.filter(organization=organization)
        else:
            patients = Patient.objects.none()
        self.fields['patient'].queryset = patients.order_by('nom', 'prenom')
        recent_ids = patients.order_by('-date_creation').values_list('id', flat=True)[:5]
        self.fields['patient'].widget.attrs['data-recent-ids'] = ','.join(str(pk) for pk in recent_ids)
        self.fields['patient'].label = "Patient"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('mode') == 'lien_public' and not cleaned.get('duree_jours'):
            self.add_error('duree_jours', "Choisissez une durée de validité pour le lien.")
        return cleaned


class NotesImporteesBRIEFForm(forms.Form):
    """Mode 'importe' : un score brut par échelle (déjà coté sur papier) + les scores de
    validité, facultatifs puisqu'ils ne peuvent pas être recalculés sans les réponses."""

    negativite = forms.IntegerField(
        required=False, min_value=0, max_value=9, label="Score de Négativité (0 à 9)",
        widget=forms.NumberInput(attrs={'class': TEXT_INPUT_CLASS}),
    )
    incoherence = forms.IntegerField(
        required=False, min_value=0, max_value=20, label="Score d'Incohérence (0 à 20)",
        widget=forms.NumberInput(attrs={'class': TEXT_INPUT_CLASS}),
    )

    def __init__(self, *args, initial_notes=None, **kwargs):
        super().__init__(*args, **kwargs)
        initial_notes = initial_notes or {}
        champs_echelles = {}
        for code, libelle in ECHELLE_CHOICES:
            champs_echelles[f'echelle_{code}'] = forms.IntegerField(
                required=True, min_value=0, label=libelle,
                initial=initial_notes.get(code),
                widget=forms.NumberInput(attrs={'class': TEXT_INPUT_CLASS}),
            )
        # Échelles d'abord, validité ensuite (ordre d'affichage).
        self.fields = {**champs_echelles, **self.fields}

    def champs_echelles(self):
        return [self[name] for name in self.fields if name.startswith('echelle_')]

    def champs_validite(self):
        return [self['negativite'], self['incoherence']]
