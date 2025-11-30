from django.http import HttpResponse
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
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from io import BytesIO
    
    test = get_object_or_404(TestBeck, id=test_id, organization=request.user.organization)
    
    # Récupérer toutes les réponses
    reponses = test.reponses.select_related('item').prefetch_related('phrases_cochees').order_by('item__numero')
    
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
    
    # Créer le buffer pour le PDF
    buffer = BytesIO()
    
    # Créer le document PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Container pour les éléments
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#4F46E5'),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#4F46E5'),
        spaceAfter=10,
        spaceBefore=15,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=5
    )
    
    # Titre
    elements.append(Paragraph("INVENTAIRE DE DÉPRESSION DE BECK (BDI-II)", title_style))
    elements.append(Paragraph(f"Date du test : {test.date_passation.strftime('%d/%m/%Y à %H:%M')}", subtitle_style))
    elements.append(Spacer(1, 0.5*cm))
    
    # Informations Patient
    elements.append(Paragraph("Informations Patient", section_style))
    
    patient_data = [
        ['Nom', test.patient.nom_complet],
        ['Date de naissance', f"{test.patient.date_naissance.strftime('%d/%m/%Y')} ({test.patient.age} ans)"],
        ['Psychologue', test.psychologue.get_full_name()]
    ]
    
    patient_table = Table(patient_data, colWidths=[5*cm, 10*cm])
    patient_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F3F4F6')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(patient_table)
    elements.append(Spacer(1, 1*cm))
    
    # Score total
    score_style = ParagraphStyle(
        'Score',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER,
        spaceAfter=3
    )
    
    big_score_style = ParagraphStyle(
        'BigScore',
        parent=styles['Normal'],
        fontSize=48,
        textColor=colors.HexColor('#4F46E5'),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=1
    )
    
    score_data = [
        [Paragraph("SCORE TOTAL", score_style)],
        [Paragraph(f"{test.score_total}", big_score_style)],
        [Paragraph("", score_style)]
    ]
    
    score_table = Table(score_data, colWidths=[15*cm])
    score_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EEF2FF')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#C7D2FE')),
    ]))
    elements.append(score_table)
    elements.append(Spacer(1, 0.8*cm))
    
    # Niveau de dépression
    niveau_colors = {
        'minimale': ('#D1FAE5', '#065F46', '0-9 points'),
        'legere': ('#FEF3C7', '#92400E', '10-18 points'),
        'moderee': ('#FFEDD5', '#9A3412', '19-29 points'),
        'severe': ('#FEE2E2', '#991B1B', '30-63 points'),
    }
    
    bg_color, text_color, range_text = niveau_colors.get(
        test.niveau_depression, 
        ('#F3F4F6', '#000000', '')
    )
    
    niveau_style = ParagraphStyle(
        'Niveau',
        parent=styles['Normal'],
        fontSize=18,
        textColor=colors.HexColor(text_color),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=5
    )
    
    range_style = ParagraphStyle(
        'Range',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor(text_color),
        alignment=TA_CENTER,
    )
    
    niveau_data = [
        [Paragraph(test.get_niveau_depression_display().upper(), niveau_style)],
        [Paragraph(range_text, range_style)]
    ]
    
    niveau_table = Table(niveau_data, colWidths=[15*cm])
    niveau_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(bg_color)),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(text_color)),
    ]))
    elements.append(niveau_table)
    elements.append(Spacer(1, 1*cm))
    
    # Footer
    elements.append(Spacer(1, 2*cm))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    
    footer_text = f"Document généré le {test.date_passation.strftime('%d/%m/%Y')} • Inventaire de Dépression de Beck (BDI-II)"
    elements.append(Paragraph(footer_text, footer_style))
    
    # Construire le PDF
    doc.build(elements)
    
    # Récupérer le PDF du buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    # Créer la réponse HTTP avec le PDF
    response = HttpResponse(pdf, content_type='application/pdf')
    filename = f"Beck_BDI_{test.patient.nom}_{test.patient.prenom}_{test.date_passation.strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

