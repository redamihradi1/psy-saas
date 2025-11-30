from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction

from tests_psy.models import TestBeck, ItemBeck, PhraseBeck, ReponseItemBeck
from tests_psy.forms import TestBeckForm
from cabinet.models import Patient
from accounts.decorators import require_test_access


@login_required
@require_test_access('beck')
def beck_liste(request):
    """Liste de tous les tests Beck de l'organisation"""
    tests = TestBeck.objects.filter(
        organization=request.user.organization
    ).select_related('patient', 'psychologue').order_by('-date_passation')

    # Vérifier la licence
    license = request.user.organization.license
    tests_restants = license.get_tests_remaining('beck')
    peut_creer = license.can_add_test('beck')

    context = {
        'tests': tests,
        'title': 'Tests Beck (Inventaire de dépression)',
        'tests_restants': tests_restants,
        'peut_creer': peut_creer,
    }

    return render(request, 'tests_psy/beck/liste.html', context)


@login_required
@require_test_access('beck')
def beck_nouveau(request, patient_id=None):
    """Créer un nouveau test Beck"""

    # Vérifier la limite de tests
    if not request.user.is_superadmin():
        license = request.user.organization.license
        if not license.can_add_test('beck'):
            tests_restants = license.get_tests_remaining('beck')
            messages.error(
                request,
                f"Limite de tests Beck atteinte ! Votre licence autorise {license.max_tests_beck} tests Beck maximum."
            )
            return redirect('tests_psy:beck_liste')

    # Si patient_id fourni, le pré-sélectionner
    patient = None
    if patient_id:
        patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)

    if request.method == 'POST':
        form = TestBeckForm(request.POST, organization=request.user.organization)
        if form.is_valid():
            test = form.save(commit=False)
            test.organization = request.user.organization
            test.psychologue = request.user
            test.save()

            messages.success(request, "Test Beck créé avec succès !")
            return redirect('tests_psy:beck_passation', test_id=test.id)
        else:
            messages.error(request, "Erreur dans le formulaire.")
    else:
        initial = {}
        if patient:
            initial['patient'] = patient
        form = TestBeckForm(initial=initial, organization=request.user.organization)

    context = {
        'form': form,
        'patient': patient,
        'title': 'Nouveau Test Beck'
    }

    return render(request, 'tests_psy/beck/nouveau.html', context)


@login_required
@require_test_access('beck')
def beck_passation(request, test_id):
    """Interface de passation du test Beck"""
    test = get_object_or_404(TestBeck, id=test_id, organization=request.user.organization)

    if request.method == 'POST':
        # Traiter la soumission
        return beck_submit(request, test_id)

    # Récupérer tous les items avec leurs phrases
    items = ItemBeck.objects.prefetch_related('phrases').order_by('numero')

    # Récupérer les réponses existantes (si modification)
    reponses_existantes = {}
    for reponse in test.reponses.all():
        phrases_ids = list(reponse.phrases_cochees.values_list('id', flat=True))
        reponses_existantes[reponse.item.numero] = phrases_ids

    context = {
        'test': test,
        'patient': test.patient,
        'items': items,
        'reponses_existantes': reponses_existantes,
        'title': f'Test Beck - {test.patient.nom_complet}'
    }

    return render(request, 'tests_psy/beck/passation.html', context)


@login_required
@require_test_access('beck')
def beck_submit(request, test_id):
    """Traiter la soumission du test Beck"""
    if request.method != 'POST':
        return redirect('tests_psy:beck_passation', test_id=test_id)

    test = get_object_or_404(TestBeck, id=test_id, organization=request.user.organization)

    # Utiliser une transaction pour garantir la cohérence
    with transaction.atomic():
        # Supprimer les anciennes réponses (si re-soumission)
        test.reponses.all().delete()

        # Traiter les réponses pour chaque item
        items = ItemBeck.objects.all().order_by('numero')

        for item in items:
            # Récupérer les phrases cochées pour cet item
            phrases_cochees_ids = request.POST.getlist(f'item_{item.numero}')

            if phrases_cochees_ids:
                # Créer la réponse pour cet item
                reponse = ReponseItemBeck.objects.create(
                    test=test,
                    item=item,
                    organization=request.user.organization
                )

                # Ajouter les phrases cochées
                phrases = PhraseBeck.objects.filter(id__in=phrases_cochees_ids)
                reponse.phrases_cochees.set(phrases)

                # Calculer le score (max des scores des phrases cochées)
                reponse.calculer_score()

        # Calculer le score total du test
        test.calculer_score_total()

    messages.success(request, "Test Beck complété avec succès !")

    # Afficher un warning si alerte suicide
    if test.alerte_suicide:
        messages.warning(
            request,
            "⚠️ ALERTE : Le patient a exprimé des idées suicidaires (Item 9). "
            "Une évaluation approfondie et un suivi immédiat sont recommandés."
        )

    return redirect('tests_psy:beck_resultats', test_id=test.id)


