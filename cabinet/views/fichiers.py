import os
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from ..models import Patient, PatientFichier
from ..forms import PatientFichierForm


@login_required
def fichier_upload(request, patient_id):
    """Upload un fichier pour un patient"""
    patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)

    if request.method == 'POST':
        form = PatientFichierForm(request.POST, request.FILES)
        if form.is_valid():
            fichier = form.save(commit=False)
            fichier.patient = patient
            fichier.organization = request.user.organization
            fichier.save()
            messages.success(request, f"Fichier '{fichier.nom_fichier}' uploadé avec succès !")
            return redirect('cabinet:patient_detail', patient_id=patient.id)
        else:
            messages.error(request, "Erreur lors de l'upload du fichier.")
    else:
        form = PatientFichierForm()

    context = {
        'form': form,
        'patient': patient,
        'title': f'Ajouter un fichier pour {patient.nom_complet}'
    }

    return render(request, 'cabinet/fichier_upload.html', context)


@login_required
def fichier_delete(request, patient_id, fichier_id):
    """Supprimer un fichier"""
    patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)
    fichier = get_object_or_404(PatientFichier, id=fichier_id, patient=patient)

    if request.method == 'POST':
        nom = fichier.nom_fichier
        # Supprimer le fichier physique
        if fichier.fichier:
            if os.path.isfile(fichier.fichier.path):
                os.remove(fichier.fichier.path)
        fichier.delete()
        messages.success(request, f"Fichier '{nom}' supprimé.")
        return redirect('cabinet:patient_detail', patient_id=patient.id)

    context = {
        'fichier': fichier,
        'patient': patient
    }

    return render(request, 'cabinet/fichier_delete.html', context)


@login_required
def fichier_download(request, patient_id, fichier_id):
    """Télécharger un fichier"""
    patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)
    fichier = get_object_or_404(PatientFichier, id=fichier_id, patient=patient)

    if not fichier.fichier or not os.path.isfile(fichier.fichier.path):
        raise Http404("Fichier introuvable")

    response = FileResponse(open(fichier.fichier.path, 'rb'))
    response['Content-Disposition'] = f'attachment; filename="{fichier.nom_fichier}"'

    return response


@login_required
def fichier_preview(request, patient_id, fichier_id):
    """Prévisualiser un fichier (images et PDF)"""
    patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)
    fichier = get_object_or_404(PatientFichier, id=fichier_id, patient=patient)

    if not fichier.fichier or not os.path.isfile(fichier.fichier.path):
        raise Http404("Fichier introuvable")

    # Pour les images et PDF, on peut les afficher directement
    if fichier.est_image or fichier.est_pdf:
        response = FileResponse(open(fichier.fichier.path, 'rb'))
        response['Content-Disposition'] = f'inline; filename="{fichier.nom_fichier}"'
        return response
    else:
        # Pour les autres types, on télécharge
        return fichier_download(request, patient_id, fichier_id)
