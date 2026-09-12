import csv
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from ..models import Consultation, Depense

MOIS_NOMS = [
    '', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
]


def _parse_periode(request):
    today = timezone.now().date()
    try:
        annee = int(request.GET.get('annee', today.year))
        mois = int(request.GET.get('mois', today.month))
        date(annee, mois, 1)
    except (ValueError, TypeError):
        annee, mois = today.year, today.month
    return annee, mois


def _mois_precedent(annee, mois):
    return (annee - 1, 12) if mois == 1 else (annee, mois - 1)


def _mois_suivant(annee, mois):
    return (annee + 1, 1) if mois == 12 else (annee, mois + 1)


@login_required
def comptabilite_dashboard(request):
    organization = request.user.organization
    annee, mois = _parse_periode(request)

    revenus_mois = Consultation.objects.filter(
        organization=organization, statut_paiement='paye',
        date_seance__year=annee, date_seance__month=mois,
    ).aggregate(total=Sum('tarif'))['total'] or 0

    depenses_qs_mois = Depense.objects.filter(
        organization=organization, date_depense__year=annee, date_depense__month=mois,
    )
    depenses_mois = depenses_qs_mois.aggregate(total=Sum('montant'))['total'] or 0
    resultat_mois = revenus_mois - depenses_mois

    revenus_annee = Consultation.objects.filter(
        organization=organization, statut_paiement='paye', date_seance__year=annee,
    ).aggregate(total=Sum('tarif'))['total'] or 0

    depenses_annee = Depense.objects.filter(
        organization=organization, date_depense__year=annee,
    ).aggregate(total=Sum('montant'))['total'] or 0
    resultat_annee = revenus_annee - depenses_annee

    # Évolution sur les 6 derniers mois (par rapport à la période sélectionnée)
    evolution = []
    a, m = annee, mois
    periode_courante = (a, m)
    for _ in range(6):
        rev = Consultation.objects.filter(
            organization=organization, statut_paiement='paye', date_seance__year=a, date_seance__month=m,
        ).aggregate(total=Sum('tarif'))['total'] or 0
        dep = Depense.objects.filter(
            organization=organization, date_depense__year=a, date_depense__month=m,
        ).aggregate(total=Sum('montant'))['total'] or 0
        evolution.append({
            'label': f"{MOIS_NOMS[m][:3]} {a}",
            'revenus': float(rev),
            'depenses': float(dep),
        })
        a, m = _mois_precedent(a, m)
    evolution.reverse()

    # Répartition des dépenses par catégorie (mois sélectionné)
    repartition_qs = depenses_qs_mois.values('categorie').annotate(total=Sum('montant'), count=Count('id'))
    categorie_dict = dict(Depense.CATEGORIE_CHOICES)
    repartition = [
        {
            'categorie_name': categorie_dict.get(r['categorie'], r['categorie']),
            'total': float(r['total']),
        }
        for r in repartition_qs
    ]

    depenses_liste = depenses_qs_mois.order_by('-date_depense')

    alertes_paiement = Consultation.objects.filter(
        organization=organization, date_seance__year=annee, date_seance__month=mois,
    ).filter(
        Q(statut_paiement='attente') | Q(tarif=0)
    ).exclude(statut_consultation='annule').select_related('patient').order_by('date_seance')

    mois_precedent = _mois_precedent(annee, mois)
    mois_suivant = _mois_suivant(annee, mois)

    context = {
        'today': timezone.now().date(),
        'annee': annee,
        'mois': mois,
        'mois_nom': MOIS_NOMS[mois],
        'mois_precedent': mois_precedent,
        'mois_suivant': mois_suivant,
        'revenus_mois': revenus_mois,
        'depenses_mois': depenses_mois,
        'resultat_mois': resultat_mois,
        'revenus_annee': revenus_annee,
        'depenses_annee': depenses_annee,
        'resultat_annee': resultat_annee,
        'evolution': evolution,
        'repartition': repartition,
        'depenses_liste': depenses_liste,
        'categories': Depense.CATEGORIE_CHOICES,
        'alertes_paiement': alertes_paiement,
    }
    return render(request, 'cabinet/comptabilite_dashboard.html', context)


@login_required
def depense_create(request):
    if request.method == 'POST':
        Depense.objects.create(
            organization=request.user.organization,
            categorie=request.POST.get('categorie', 'autre'),
            description=request.POST.get('description', ''),
            montant=request.POST.get('montant') or 0,
            date_depense=request.POST.get('date_depense') or timezone.now().date(),
        )
        messages.success(request, "Dépense ajoutée.")

    return redirect(request.POST.get('next') or 'cabinet:comptabilite_dashboard')


@login_required
def depense_edit(request, depense_id):
    depense = get_object_or_404(Depense, id=depense_id)

    if request.method == 'POST':
        depense.categorie = request.POST.get('categorie', depense.categorie)
        depense.description = request.POST.get('description', depense.description)
        depense.montant = request.POST.get('montant') or depense.montant
        depense.date_depense = request.POST.get('date_depense') or depense.date_depense
        depense.save()
        messages.success(request, "Dépense modifiée.")
        return redirect(request.POST.get('next') or 'cabinet:comptabilite_dashboard')

    return render(request, 'cabinet/depense_form.html', {
        'depense': depense,
        'categories': Depense.CATEGORIE_CHOICES,
        'next': request.GET.get('next', ''),
    })


@login_required
def depense_delete(request, depense_id):
    depense = get_object_or_404(Depense, id=depense_id)

    if request.method == 'POST':
        depense.delete()
        messages.success(request, "Dépense supprimée.")
        return redirect(request.POST.get('next') or 'cabinet:comptabilite_dashboard')

    return render(request, 'cabinet/depense_delete.html', {'depense': depense})


@login_required
def comptabilite_export_csv(request):
    organization = request.user.organization
    annee, mois = _parse_periode(request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="comptabilite_{annee}_{mois:02d}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Type', 'Date', 'Catégorie/Patient', 'Description', 'Montant (DHS)'])

    consultations = Consultation.objects.filter(
        organization=organization, statut_paiement='paye',
        date_seance__year=annee, date_seance__month=mois,
    ).select_related('patient').order_by('date_seance')
    for c in consultations:
        writer.writerow(['Revenu', c.date_seance.strftime('%d/%m/%Y'), c.patient.nom_complet, c.get_type_consultation_display(), c.tarif])

    depenses = Depense.objects.filter(
        organization=organization, date_depense__year=annee, date_depense__month=mois,
    ).order_by('date_depense')
    for d in depenses:
        writer.writerow(['Dépense', d.date_depense.strftime('%d/%m/%Y'), d.get_categorie_display(), d.description, -d.montant])

    return response
