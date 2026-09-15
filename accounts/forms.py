from django import forms
from django.utils.text import slugify

from .models import User, Organization, License

TEXT_INPUT_CLASS = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent'
CHECKBOX_CLASS = 'w-5 h-5 text-primary rounded border-gray-300 focus:ring-primary'

# Champs de permissions gérés par ces formulaires (dans l'ordre d'affichage).
# Un(e) assistant(e) est toujours créé(e) par le super admin de la plateforme et attaché(e)
# à un psychologue existant (= son organisation). Créer un nouveau psychologue implique une
# nouvelle organisation + une nouvelle licence : voir ClientCreateForm plus bas.
MODULE_FIELDS = ['can_access_patients', 'can_access_consultations', 'can_access_agenda',
                  'can_access_comptabilite', 'can_access_tags', 'can_export_backup']
TEST_FIELDS = ['can_access_vineland', 'can_access_beck', 'can_access_stai', 'can_access_d2r']
PERMISSION_FIELDS = MODULE_FIELDS + TEST_FIELDS

# Pour le psychologue (titulaire) uniquement : une case "has_x" de licence règle à la fois la
# disponibilité du test pour le cabinet ET l'accès utilisateur du psychologue (un seul interrupteur,
# voir ClientCreateForm/ClientEditForm). Ne s'applique pas aux assistant(e)s, qui gardent les deux
# cases séparées (AssistantCreateForm/AssistantEditForm) pour un contrôle plus fin.
LICENSE_TO_USER_TEST_FIELD = {
    'has_vineland': 'can_access_vineland',
    'has_beck': 'can_access_beck',
    'has_stai': 'can_access_stai',
    'has_d2r': 'can_access_d2r',
}

# Accès accordés par défaut à la création d'un(e) assistant(e) - le reste (tests, comptabilité,
# agenda, sauvegarde) est décoché par défaut et à activer explicitement au cas par cas.
DEFAULT_GRANTED_ON_CREATE = {'can_access_patients', 'can_access_consultations', 'can_access_tags'}


def _permission_widgets():
    return {field: forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}) for field in PERMISSION_FIELDS}


def _unique_slug(name):
    base = slugify(name) or 'cabinet'
    slug = base
    i = 2
    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


