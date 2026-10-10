"""Vues PUBLIQUES du test BRIEF - lien envoyé au parent pour remplir le questionnaire à
distance, sans compte. Même principe que tests_psy/views/vineland/public.py : jeton secret
unique en base, aucune authentification, tenant posé manuellement, jamais aucun score ni
résultat exposé. Les pages d'état (lien invalide/expiré/déjà soumis/merci) sont celles de
Vineland, rédigées sans mention du test.
"""
from django.shortcuts import render, redirect
from django.utils import timezone

from core.middleware import set_current_tenant
from tests_psy.models import TestBRIEF

from .views import _build_passation_context, _save_passation_post


def _resolve_public_test(request, token):
    """(test, None) si le lien est utilisable, sinon (None, page d'erreur calme)."""
    try:
        test = TestBRIEF.all_objects.select_related('organization', 'organization__license', 'patient').get(
            lien_token=token, mode='lien_public',
        )
    except TestBRIEF.DoesNotExist:
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


def brief_public_questionnaire(request, token):
    test, error = _resolve_public_test(request, token)
    if error:
        return error

    set_current_tenant(test.organization)
    try:
        if request.method == 'POST':
            _save_passation_post(test, request.POST)
            if request.POST.get('action') == 'submit':
                now = timezone.now()
                test.lien_soumis_le = now
                test.termine_le = now
                test.save(update_fields=['lien_soumis_le', 'termine_le'])
                return redirect('tests_psy:brief_public_merci', token=token)
            return redirect('tests_psy:brief_public_questionnaire', token=token)

        return render(request, 'tests_psy/brief/questionnaire.html', {
            'test': test,
            'patient': test.patient,
            'is_public': True,
            **_build_passation_context(test),
        })
    finally:
        set_current_tenant(None)


def brief_public_merci(request, token):
    test = TestBRIEF.all_objects.filter(
        lien_token=token, mode='lien_public', lien_soumis_le__isnull=False,
    ).select_related('patient').first()
    if not test:
        return render(request, 'tests_psy/vineland/public/lien_invalide.html', status=404)
    return render(request, 'tests_psy/vineland/public/merci.html', {'patient_prenom': test.patient.prenom})
