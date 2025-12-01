from django.http import HttpResponse

from django.shortcuts import render, redirect, get_object_or_404

from django.contrib.auth.decorators import login_required

from django.contrib import messages

from django.db import transaction

 

from tests_psy.models import TestSTAI, ItemSTAI, ReponseItemSTAI

from tests_psy.forms import TestSTAIForm

from cabinet.models import Patient

from accounts.decorators import require_test_access

 

 

@login_required

@require_test_access('stai')

def stai_liste(request):

    """Liste de tous les tests STAI de l'organisation"""

    tests = TestSTAI.objects.filter(

        organization=request.user.organization

    ).select_related('patient', 'psychologue').order_by('-date_passation')

 

    # Vérifier la licence

    license = request.user.organization.license

    tests_restants = license.get_tests_remaining('stai')

    peut_creer = license.can_add_test('stai')

 

    context = {

        'tests': tests,

        'title': 'Tests STAI (Inventaire d\'anxiété état-trait)',

        'tests_restants': tests_restants,

        'peut_creer': peut_creer,

    }

 

    return render(request, 'tests_psy/stai/liste.html', context)

 

 

@login_required

@require_test_access('stai')

def stai_nouveau(request, patient_id=None):

    """Créer un nouveau test STAI"""

 

    # Vérifier la limite de tests

    if not request.user.is_superadmin():

        license = request.user.organization.license

        if not license.can_add_test('stai'):

            tests_restants = license.get_tests_remaining('stai')

            messages.error(

                request,

                f"Limite de tests STAI atteinte ! Votre licence autorise {license.max_tests_stai} tests STAI maximum."

            )

            return redirect('tests_psy:stai_liste')

 

    # Si patient_id fourni, le pré-sélectionner

    patient = None

    if patient_id:

        patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)

 

    if request.method == 'POST':

        form = TestSTAIForm(request.POST, organization=request.user.organization)

        if form.is_valid():

            test = form.save(commit=False)

            test.organization = request.user.organization

            test.psychologue = request.user

            test.save()

 

            messages.success(request, "Test STAI créé avec succès !")

            return redirect('tests_psy:stai_passation', test_id=test.id)

        else:

            messages.error(request, "Erreur dans le formulaire.")

    else:

        initial = {}

        if patient:

            initial['patient'] = patient

        form = TestSTAIForm(initial=initial, organization=request.user.organization)

 

    context = {

        'form': form,

        'patient': patient,

        'title': 'Nouveau Test STAI'

    }

 

    return render(request, 'tests_psy/stai/nouveau.html', context)

 

 

@login_required

@require_test_access('stai')

def stai_passation(request, test_id):

    """Interface de passation du test STAI"""

    test = get_object_or_404(TestSTAI, id=test_id, organization=request.user.organization)

 

    if request.method == 'POST':

        # Traiter la soumission

        return stai_submit(request, test_id)

 

    # Récupérer tous les items, séparés par section

    items_etat = ItemSTAI.objects.filter(section='ETAT').order_by('numero')

    items_trait = ItemSTAI.objects.filter(section='TRAIT').order_by('numero')

 

    # Récupérer les réponses existantes (si modification)

    reponses_existantes = {}

    for reponse in test.reponses.all():

        reponses_existantes[reponse.item.numero] = reponse.valeur_choisie

 

    context = {

        'test': test,

        'patient': test.patient,

        'items_etat': items_etat,

        'items_trait': items_trait,

        'reponses_existantes': reponses_existantes,

        'title': f'Test STAI - {test.patient.nom_complet}'

    }

 

    return render(request, 'tests_psy/stai/passation.html', context)

 

 

@login_required

@require_test_access('stai')

