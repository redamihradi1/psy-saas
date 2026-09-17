from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .decorators import superadmin_required
from .models import User, Organization, License
from .forms import AssistantCreateForm, AssistantEditForm, SetPasswordForm, ClientCreateForm, ClientEditForm


def _post_login_redirect(user):
    """Le super admin de la plateforme n'a rien à faire sur le dashboard d'un cabinet - il
    atterrit directement sur la vue d'ensemble des clients."""
    if user.is_superadmin():
        return redirect('accounts:clients_list')
    return redirect('cabinet:dashboard')


def home_view(request):
    """Page d'accueil publique. Un utilisateur déjà connecté n'a rien à faire sur la
    page marketing - il est renvoyé directement vers son espace."""
    if request.user.is_authenticated:
        return _post_login_redirect(request.user)
    return render(request, 'home.html')


def login_view(request):
    if request.user.is_authenticated:
        return _post_login_redirect(request.user)

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f'Bienvenue {user.get_full_name()}!')
            return _post_login_redirect(user)
        else:
            messages.error(request, 'Identifiants incorrects')

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'Déconnexion réussie')
    return redirect('accounts:login')

@login_required
def profile_view(request):
    """Page Mon compte - Affichage des infos (lecture seule)"""
    return render(request, 'accounts/profile.html')


@login_required
def settings_view(request):
    """Page Paramètres - Modification des infos et mot de passe"""
    if request.method == 'POST':
        # Modification des infos personnelles
        if 'update_profile' in request.POST:
            user = request.user
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.email = request.POST.get('email', '')
            user.phone = request.POST.get('phone', '')
            user.license_number = request.POST.get('license_number', '')
            user.save()
            
            messages.success(request, 'Vos informations ont été mises à jour avec succès !')
            return redirect('accounts:settings')
        
        # Changement de mot de passe
        elif 'change_password' in request.POST:
            form = PasswordChangeForm(request.user, request.POST)
            if form.is_valid():
                user = form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Votre mot de passe a été changé avec succès !')
                return redirect('accounts:settings')
            else:
                messages.error(request, 'Erreur lors du changement de mot de passe.')
                return render(request, 'accounts/settings.html', {'form': form})
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'accounts/settings.html', {'form': form})


## --- Administration plateforme (super admin uniquement) --------------------------------
## Chaque psychologue = une organisation + une licence propres. Créer un nouveau psychologue
## crée donc les trois à la fois (voir client_create). Un(e) assistant(e), lui/elle, est
## toujours créé(e) par le super admin et attaché(e) à un psychologue existant (= son org).


@superadmin_required
def clients_list(request):
    """Vue d'ensemble de la plateforme : liste des cabinets + stats globales, tous clients confondus."""
    from django.db.models import Sum
    from cabinet.models import Patient, Consultation

    organizations = Organization.objects.select_related('license').prefetch_related('users').order_by('-created_at')

    total_clients = organizations.count()
    total_patients = Patient.objects.count()
    total_consultations = Consultation.objects.count()
    licences_actives = sum(1 for org in organizations if getattr(org, 'license', None) and org.license.is_active())

    today = timezone.now().date()
    ca_mois_plateforme = Consultation.objects.filter(
        statut_paiement='paye', date_seance__year=today.year, date_seance__month=today.month,
    ).aggregate(total=Sum('tarif'))['total'] or 0

    licences_a_surveiller = [
        org for org in organizations
        if getattr(org, 'license', None) and (
            not org.license.is_active() or org.license.expire_bientot()
        )
    ]

    return render(request, 'accounts/clients_list.html', {
        'organizations': organizations,
        'total_clients': total_clients,
        'total_patients': total_patients,
        'total_consultations': total_consultations,
        'licences_actives': licences_actives,
        'ca_mois_plateforme': ca_mois_plateforme,
        'licences_a_surveiller': licences_a_surveiller,
    })


@superadmin_required
def client_create(request):
    """Onboarding d'un nouveau client : organisation + licence + compte psychologue en une fois."""
    if request.method == 'POST':
        form = ClientCreateForm(request.POST)
        if form.is_valid():
            organization, user = form.save()
            messages.success(request, f"Cabinet « {organization.name} » créé avec le compte {user.username}.")
            return redirect('accounts:clients_list')
    else:
        form = ClientCreateForm()

    return render(request, 'accounts/client_form.html', {'form': form, 'mode': 'create'})


