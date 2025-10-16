from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from collections import defaultdict

from tests_psy.models import TestD2R, SymboleReference, NormeExactitude, NormeRythmeTraitement, NormeCapaciteConcentration
from tests_psy.forms import TestD2RForm, TestD2RResponseForm
from cabinet.models import Patient


@login_required
def d2r_nouveau(request, patient_id=None):
    """Créer un nouveau test D2R"""
    
    # Si patient_id fourni, le sélectionner
    patient = None
    if patient_id:
        patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)
    
    if request.method == 'POST':
        form = TestD2RForm(request.POST)
        if form.is_valid():
            test = form.save(commit=False)
            test.organization = request.user.organization
            test.psychologue = request.user
            test.reponses_correctes = 0
            test.reponses_incorrectes = 0
            test.reponses_omises = 0
            test.temps_total = 0
            test.save()
            
            messages.success(request, "Test D2R créé avec succès !")
            return redirect('tests_psy:d2r_passation', test_id=test.id)
        else:
            messages.error(request, "Erreur dans le formulaire.")
    else:
        initial = {}
        if patient:
            initial['patient'] = patient
            initial['age'] = patient.age
        form = TestD2RForm(initial=initial)
        
        # Filtrer les patients par organisation
        form.fields['patient'].queryset = Patient.objects.filter(
            organization=request.user.organization
        )
    
    context = {
        'form': form,
        'patient': patient,
        'title': 'Nouveau Test D2R'
    }
    
    return render(request, 'tests_psy/d2r/nouveau.html', context)


@login_required
def d2r_passation(request, test_id):
    """Interface de passation du test D2R"""
    test = get_object_or_404(TestD2R, id=test_id, organization=request.user.organization)
    
    # ← CORRIGÉ ICI : Plus de filtre par organization
    symbols = SymboleReference.objects.filter(page=1).order_by('ligne', 'position')
    
    symbols_by_line = defaultdict(list)
    for symbol in symbols:
        symbols_by_line[symbol.ligne].append(symbol)
    
    form = TestD2RResponseForm()
    
    context = {
        'test': test,
        'patient': test.patient,
        'symbols_by_line': dict(symbols_by_line),
        'form': form,
        'timer_seconds': 20,
    }
    
    return render(request, 'tests_psy/d2r/passation.html', context)


@login_required
def d2r_submit(request, test_id):
    """Soumettre les résultats du test"""
    if request.method != 'POST':
        return redirect('tests_psy:d2r_passation', test_id=test_id)
    
    test = get_object_or_404(TestD2R, id=test_id, organization=request.user.organization)
    
    # Récupérer les symboles sélectionnés
    selected_symbols_str = request.POST.get('selected_symbols', '')
    selected_symbols = set(int(id_) for id_ in selected_symbols_str.split(',') if id_)

    total_correctes = 0
    total_incorrectes = 0 
    total_omises = 0

    # Pour chaque ligne (de 2 à 13)
    for line_number in range(2, 14):
        # ← CORRIGÉ ICI : Plus de filtre par organization
        line_symbols = SymboleReference.objects.filter(
            page=1,
            ligne=line_number
        ).order_by('position')
        
        line_selected = [s for s in line_symbols if s.id in selected_symbols]
        
        if not line_selected:
            continue
            
        last_selected_position = max(s.position for s in line_selected)
        
        for symbol in line_symbols:
            if symbol.position > last_selected_position:
                break
                
            total_traits = symbol.traits_haut + symbol.traits_bas
            is_target = symbol.lettre == 'd' and total_traits == 2
            
            if symbol.id in selected_symbols:
                if is_target:
                    total_correctes += 1
                else:
                    total_incorrectes += 1
            else:
                if is_target:
                    total_omises += 1
    
    # Récupérer le temps total
    temps_total = int(request.POST.get('temps_total', 0))
    
    # Mettre à jour le test
    test.reponses_correctes = total_correctes
    test.reponses_incorrectes = total_incorrectes
    test.reponses_omises = total_omises
    test.temps_total = temps_total
    test.note_cct = total_correctes
    test.note_exactitude = ((total_incorrectes + total_omises) / total_correctes) * 100 if total_correctes > 0 else 0
    test.capacite_concentration = total_correctes - total_incorrectes - total_omises
    test.save()
    
    messages.success(request, "Test D2R complété avec succès !")
    return redirect('tests_psy:d2r_resultats', test_id=test_id)


@login_required
def d2r_resultats(request, test_id):
    """Afficher les résultats du test D2R"""
    test = get_object_or_404(TestD2R, id=test_id, organization=request.user.organization)
    
    # Calculs
    cct = test.reponses_correctes
    ec = test.reponses_incorrectes
    eo = test.reponses_omises or 0
    cc = cct - ec - eo
    e_percentage = ((eo + ec) / cct) * 100 if cct > 0 else 0
    e_pourcentage_sans_virgule = int(e_percentage)
    
    total_reponses = cct + ec
    precision = (cct / total_reponses * 100) if total_reponses > 0 else 0
    temps_moyen_ligne = test.temps_total / 14 if test.temps_total > 0 else 0
    
    # Récupération des normes
    norme_exactitude = NormeExactitude.objects.filter(
        age_min__lte=test.age,
        age_max__gte=test.age,
        valeur_min__lte=e_pourcentage_sans_virgule,
        valeur_max__gte=e_pourcentage_sans_virgule
    ).first()

    norme_rythme = NormeRythmeTraitement.objects.filter(
        age_min__lte=test.age,
        age_max__gte=test.age,
        valeur_min__lte=cct,
        valeur_max__gte=cct
    ).first()

    norme_concentration = NormeCapaciteConcentration.objects.filter(
        age_min__lte=test.age,
        age_max__gte=test.age,
        valeur_min__lte=cc,
        valeur_max__gte=cc
    ).first()
    
    context = {
        'test': test,
        'patient': test.patient,
        'total_reponses': total_reponses,
        'precision': round(precision, 2),
        'temps_moyen_ligne': round(temps_moyen_ligne, 1),
        'cct': cct,
        'ec': ec,
        'eo': eo,
        'cc': cc,
        'e_percentage': round(e_percentage, 2),
        'note_standard_e': norme_exactitude.note_standard if norme_exactitude else None,
        'percentile_e': norme_exactitude.percentile if norme_exactitude else None,
        'note_standard_cct': norme_rythme.note_standard if norme_rythme else None,
        'percentile_cct': norme_rythme.percentile if norme_rythme else None,
        'note_standard_cc': norme_concentration.note_standard if norme_concentration else None,
        'percentile_cc': norme_concentration.percentile if norme_concentration else None,
    }
    
    return render(request, 'tests_psy/d2r/resultats.html', context)


@login_required
def d2r_liste(request):
    """Liste de tous les tests D2R"""
    tests = TestD2R.objects.filter(
        organization=request.user.organization
    ).select_related('patient', 'psychologue').order_by('-date_passation')
    
    context = {
        'tests': tests,
        'title': 'Tests D2R'
    }
    
    return render(request, 'tests_psy/d2r/liste.html', context)


@login_required
def d2r_pdf(request, test_id):
    """Exporter les résultats en PDF (à implémenter)"""
    test = get_object_or_404(TestD2R, id=test_id, organization=request.user.organization)
    
    # TODO: Implémenter l'export PDF
    messages.info(request, "Export PDF à venir...")
    return redirect('tests_psy:d2r_resultats', test_id=test_id)