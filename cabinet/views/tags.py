from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods

from ..models import Tag, Patient


@login_required
def tags_list(request):
    tags = Tag.objects.all()
    return render(request, 'cabinet/tags_list.html', {'tags': tags})


@login_required
@require_http_methods(["POST"])
def tag_create(request):
    nom = request.POST.get('nom', '').strip()
    couleur = request.POST.get('couleur', '#e879f9')

    if nom:
        Tag.objects.get_or_create(
            organization=request.user.organization, nom=nom,
            defaults={'couleur': couleur},
        )
        messages.success(request, f"Tag « {nom} » créé.")
    return redirect('cabinet:tags_list')


@login_required
@require_http_methods(["POST"])
def tag_delete(request, tag_id):
    tag = get_object_or_404(Tag, id=tag_id)
    tag.delete()
    messages.success(request, "Tag supprimé.")
    return redirect('cabinet:tags_list')


@login_required
@require_http_methods(["POST"])
def patient_tags_update(request, patient_id):
    """Met à jour les tags assignés à un patient (depuis la fiche patient)"""
    patient = get_object_or_404(Patient, id=patient_id)
    tag_ids = request.POST.getlist('tags')
    patient.tags.set(Tag.objects.filter(id__in=tag_ids))
    return redirect('cabinet:patient_detail', patient_id=patient.id)
