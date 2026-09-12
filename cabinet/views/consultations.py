from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from ..models import Patient, Consultation
from ..forms import ConsultationForm
from ..invoices import generate_invoice_pdf


@login_required
def consultations_list(request):
    """Liste des consultations"""

    if request.user.is_superadmin():
        consultations = Consultation.all_objects.select_related('patient').all()
    else:
        consultations = Consultation.objects.select_related('patient').all()

    # Filtres
    lieu_filter = request.GET.get('lieu', '')
    if lieu_filter:
        consultations = consultations.filter(lieu_consultation=lieu_filter)

    statut_filter = request.GET.get('statut', '')
    if statut_filter:
        consultations = consultations.filter(statut_paiement=statut_filter)

    # Pagination
    paginator = Paginator(consultations.order_by('-date_seance'), 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'lieu_filter': lieu_filter,
        'statut_filter': statut_filter,
    }

    return render(request, 'cabinet/consultations_list.html', context)


@login_required
def consultation_create(request):
    """Créer une consultation"""

    if request.method == 'POST':
        form = ConsultationForm(request.POST, request=request)
        if form.is_valid():
            consultation = form.save(commit=False)
            consultation.organization = consultation.patient.organization
            consultation.save()

            messages.success(request, "Consultation créée!")

            return redirect('cabinet:consultation_detail', consultation_id=consultation.id)
    else:
        form = ConsultationForm(request=request)

    context = {
        'form': form,
        'title': 'Nouvelle Consultation',
    }

    return render(request, 'cabinet/consultation_form.html', context)


@login_required
def consultation_detail(request, consultation_id):
    """Détails d'une consultation"""

    if request.user.is_superadmin():
        consultation = get_object_or_404(
            Consultation.all_objects.select_related('patient'),
            id=consultation_id
        )
    else:
        consultation = get_object_or_404(
            Consultation.objects.select_related('patient'),
            id=consultation_id
        )

    context = {'consultation': consultation}
    return render(request, 'cabinet/consultation_detail.html', context)


@login_required
def consultation_edit(request, consultation_id):
    """Modifier une consultation"""

    if request.user.is_superadmin():
        consultation = get_object_or_404(Consultation.all_objects, id=consultation_id)
    else:
        consultation = get_object_or_404(Consultation, id=consultation_id)

    if request.method == 'POST':
        form = ConsultationForm(request.POST, instance=consultation, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, "Consultation modifiée!")
            return redirect('cabinet:consultation_detail', consultation_id=consultation.id)
    else:
        form = ConsultationForm(instance=consultation, request=request)

    context = {
        'form': form,
        'consultation': consultation,
        'title': 'Modifier Consultation',
    }

    return render(request, 'cabinet/consultation_form.html', context)


@login_required
def consultation_reporter(request, consultation_id):
    """Reporter une consultation"""
    consultation = get_object_or_404(
        Consultation,
        id=consultation_id,
        patient__organization=request.user.organization
    )

    if request.method == 'POST':
        # Nouvelle date - parser la string en datetime
        nouvelle_date_str = request.POST.get('nouvelle_date')
        nouvelle_date = parse_datetime(nouvelle_date_str)

        if not nouvelle_date:
            messages.error(request, "Format de date invalide")
            return redirect('cabinet:consultation_reporter', consultation_id=consultation.id)

        motif_report = request.POST.get('motif_report', '')
        consultation.reporter(nouvelle_date, motif_report)

        messages.success(request, f"Consultation reportée au {nouvelle_date.strftime('%d/%m/%Y à %H:%M')}")
        return redirect('cabinet:consultation_detail', consultation_id=consultation.id)

    context = {
        'consultation': consultation,
        'title': 'Reporter la consultation'
    }
    return render(request, 'cabinet/consultation_reporter.html', context)


@login_required
def consultation_annuler(request, consultation_id):
    """Annuler une consultation"""
    consultation = get_object_or_404(
        Consultation,
        id=consultation_id,
        patient__organization=request.user.organization
    )

    if request.method == 'POST':
        motif_annulation = request.POST.get('motif_annulation', '')

        consultation.annuler(motif_annulation)

        messages.warning(request, "Consultation annulée")
        return redirect('cabinet:consultation_detail', consultation_id=consultation.id)

    context = {
        'consultation': consultation,
        'title': 'Annuler la consultation'
    }
    return render(request, 'cabinet/consultation_annuler.html', context)


