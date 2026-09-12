from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from ..models import Patient, Anamnese


@login_required
def anamnese_edit(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)
    anamnese = get_object_or_404(Anamnese, patient=patient)

    if request.method == 'POST':
        anamnese.motif_consultation = request.POST.get('motif_consultation')
        anamnese.antecedents_medicaux = request.POST.get('antecedents_medicaux', '')
        anamnese.antecedents_familiaux = request.POST.get('antecedents_familiaux', '')
        anamnese.medicaments_actuels = request.POST.get('medicaments_actuels', '')
        anamnese.consommation_substances = request.POST.get('consommation_substances', '')
        anamnese.situation_professionnelle = request.POST.get('situation_professionnelle', '')
        anamnese.situation_familiale = request.POST.get('situation_familiale', '')
        anamnese.troubles_sommeil = request.POST.get('troubles_sommeil', '')
        anamnese.troubles_alimentaires = request.POST.get('troubles_alimentaires', '')
        anamnese.activite_physique = request.POST.get('activite_physique', '')
        anamnese.hobbies_bien_etre = request.POST.get('hobbies_bien_etre', '')
        anamnese.objectifs_therapie = request.POST.get('objectifs_therapie', '')
        anamnese.attentes_patient = request.POST.get('attentes_patient', '')
        anamnese.changements_souhaites = request.POST.get('changements_souhaites', '')
        anamnese.contraintes_horaires = request.POST.get('contraintes_horaires', '')
        anamnese.niveau_stress = request.POST.get('niveau_stress', 5)
        anamnese.deja_consulte_psy = request.POST.get('deja_consulte_psy') == 'on'
        anamnese.save()

        messages.success(request, 'Anamnèse modifiée avec succès')
        return redirect('cabinet:patient_detail', patient_id=patient.id)

    return render(request, 'cabinet/anamnese_edit.html', {'patient': patient, 'anamnese': anamnese})


@login_required
def anamnese_create(request, patient_id):
    """Créer une anamnèse"""
    if request.user.is_superadmin():
        patient = get_object_or_404(Patient.all_objects, id=patient_id)
    else:
        patient = get_object_or_404(Patient, id=patient_id)

    # Vérifier si anamnèse existe déjà
    if hasattr(patient, 'anamnese'):
        messages.warning(request, "Une anamnèse existe déjà pour ce patient.")
        return redirect('cabinet:patient_detail', patient_id=patient.id)

    if request.method == 'POST':
        anamnese = Anamnese(
            patient=patient,
            motif_consultation=request.POST.get('motif_consultation', ''),
            antecedents_medicaux=request.POST.get('antecedents_medicaux', ''),
            antecedents_familiaux=request.POST.get('antecedents_familiaux', ''),
            medicaments_actuels=request.POST.get('medicaments_actuels', ''),
            situation_professionnelle=request.POST.get('situation_professionnelle', ''),
            situation_familiale=request.POST.get('situation_familiale', ''),
            troubles_sommeil=request.POST.get('troubles_sommeil', ''),
            troubles_alimentaires=request.POST.get('troubles_alimentaires', ''),
            activite_physique=request.POST.get('activite_physique', ''),
            hobbies_bien_etre=request.POST.get('hobbies_bien_etre', ''),
            changements_souhaites=request.POST.get('changements_souhaites', ''),
            consommation_substances=request.POST.get('consommation_substances', ''),
            niveau_stress=int(request.POST.get('niveau_stress', 5)),
            objectifs_therapie=request.POST.get('objectifs_therapie', ''),
            attentes_patient=request.POST.get('attentes_patient', ''),
            contraintes_horaires=request.POST.get('contraintes_horaires', ''),
            deja_consulte_psy=request.POST.get('deja_consulte_psy') == 'true',
        )
        anamnese.organization = patient.organization
        anamnese.save()
        messages.success(request, "Anamnèse créée avec succès!")
        return redirect('cabinet:patient_detail', patient_id=patient.id)

    return render(request, 'cabinet/anamnese_create.html', {'patient': patient, 'form': {}})