class AssistantCreateForm(forms.ModelForm):
    psychologue = forms.ModelChoiceField(
        queryset=User.objects.filter(role='psychologist').select_related('organization').order_by('organization__name'),
        label="Attacher au cabinet (psychologue)",
        widget=forms.Select(attrs={'class': TEXT_INPUT_CLASS}),
    )
    password1 = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={'class': TEXT_INPUT_CLASS}),
        min_length=8,
        help_text="8 caractères minimum.",
    )
    password2 = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={'class': TEXT_INPUT_CLASS}),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email'] + PERMISSION_FIELDS
        widgets = {
            'username': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': "Identifiant de connexion"}),
            'first_name': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': "Prénom"}),
            'last_name': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': "Nom"}),
            'email': forms.EmailInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': "email@exemple.com"}),
            **_permission_widgets(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in PERMISSION_FIELDS:
            self.fields[field].required = False
            if not self.is_bound:
                self.fields[field].initial = field in DEFAULT_GRANTED_ON_CREATE

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Ce nom d'utilisateur est déjà pris.")
        return username

    def clean(self):
        cleaned = super().clean()
        password1, password2 = cleaned.get('password1'), cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Les mots de passe ne correspondent pas.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'assistant'
        user.organization = self.cleaned_data['psychologue'].organization
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class AssistantEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'is_active'] + PERMISSION_FIELDS
        widgets = {
            'first_name': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS}),
            'last_name': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS}),
            'email': forms.EmailInput(attrs={'class': TEXT_INPUT_CLASS}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            **_permission_widgets(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in PERMISSION_FIELDS:
            self.fields[field].required = False


class SetPasswordForm(forms.Form):
    password1 = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput(attrs={'class': TEXT_INPUT_CLASS}),
        min_length=8,
        help_text="8 caractères minimum.",
    )
    password2 = forms.CharField(
        label="Confirmer le nouveau mot de passe",
        widget=forms.PasswordInput(attrs={'class': TEXT_INPUT_CLASS}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password1') and cleaned.get('password1') != cleaned.get('password2'):
            self.add_error('password2', "Les mots de passe ne correspondent pas.")
        return cleaned


class ClientCreateForm(forms.Form):
    """Onboarding d'un nouveau client : crée en une fois l'organisation, sa licence et le
    compte psychologue titulaire. Réservé au super admin de la plateforme."""

    # Cabinet (Organization)
    org_name = forms.CharField(label="Nom du cabinet", widget=forms.TextInput(attrs={'class': TEXT_INPUT_CLASS}))
    org_phone = forms.CharField(label="Téléphone du cabinet", required=False, widget=forms.TextInput(attrs={'class': TEXT_INPUT_CLASS}))
    org_city = forms.CharField(label="Ville", required=False, widget=forms.TextInput(attrs={'class': TEXT_INPUT_CLASS}))
    org_address = forms.CharField(label="Adresse", required=False, widget=forms.Textarea(attrs={'class': TEXT_INPUT_CLASS, 'rows': 2}))

    # Licence
    plan = forms.ChoiceField(
        label="Formule", choices=License.PLAN_CHOICES, initial='trial',
        widget=forms.Select(attrs={'class': TEXT_INPUT_CLASS}),
    )
    max_patients = forms.IntegerField(
        label="Nombre max de patients", initial=10, min_value=1,
        widget=forms.NumberInput(attrs={'class': TEXT_INPUT_CLASS}),
    )
    # Un seul interrupteur par test : coché = activé sur la licence du cabinet ET utilisable
    # tout de suite par son psychologue (il n'y a qu'un seul psychologue par cabinet, donc pas
    # de raison d'activer un test sur la licence sans le lui donner - contrairement aux
    # assistant(e)s, qui peuvent avoir un accès plus restreint que lui, voir AssistantCreateForm).
    has_vineland = forms.BooleanField(label="Test Vineland", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    has_beck = forms.BooleanField(label="Test Beck", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    has_stai = forms.BooleanField(label="Test STAI", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    has_d2r = forms.BooleanField(label="Test D2R", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))

    # Accès du psychologue à ses modules (onglets) - par défaut : Patients uniquement, le
    # reste doit être coché explicitement.
    can_access_patients = forms.BooleanField(label="Patients", required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    can_access_consultations = forms.BooleanField(label="Consultations", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    can_access_agenda = forms.BooleanField(label="Agenda", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    can_access_comptabilite = forms.BooleanField(label="Comptabilité", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    can_access_tags = forms.BooleanField(label="Tags", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    can_export_backup = forms.BooleanField(label="Sauvegarde", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))

    # Compte psychologue (titulaire)
    username = forms.CharField(label="Nom d'utilisateur", widget=forms.TextInput(attrs={'class': TEXT_INPUT_CLASS}))
    first_name = forms.CharField(label="Prénom", required=False, widget=forms.TextInput(attrs={'class': TEXT_INPUT_CLASS}))
    last_name = forms.CharField(label="Nom", required=False, widget=forms.TextInput(attrs={'class': TEXT_INPUT_CLASS}))
    email = forms.EmailField(label="Email", required=False, widget=forms.EmailInput(attrs={'class': TEXT_INPUT_CLASS}))
    phone = forms.CharField(label="Téléphone personnel", required=False, widget=forms.TextInput(attrs={'class': TEXT_INPUT_CLASS}))
    license_number = forms.CharField(label="Numéro de licence professionnelle", required=False, widget=forms.TextInput(attrs={'class': TEXT_INPUT_CLASS}))
    password1 = forms.CharField(
        label="Mot de passe", widget=forms.PasswordInput(attrs={'class': TEXT_INPUT_CLASS}),
        min_length=8, help_text="8 caractères minimum.",
    )
    password2 = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput(attrs={'class': TEXT_INPUT_CLASS}))

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Ce nom d'utilisateur est déjà pris.")
        return username

    def clean_org_name(self):
        org_name = self.cleaned_data['org_name']
        if Organization.objects.filter(name__iexact=org_name).exists():
            raise forms.ValidationError("Un cabinet avec ce nom existe déjà.")
        return org_name

    def clean(self):
        cleaned = super().clean()
        password1, password2 = cleaned.get('password1'), cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Les mots de passe ne correspondent pas.")
        return cleaned

    def save(self):
        data = self.cleaned_data
        organization = Organization.objects.create(
            name=data['org_name'],
            slug=_unique_slug(data['org_name']),
            phone=data['org_phone'],
            address=data['org_address'],
            city=data['org_city'],
        )
        License.objects.create(
            organization=organization,
            plan=data['plan'],
            status='active',
            max_patients=data['max_patients'],
            has_vineland=data['has_vineland'],
            has_beck=data['has_beck'],
            has_stai=data['has_stai'],
            has_d2r=data['has_d2r'],
        )
        user = User(
            username=data['username'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data['email'],
            phone=data['phone'],
            license_number=data['license_number'],
            role='psychologist',
            organization=organization,
            **{field: data[field] for field in MODULE_FIELDS},
            **{user_field: data[license_field] for license_field, user_field in LICENSE_TO_USER_TEST_FIELD.items()},
        )
        user.set_password(data['password1'])
        user.save()
        return organization, user


class ClientEditForm(forms.Form):
    """Édition d'un cabinet existant : infos du cabinet, licence, et accès du psychologue
    titulaire dans son propre cabinet. Réservé au super admin de la plateforme."""

    org_name = forms.CharField(label="Nom du cabinet", widget=forms.TextInput(attrs={'class': TEXT_INPUT_CLASS}))
    org_phone = forms.CharField(label="Téléphone du cabinet", required=False, widget=forms.TextInput(attrs={'class': TEXT_INPUT_CLASS}))
    org_city = forms.CharField(label="Ville", required=False, widget=forms.TextInput(attrs={'class': TEXT_INPUT_CLASS}))
    org_address = forms.CharField(label="Adresse", required=False, widget=forms.Textarea(attrs={'class': TEXT_INPUT_CLASS, 'rows': 2}))

    plan = forms.ChoiceField(label="Formule", choices=License.PLAN_CHOICES, widget=forms.Select(attrs={'class': TEXT_INPUT_CLASS}))
    status = forms.ChoiceField(label="Statut de la licence", choices=License.STATUS_CHOICES, widget=forms.Select(attrs={'class': TEXT_INPUT_CLASS}))
    max_patients = forms.IntegerField(label="Nombre max de patients", min_value=1, widget=forms.NumberInput(attrs={'class': TEXT_INPUT_CLASS}))
    has_vineland = forms.BooleanField(label="Test Vineland", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    has_beck = forms.BooleanField(label="Test Beck", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    has_stai = forms.BooleanField(label="Test STAI", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    has_d2r = forms.BooleanField(label="Test D2R", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))

    can_access_patients = forms.BooleanField(label="Patients", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    can_access_consultations = forms.BooleanField(label="Consultations", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    can_access_agenda = forms.BooleanField(label="Agenda", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    can_access_comptabilite = forms.BooleanField(label="Comptabilité", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    can_access_tags = forms.BooleanField(label="Tags", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))
    can_export_backup = forms.BooleanField(label="Sauvegarde", required=False, widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}))

    def __init__(self, organization, *args, **kwargs):
        self.organization = organization
        self.psychologue = organization.users.filter(role='psychologist').order_by('id').first()

        if not args and 'data' not in kwargs:
            license = getattr(organization, 'license', None)
            initial = {
                'org_name': organization.name, 'org_phone': organization.phone,
                'org_city': organization.city, 'org_address': organization.address,
            }
            if license:
                initial.update({
                    'plan': license.plan, 'status': license.status, 'max_patients': license.max_patients,
                    'has_vineland': license.has_vineland, 'has_beck': license.has_beck,
                    'has_stai': license.has_stai, 'has_d2r': license.has_d2r,
                })
            if self.psychologue:
                initial.update({field: getattr(self.psychologue, field) for field in MODULE_FIELDS})
            kwargs['initial'] = initial

        super().__init__(*args, **kwargs)

    def clean_org_name(self):
        org_name = self.cleaned_data['org_name']
        if Organization.objects.filter(name__iexact=org_name).exclude(id=self.organization.id).exists():
            raise forms.ValidationError("Un cabinet avec ce nom existe déjà.")
        return org_name

    def save(self):
        data = self.cleaned_data
        organization = self.organization

        organization.name = data['org_name']
        organization.phone = data['org_phone']
        organization.city = data['org_city']
        organization.address = data['org_address']
        organization.save()

        license, _ = License.objects.get_or_create(organization=organization)
        license.plan = data['plan']
        license.status = data['status']
        license.max_patients = data['max_patients']
        license.has_vineland = data['has_vineland']
        license.has_beck = data['has_beck']
        license.has_stai = data['has_stai']
        license.has_d2r = data['has_d2r']
        license.save()

        if self.psychologue:
            for field in MODULE_FIELDS:
                setattr(self.psychologue, field, data[field])
            for license_field, user_field in LICENSE_TO_USER_TEST_FIELD.items():
                setattr(self.psychologue, user_field, data[license_field])
            self.psychologue.save()

        return organization
