from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import models
from datetime import date, timedelta
from .models import Patient, Anamnese, Consultation, PackMindOffice, PatientFichier


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['nom', 'prenom', 'date_naissance', 'categorie_age', 'telephone', 'email']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Nom du patient'
            }),
            'prenom': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Prénom du patient'
            }),
            'date_naissance': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'type': 'date'
            }),
            'categorie_age': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': '+212 XXX XXX XXX'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'email@exemple.com'
            }),
        }
    
    def clean_date_naissance(self):
        date_naissance = self.cleaned_data['date_naissance']
        
        if date_naissance > date.today():
            raise ValidationError("La date de naissance ne peut pas être dans le futur.")
        
        age = date.today().year - date_naissance.year
        if age > 120:
            raise ValidationError("L'âge ne peut pas dépasser 120 ans.")
        
        return date_naissance
    
    def clean_telephone(self):
        telephone = self.cleaned_data.get('telephone')
        if telephone:
            telephone = ''.join(filter(str.isdigit, telephone))
            if len(telephone) < 10:
                raise ValidationError("Le numéro de téléphone doit contenir au moins 10 chiffres.")
        return telephone

class PatientFichierForm(forms.ModelForm):
    class Meta:
        model = PatientFichier
        fields = ['fichier', 'nom_fichier', 'categorie', 'description']
        widgets = {
            'fichier': forms.FileInput(attrs={
                'class': 'hidden',
                'id': 'file-input',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.xls,.xlsx,.ppt,.pptx,.txt'
            }),
            'nom_fichier': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent',
                'placeholder': 'Nom du fichier (optionnel)'
            }),
            'categorie': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent',
                'rows': 3,
                'placeholder': 'Description ou notes (optionnel)'
            }),
        }
    
    def clean_fichier(self):
        fichier = self.cleaned_data.get('fichier')
        if fichier:
            # Vérifier la taille (max 10 MB)
            if fichier.size > 10 * 1024 * 1024:
                raise forms.ValidationError("Le fichier ne doit pas dépasser 10 MB")
            
            # Vérifier l'extension
            import os
            ext = os.path.splitext(fichier.name)[1].lower()
            extensions_valides = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.gif', '.xls', '.xlsx', '.ppt', '.pptx', '.txt']
            if ext not in extensions_valides:
                raise forms.ValidationError(f"Extension non autorisée. Extensions valides : {', '.join(extensions_valides)}")
        
        return fichier

class ConsultationForm(forms.ModelForm):
    date_seance = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'type': 'datetime-local',
            }
        ),
        input_formats=['%Y-%m-%dT%H:%M'],
        label="Date et heure de séance"
    )
    
    class Meta:
        model = Consultation
        fields = [
            'patient', 'date_seance', 'duree_minutes', 'type_consultation',
            'lieu_consultation', 'pack_mind_office_utilise', 'tarif',
            'statut_paiement', 'date_paiement', 'notes_cliniques',
            'objectifs_seance', 'exercices_prevus', 'suivi_progression'
        ]
        widgets = {
            'patient': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'duree_minutes': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'min': '15',
                'max': '180',
                'step': '15',
                'value': '60'
            }),
            'type_consultation': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'lieu_consultation': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'pack_mind_office_utilise': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'tarif': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'step': '0.01',
                'placeholder': '400.00'
            }),
            'statut_paiement': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'date_paiement': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'type': 'date'
            }),
            'notes_cliniques': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 6
            }),
            'objectifs_seance': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 3
            }),
            'exercices_prevus': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 3
            }),
            'suivi_progression': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 4
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filtrer patients par organisation
        if self.request and hasattr(self.request, 'tenant') and self.request.tenant:
            self.fields['patient'].queryset = Patient.objects.filter(
                organization=self.request.tenant
            ).order_by('nom', 'prenom')
            
            self.fields['pack_mind_office_utilise'].queryset = PackMindOffice.objects.filter(
                organization=self.request.tenant,
                statut='actif',
                nombre_seances_utilisees__lt=models.F('nombre_seances_total')
            ).order_by('-date_achat')
        
        self.fields['pack_mind_office_utilise'].required = False
        self.fields['date_paiement'].required = False
        
        if self.instance and self.instance.pk and self.instance.date_seance:
            local_dt = timezone.localtime(self.instance.date_seance)
            self.initial['date_seance'] = local_dt.strftime('%Y-%m-%dT%H:%M')


class PackMindOfficeForm(forms.ModelForm):
    class Meta:
        model = PackMindOffice
        exclude = ['nombre_seances_utilisees', 'date_creation', 'date_modification', 'organization']
        widgets = {
            'nom_pack': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'nombre_seances_total': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'min': 1
            }),
            'date_achat': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'type': 'date'
            }, format='%Y-%m-%d'),
            'date_expiration': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'type': 'date'
            }, format='%Y-%m-%d'),
            'prix_pack': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'step': 0.01
            }),
            'statut': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 3
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_achat'].input_formats = ['%Y-%m-%d']
        self.fields['date_expiration'].input_formats = ['%Y-%m-%d']