def stai_submit(request, test_id):

    """Traiter la soumission du test STAI"""

    if request.method != 'POST':

        return redirect('tests_psy:stai_passation', test_id=test_id)

 

    test = get_object_or_404(TestSTAI, id=test_id, organization=request.user.organization)

 

    # Utiliser une transaction pour garantir la cohérence

    with transaction.atomic():

        # Supprimer les anciennes réponses (si re-soumission)

        test.reponses.all().delete()

 

        # Traiter les réponses pour les 40 items

        items = ItemSTAI.objects.all().order_by('numero')

        items_manquants = []

 

        for item in items:

            # Récupérer la valeur choisie pour cet item

            valeur_choisie = request.POST.get(f'item_{item.numero}')

 

            if valeur_choisie:

                valeur_choisie = int(valeur_choisie)

 

                # Créer la réponse pour cet item

                reponse = ReponseItemSTAI.objects.create(

                    test=test,

                    item=item,

                    valeur_choisie=valeur_choisie,

                    organization=request.user.organization

                )

 

                # Calculer le score (avec inversion si nécessaire)

                reponse.calculer_score()

            else:

                items_manquants.append(item.numero)

 

        # Vérifier que tous les items ont été répondus

        if items_manquants:

            messages.error(

                request,

                f"Veuillez répondre à tous les items. Items manquants : {', '.join(map(str, items_manquants))}"

            )

            return redirect('tests_psy:stai_passation', test_id=test.id)

 

        # Calculer les scores totaux

        test.calculer_scores()

 

    messages.success(request, "Test STAI complété avec succès !")

 

    return redirect('tests_psy:stai_resultats', test_id=test.id)

 

 

@login_required

@require_test_access('stai')

def stai_resultats(request, test_id):

    """Afficher les résultats du test STAI"""

    test = get_object_or_404(TestSTAI, id=test_id, organization=request.user.organization)

 

    # Récupérer toutes les réponses avec les items

    reponses = test.reponses.select_related('item').order_by('item__numero')

 

    # Organiser les réponses par section

    reponses_etat = reponses.filter(item__section='ETAT')

    reponses_trait = reponses.filter(item__section='TRAIT')

 

    # Récupérer les tests STAI précédents du patient pour le graphique d'évolution

    tests_precedents = TestSTAI.objects.filter(

        patient=test.patient,

        organization=request.user.organization

    ).order_by('date_passation')

 

    # Données pour les graphiques

    evolution_data_etat = {

        'dates': [t.date_passation.strftime('%d/%m/%Y') for t in tests_precedents],

        'scores': [t.score_etat for t in tests_precedents]

    }

 

    evolution_data_trait = {

        'dates': [t.date_passation.strftime('%d/%m/%Y') for t in tests_precedents],

        'scores': [t.score_trait for t in tests_precedents]

    }

 

    # Recommandations selon le niveau

    recommandations = {

        'minimale': [

            "Absence ou présence minimale d'anxiété",

            "Continuer à surveiller l'évolution",

            "Maintenir les stratégies d'adaptation actuelles"

        ],

        'faible': [

            "Anxiété faible, dans les limites normales",

            "Renforcer les stratégies de gestion du stress",

            "Réévaluer si nécessaire"

        ],

        'moderee': [

            "Anxiété modérée détectée",

            "Envisager un suivi psychothérapeutique",

            "Techniques de relaxation et gestion du stress recommandées",

            "Réévaluer dans 2-4 semaines"

        ],

        'elevee': [

            "Anxiété élevée nécessitant une attention",

            "Psychothérapie recommandée (TCC, relaxation)",

            "Évaluer l'impact sur le fonctionnement quotidien",

            "Suivi régulier conseillé"

        ],

        'tres_elevee': [

            "Anxiété très élevée - Prise en charge recommandée",

            "Consultation spécialisée fortement recommandée",

            "Traitement combiné possible (psychothérapie + pharmacothérapie)",

            "Suivi rapproché nécessaire",

            "Évaluer les impacts sur la vie quotidienne"

        ]

    }

 

    context = {

        'test': test,

        'patient': test.patient,

        'reponses_etat': reponses_etat,

        'reponses_trait': reponses_trait,

        'evolution_data_etat': evolution_data_etat,

        'evolution_data_trait': evolution_data_trait,

        'recommandations_etat': recommandations.get(test.niveau_anxiete_etat, []),

        'recommandations_trait': recommandations.get(test.niveau_anxiete_trait, []),

        'nb_tests_precedents': tests_precedents.count(),

        'title': f'Résultats STAI - {test.patient.nom_complet}'

    }

 

    return render(request, 'tests_psy/stai/resultats.html', context)

 

 

