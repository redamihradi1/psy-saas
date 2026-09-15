"""Vues PUBLIQUES du test Vineland - lien envoyé aux parents pour une passation à
distance, sans compte. Volontairement isolées des vues authentifiées (views.py) pour que
tout ce qui est atteignable sans connexion soit clairement identifiable dans un seul
fichier. Mirror du pattern déjà utilisé pour le flux .ics public de l'agenda
(cabinet/views/agenda.py::agenda_ics_feed) : jeton secret unique en base, aucun décorateur
d'authentification, tenant posé manuellement puisque TenantMiddleware ne le fait jamais
pour un utilisateur anonyme.
"""
from django.shortcuts import render, redirect
from django.utils import timezone

from core.middleware import set_current_tenant
from tests_psy.models import TestVineland

from .views import _build_questionnaire_context, _save_questionnaire_post


def _resolve_public_test(request, token):
    """Retourne (test, None) si le lien est valide et utilisable, ou (None, HttpResponse)
    avec une page d'erreur calme sinon. Centralise tous les contrôles - aucun ne doit
    jamais laisser fuiter une trace technique (traceback, 403 brut) au parent."""
    try:
        test = TestVineland.all_objects.select_related('organization', 'organization__license', 'patient').get(
            lien_token=token, mode='lien_public',
        )
    except TestVineland.DoesNotExist:
        return None, render(request, 'tests_psy/vineland/public/lien_invalide.html', status=404)

    if not test.organization.is_active:
        return None, render(request, 'tests_psy/vineland/public/lien_invalide.html', status=404)

    license = getattr(test.organization, 'license', None)
    if not license or not license.is_active():
        return None, render(request, 'tests_psy/vineland/public/lien_invalide.html', status=404)

    if test.lien_soumis_le is not None:
        return None, render(request, 'tests_psy/vineland/public/lien_deja_soumis.html')

    if test.lien_expire_le and test.lien_expire_le < timezone.now():
        return None, render(request, 'tests_psy/vineland/public/lien_expire.html')

    return test, None


def vineland_public_questionnaire(request, token):
    """Questionnaire Vineland rempli par les parents, à distance - même pagination et
    même sauvegarde des réponses que la passation en cabinet (vineland_questionnaire),
    mais jamais aucun lien vers les résultats/scores, et verrouillage à la soumission."""
    test, error = _resolve_public_test(request, token)
    if error:
        return error

    set_current_tenant(test.organization)
    try:
        page_number = request.GET.get('page', 1)
        page_obj, initial_data = _build_questionnaire_context(test, page_number)

        if request.method == 'POST':
            action = request.POST.get('action')
            _save_questionnaire_post(test, request.POST, page_obj.object_list)

            if action == 'previous':
                return redirect(f'{request.path}?page={int(page_number) - 1}')
            elif action == 'next':
                return redirect(f'{request.path}?page={int(page_number) + 1}')
            elif action == 'submit':
                test.lien_soumis_le = timezone.now()
                test.save(update_fields=['lien_soumis_le'])
                return redirect('tests_psy:vineland_public_merci', token=token)

        return render(request, 'tests_psy/vineland/questionnaire.html', {
            'test': test,
            'patient': test.patient,
            'page_obj': page_obj,
            'initial_data': initial_data,
            'is_public': True,
        })
    finally:
        set_current_tenant(None)


def vineland_public_merci(request, token):
    """Page de confirmation après soumission - jamais de score, jamais de résultat."""
    test = TestVineland.all_objects.filter(
        lien_token=token, mode='lien_public', lien_soumis_le__isnull=False,
    ).select_related('patient').first()

    if not test:
        return render(request, 'tests_psy/vineland/public/lien_invalide.html', status=404)

    return render(request, 'tests_psy/vineland/public/merci.html', {
        'patient_prenom': test.patient.prenom,
    })