@login_required
def consultation_confirmer_paiement(request, consultation_id):
    """Confirmer le paiement d'une consultation"""

    if request.user.is_superadmin():
        consultation = get_object_or_404(Consultation.all_objects, id=consultation_id)
    else:
        consultation = get_object_or_404(
            Consultation,
            id=consultation_id,
            patient__organization=request.user.organization
        )

    if request.method == 'POST':
        consultation.statut_paiement = 'paye'
        consultation.date_paiement = timezone.localdate()
        consultation.save()

        messages.success(request, f"Paiement de {consultation.tarif} DHS confirmé avec succès!")
        return redirect('cabinet:consultation_detail', consultation_id=consultation.id)

    # Si GET, rediriger vers la page de détail
    return redirect('cabinet:consultation_detail', consultation_id=consultation.id)


@login_required
def consultation_delete(request, consultation_id):
    """Supprimer une consultation"""

    if request.user.is_superadmin():
        consultation = get_object_or_404(Consultation.all_objects, id=consultation_id)
    else:
        consultation = get_object_or_404(Consultation, id=consultation_id)

    if request.method == 'POST':
        consultation.delete()
        messages.success(request, "Consultation supprimée.")
        return redirect('cabinet:consultations_list')

    context = {'consultation': consultation}
    return render(request, 'cabinet/consultation_delete.html', context)


@login_required
def consultation_invoice(request, consultation_id):
    """Génère la facture PDF d'une consultation"""

    if request.user.is_superadmin():
        consultation = get_object_or_404(
            Consultation.all_objects.select_related('patient', 'organization'),
            id=consultation_id
        )
    else:
        consultation = get_object_or_404(
            Consultation.objects.select_related('patient', 'organization'),
            id=consultation_id
        )

    pdf_bytes = generate_invoice_pdf(consultation)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="facture_consultation_{consultation.id}.pdf"'
    return response


@login_required
@require_http_methods(["POST"])
def consultation_create_ajax(request):
    """Création de consultation via AJAX"""
    try:
        organization = request.user.organization
        patient_id = request.POST.get('patient')
        patient = Patient.objects.get(id=patient_id, organization=organization)

        # Combiner date et heure en un seul DateTimeField
        date_str = request.POST.get('date')
        heure_str = request.POST.get('heure')
        date_seance = timezone.datetime.strptime(f"{date_str} {heure_str}", "%Y-%m-%d %H:%M")
        date_seance = timezone.make_aware(date_seance)

        consultation = Consultation.objects.create(
            patient=patient,
            organization=organization,
            date_seance=date_seance,
            duree_minutes=int(request.POST.get('duree', 60)),
            type_consultation=request.POST.get('type_consultation', 'individuelle'),
            statut_consultation=request.POST.get('statut', 'planifie'),
            notes_cliniques=request.POST.get('notes', ''),
            tarif=0,  # Tu peux adapter selon tes besoins
            lieu_consultation='visio'  # Valeur par défaut
        )

        return JsonResponse({'success': True, 'id': consultation.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def consultation_edit_ajax(request, pk):
    """Modification de consultation via AJAX"""
    try:
        if request.user.is_superadmin():
            consultation = Consultation.all_objects.get(pk=pk)
        else:
            consultation = Consultation.objects.get(pk=pk)

        # Combiner date et heure
        date_str = request.POST.get('date')
        heure_str = request.POST.get('heure')
        date_seance = timezone.datetime.strptime(f"{date_str} {heure_str}", "%Y-%m-%d %H:%M")
        date_seance = timezone.make_aware(date_seance)

        consultation.date_seance = date_seance
        consultation.duree_minutes = int(request.POST.get('duree', 60))
        consultation.type_consultation = request.POST.get('type_consultation')
        consultation.statut_consultation = request.POST.get('statut')
        consultation.notes_cliniques = request.POST.get('notes', '')
        consultation.save()

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