@login_required

@require_test_access('stai')

def stai_pdf(request, test_id):

    """Générer un rapport PDF du test STAI"""

    from reportlab.lib.pagesizes import A4

    from reportlab.lib import colors

    from reportlab.lib.units import cm

    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    from io import BytesIO

 

    test = get_object_or_404(TestSTAI, id=test_id, organization=request.user.organization)

 

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

        fontSize=18,

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

 

    # Titre

    elements.append(Paragraph("INVENTAIRE D'ANXIÉTÉ ÉTAT-TRAIT (STAI)", title_style))

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

    elements.append(Spacer(1, 0.8*cm))

 

    # Scores

    elements.append(Paragraph("Résultats", section_style))

 

    # Couleurs selon le niveau

    niveau_colors = {

        'minimale': ('#D1FAE5', '#065F46'),

        'faible': ('#FEF3C7', '#92400E'),

        'moderee': ('#FFEDD5', '#9A3412'),

        'elevee': ('#FED7D7', '#9B2C2C'),

        'tres_elevee': ('#FEE2E2', '#991B1B'),

    }

 

    # Score ÉTAT

    bg_color_etat, text_color_etat = niveau_colors.get(

        test.niveau_anxiete_etat,

        ('#F3F4F6', '#000000')

    )

 

    score_data_etat = [

        [Paragraph(f"<b>ANXIÉTÉ ÉTAT (Y1)</b>", styles['Normal'])],

        [Paragraph(f"<font size=24><b>{test.score_etat}</b></font> / 80", styles['Normal'])],

        [Paragraph(f"<b>{test.niveau_etat_display}</b>", styles['Normal'])]

    ]

 

    score_table_etat = Table(score_data_etat, colWidths=[7*cm])

    score_table_etat.setStyle(TableStyle([

        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(bg_color_etat)),

        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(text_color_etat)),

        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),

        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        ('TOPPADDING', (0, 0), (-1, -1), 10),

        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),

        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(text_color_etat)),

    ]))

 

    # Score TRAIT

    bg_color_trait, text_color_trait = niveau_colors.get(

        test.niveau_anxiete_trait,

        ('#F3F4F6', '#000000')

    )

 

    score_data_trait = [

        [Paragraph(f"<b>ANXIÉTÉ TRAIT (Y2)</b>", styles['Normal'])],

        [Paragraph(f"<font size=24><b>{test.score_trait}</b></font> / 80", styles['Normal'])],

        [Paragraph(f"<b>{test.niveau_trait_display}</b>", styles['Normal'])]

    ]

 

    score_table_trait = Table(score_data_trait, colWidths=[7*cm])

    score_table_trait.setStyle(TableStyle([

        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(bg_color_trait)),

        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(text_color_trait)),

        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),

        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        ('TOPPADDING', (0, 0), (-1, -1), 10),

        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),

        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(text_color_trait)),

    ]))

 

    # Mettre les deux scores côte à côte

    scores_table = Table([[score_table_etat, score_table_trait]], colWidths=[7.5*cm, 7.5*cm])

    scores_table.setStyle(TableStyle([

        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),

        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

    ]))

 

    elements.append(scores_table)

    elements.append(Spacer(1, 1*cm))

 

    # Footer

    footer_style = ParagraphStyle(

        'Footer',

        parent=styles['Normal'],

        fontSize=8,

        textColor=colors.grey,

        alignment=TA_CENTER

    )

 

    footer_text = f"Document généré le {test.date_passation.strftime('%d/%m/%Y')} • Inventaire d'Anxiété État-Trait de Spielberger (STAI)"

    elements.append(Paragraph(footer_text, footer_style))

 

    # Construire le PDF

    doc.build(elements)

 

    # Récupérer le PDF du buffer

    pdf = buffer.getvalue()

    buffer.close()

 

    # Créer la réponse HTTP avec le PDF

    response = HttpResponse(pdf, content_type='application/pdf')

    filename = f"STAI_{test.patient.nom}_{test.patient.prenom}_{test.date_passation.strftime('%Y%m%d')}.pdf"

    response['Content-Disposition'] = f'attachment; filename="{filename}"'

 

    return response