@login_required
@require_test_access('beck')
def beck_resultats(request, test_id):
    """Afficher les résultats du test Beck"""
    test = get_object_or_404(TestBeck, id=test_id, organization=request.user.organization)

    # Récupérer toutes les réponses avec les items
    reponses = test.reponses.select_related('item').prefetch_related('phrases_cochees').order_by('item__numero')

    # Organiser les réponses par item
    reponses_par_item = {}
    for reponse in reponses:
        reponses_par_item[reponse.item.numero] = {
            'item': reponse.item,
            'score': reponse.score_item,
            'phrases': reponse.phrases_cochees.all()
        }

    # Récupérer les tests Beck précédents du patient pour le graphique d'évolution
    tests_precedents = TestBeck.objects.filter(
        patient=test.patient,
        organization=request.user.organization
    ).order_by('date_passation')

    # Données pour le graphique
    evolution_data = {
        'dates': [t.date_passation.strftime('%d/%m/%Y') for t in tests_precedents],
        'scores': [t.score_total for t in tests_precedents]
    }

    # Interprétation du score
    interpretation = test.interpretation_score

    # Recommandations selon le niveau
    recommandations = {
        'minimale': [
            "Absence ou présence minimale de symptômes dépressifs",
            "Continuer à surveiller l'évolution",
            "Maintenir les activités habituelles et le réseau de soutien"
        ],
        'legere': [
            "Symptômes dépressifs légers détectés",
            "Envisager un suivi psychothérapeutique",
            "Renforcer les stratégies d'adaptation (activité physique, soutien social)",
            "Réévaluer dans 2-4 semaines"
        ],
        'moderee': [
            "Dépression modérée nécessitant une intervention",
            "Psychothérapie recommandée (TCC, thérapie interpersonnelle)",
            "Évaluer la nécessité d'un traitement pharmacologique",
            "Suivi régulier et réévaluation fréquente",
            "Consulter un médecin si besoin"
        ],
        'severe': [
            "Dépression sévère - Prise en charge immédiate nécessaire",
            "Consultation psychiatrique urgente recommandée",
            "Traitement combiné (psychothérapie + pharmacothérapie)",
            "Évaluer le risque suicidaire en détail",
            "Suivi rapproché et soutien du réseau familial",
            "Envisager une hospitalisation si nécessaire"
        ]
    }

    context = {
        'test': test,
        'patient': test.patient,
        'reponses_par_item': reponses_par_item,
        'evolution_data': evolution_data,
        'interpretation': interpretation,
        'recommandations': recommandations.get(test.niveau_depression, []),
        'nb_tests_precedents': tests_precedents.count(),
        'title': f'Résultats Beck - {test.patient.nom_complet}'
    }

    return render(request, 'tests_psy/beck/resultats.html', context)


@login_required
@require_test_access('beck')
def beck_pdf(request, test_id):
    """Générer un rapport PDF du test Beck"""
    test = get_object_or_404(TestBeck, id=test_id, organization=request.user.organization)

    # Récupérer toutes les réponses
    reponses = test.reponses.select_related('item').prefetch_related('phrases_cochees').order_by('item__numero')

    # Organiser les réponses par item
    reponses_par_item = {}
    for reponse in reponses:
        reponses_par_item[reponse.item.numero] = {
            'item': reponse.item,
            'score': reponse.score_item,
            'phrases': reponse.phrases_cochees.all()
        }

    # Recommandations selon le niveau
    recommandations = {
        'minimale': [
            "Absence ou présence minimale de symptômes dépressifs",
            "Continuer à surveiller l'évolution",
        ],
        'legere': [
            "Symptômes dépressifs légers détectés",
            "Envisager un suivi psychothérapeutique",
            "Réévaluer dans 2-4 semaines"
        ],
        'moderee': [
            "Dépression modérée nécessitant une intervention",
            "Psychothérapie recommandée",
            "Évaluer la nécessité d'un traitement pharmacologique"
        ],
        'severe': [
            "Dépression sévère - Prise en charge immédiate",
            "Consultation psychiatrique urgente recommandée",
            "Évaluer le risque suicidaire en détail"
        ]
    }

    context = {
        'test': test,
        'patient': test.patient,
        'psychologue': test.psychologue,
        'organization': test.organization,
        'reponses_par_item': reponses_par_item,
        'interpretation': test.interpretation_score,
        'recommandations': recommandations.get(test.niveau_depression, []),
    }

    return render(request, 'tests_psy/beck/rapport_pdf.html', context)