@superadmin_required
def client_edit(request, org_id):
    """Modification d'un cabinet existant : infos, licence, et accès du psychologue titulaire."""
    organization = get_object_or_404(Organization, id=org_id)

    if request.method == 'POST':
        form = ClientEditForm(organization, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Cabinet « {organization.name} » mis à jour.")

            from cabinet.models import Patient
            nb_patients = Patient.objects.filter(organization=organization).count()
            nouvelle_limite = form.cleaned_data['max_patients']
            if nouvelle_limite < nb_patients:
                messages.warning(
                    request,
                    f"Attention : la limite ({nouvelle_limite}) est inférieure au nombre de "
                    f"patients déjà enregistrés ({nb_patients}). Rien n'est supprimé, mais le "
                    f"cabinet ne pourra plus ajouter de nouveau patient tant qu'il n'est pas "
                    f"repassé sous la limite."
                )

            return redirect('accounts:clients_list')
    else:
        form = ClientEditForm(organization)

    return render(request, 'accounts/client_form.html', {'form': form, 'mode': 'edit', 'organization': organization})


@superadmin_required
@require_http_methods(["POST"])
def client_license_renouveler(request, org_id):
    """Marque le paiement du cycle courant comme reçu et prolonge la licence d'un cycle
    (mensuel/annuel). Suivi manuel : le superadmin encaisse lui-même puis clique ce bouton,
    aucune passerelle de paiement en ligne."""
    organization = get_object_or_404(Organization, id=org_id)
    license = getattr(organization, 'license', None)

    if not license or license.plan not in License.CYCLE_JOURS:
        messages.error(request, "Cette licence n'a pas de formule d'abonnement récurrent à renouveler.")
    else:
        license.renouveler()
        messages.success(
            request,
            f"Licence de « {organization.name} » renouvelée jusqu'au {license.end_date.strftime('%d/%m/%Y')}."
        )

    return redirect(request.POST.get('next') or 'accounts:clients_list')


@superadmin_required
def client_patients(request, org_id):
    """Historique des tests passés par les patients d'un cabinet (support/suivi), groupés par
    type de test. Pour chaque test : lien vers les résultats (lecture) et vers la page de
    passation déjà existante (pré-remplie avec les réponses actuelles) pour corriger une
    réponse et relancer le calcul - pas besoin d'un éditeur dédié, la passation le fait déjà."""
    from cabinet.models import Patient
    from tests_psy.models import TestVineland, TestBeck, TestSTAI, TestD2R

    organization = get_object_or_404(Organization, id=org_id)
    patients = Patient.objects.filter(organization=organization).order_by('nom', 'prenom')

    # Ordre d'affichage des catégories de tests
    test_sources = [
        ('Vineland', TestVineland, 'tests_psy:vineland_resultats', 'tests_psy:vineland_questionnaire'),
        ('Beck', TestBeck, 'tests_psy:beck_resultats', 'tests_psy:beck_passation'),
        ('STAI', TestSTAI, 'tests_psy:stai_resultats', 'tests_psy:stai_passation'),
        ('D2R', TestD2R, 'tests_psy:d2r_resultats', 'tests_psy:d2r_passation'),
    ]

    tests_par_patient = {}
    for label, model, resultats_url_name, edit_url_name in test_sources:
        for test in model.all_objects.filter(organization=organization):
            # Vineland "notes importées" n'a pas de réponses item par item à éditer (édition
            # dédiée), et un lien public pas encore soumis par le parent n'a rien à éditer.
            if label == 'Vineland' and getattr(test, 'mode', 'cabinet') == 'importe':
                edit_url = reverse('tests_psy:vineland_notes_importees', kwargs={'test_id': test.id})
            elif label == 'Vineland' and getattr(test, 'mode', 'cabinet') == 'lien_public' and not test.lien_soumis_le:
                edit_url = None
            else:
                edit_url = reverse(edit_url_name, kwargs={'test_id': test.id})

            tests_par_patient.setdefault(test.patient_id, {}).setdefault(label, []).append({
                'date': test.date_passation,
                'resultats_url': reverse(resultats_url_name, kwargs={'test_id': test.id}),
                'edit_url': edit_url,
            })

    categories = [source[0] for source in test_sources]

    patients_avec_tests = []
    for patient in patients:
        par_type = tests_par_patient.get(patient.id, {})
        categories_avec_tests = []
        for label in categories:
            tests = sorted(par_type.get(label, []), key=lambda t: t['date'], reverse=True)
            if tests:
                categories_avec_tests.append({'label': label, 'tests': tests})
        patients_avec_tests.append({'patient': patient, 'categories': categories_avec_tests})

    return render(request, 'accounts/client_patients.html', {
        'organization': organization,
        'patients_avec_tests': patients_avec_tests,
    })


@superadmin_required
def assistants_list(request):
    """Liste de tous les comptes assistant(e), toutes organisations confondues."""
    assistants = User.objects.filter(role='assistant').select_related('organization').order_by('organization__name', 'username')
    return render(request, 'accounts/assistants_list.html', {
        'assistants': assistants,
        'set_password_form': SetPasswordForm(),
    })


@superadmin_required
def assistant_create(request):
    """Création d'un compte assistant(e), attaché à un psychologue (= son organisation)."""
    if request.method == 'POST':
        form = AssistantCreateForm(request.POST)
        if form.is_valid():
            assistant = form.save()
            messages.success(request, f"Compte assistant(e) {assistant.username} créé, attaché à {assistant.organization.name}.")
            return redirect('accounts:assistants_list')
    else:
        form = AssistantCreateForm()

    return render(request, 'accounts/assistant_form.html', {'form': form, 'mode': 'create'})


@superadmin_required
def assistant_edit(request, user_id):
    """Modification des accès d'un(e) assistant(e)."""
    assistant = get_object_or_404(User, id=user_id, role='assistant')

    if request.method == 'POST':
        form = AssistantEditForm(request.POST, instance=assistant)
        if form.is_valid():
            form.save()
            messages.success(request, f"Accès de {assistant.username} mis à jour.")
            return redirect('accounts:assistants_list')
    else:
        form = AssistantEditForm(instance=assistant)

    return render(request, 'accounts/assistant_form.html', {'form': form, 'mode': 'edit', 'assistant': assistant})


@superadmin_required
@require_http_methods(["POST"])
def assistant_reset_password(request, user_id):
    """Réinitialisation du mot de passe d'un(e) assistant(e)."""
    assistant = get_object_or_404(User, id=user_id, role='assistant')

    form = SetPasswordForm(request.POST)
    if form.is_valid():
        assistant.set_password(form.cleaned_data['password1'])
        assistant.save()
        messages.success(request, f"Mot de passe de {assistant.username} réinitialisé.")
    else:
        messages.error(request, "Mot de passe invalide : vérifie qu'il fait au moins 8 caractères et que les deux champs correspondent.")

    return redirect('accounts:assistants_list')


@superadmin_required
@require_http_methods(["POST"])
def assistant_toggle_active(request, user_id):
    """Active ou désactive le compte d'un(e) assistant(e) (sans le supprimer)."""
    assistant = get_object_or_404(User, id=user_id, role='assistant')

    assistant.is_active = not assistant.is_active
    assistant.save()
    messages.success(request, f"Compte de {assistant.username} {'réactivé' if assistant.is_active else 'désactivé'}.")
    return redirect('accounts:assistants_list')


@superadmin_required
def admin_dashboard(request):
    """Dashboard d'un cabinet au choix, consultable par le superadmin sans se connecter
    avec le compte du psychologue. Superadmin voit toujours tous les modules (pas de
    gating par permission comme pour un psychologue/assistant(e))."""
    from cabinet.views.dashboard import build_dashboard_context

    organizations = Organization.objects.order_by('name')
    org_id = request.GET.get('org')
    if not org_id:
        return render(request, 'accounts/admin_org_picker.html', {
            'organizations': organizations,
            'page_title': 'Dashboard par cabinet',
            'page_icon': 'fas fa-chart-pie',
        })

    organization = get_object_or_404(Organization, id=org_id)
    context = build_dashboard_context(organization, True, True, True)
    context.update({
        'can_agenda': False,
        'is_admin_view': True,
        'viewed_organization': organization,
        'organizations': organizations,
    })
    return render(request, 'cabinet/dashboard.html', context)


@superadmin_required
def admin_comptabilite(request):
    """Comptabilité d'un cabinet au choix, consultable en lecture par le superadmin sans
    se connecter avec le compte du psychologue. Lecture seule (les actions d'ajout/édition/
    suppression de dépense sont masquées côté template pour ce mode)."""
    from cabinet.views.comptabilite import build_comptabilite_context, _parse_periode

    organizations = Organization.objects.order_by('name')
    org_id = request.GET.get('org')
    if not org_id:
        return render(request, 'accounts/admin_org_picker.html', {
            'organizations': organizations,
            'page_title': 'Comptabilité par cabinet',
            'page_icon': 'fas fa-coins',
        })

    organization = get_object_or_404(Organization, id=org_id)
    annee, mois = _parse_periode(request)
    context = build_comptabilite_context(organization, annee, mois)
    context.update({
        'is_admin_view': True,
        'viewed_organization': organization,
        'organizations': organizations,
    })
    return render(request, 'cabinet/comptabilite_dashboard.html', context)


@superadmin_required
def admin_agenda(request):
    """Agenda d'un cabinet au choix, consultable en lecture par le superadmin sans se
    connecter avec le compte du psychologue. Lecture seule (pas de création/blocage de
    créneau ici - le calendrier interactif complet reste réservé au psychologue)."""
    organizations = Organization.objects.order_by('name')
    org_id = request.GET.get('org')
    if not org_id:
        return render(request, 'accounts/admin_org_picker.html', {
            'organizations': organizations,
            'page_title': 'Agenda par cabinet',
            'page_icon': 'fas fa-calendar-alt',
        })

    organization = get_object_or_404(Organization, id=org_id)
    return render(request, 'accounts/admin_agenda.html', {
        'is_admin_view': True,
        'viewed_organization': organization,
        'organizations': organizations,
    })