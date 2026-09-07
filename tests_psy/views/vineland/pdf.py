"""Génération du rapport PDF Vineland (page de couverture, synthèse, comparaisons)."""
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

from tests_psy.models import Domain, SousDomain

from .scoring import get_age_tranches, find_echelle_v_mapping, get_domain_mapping
from .comparisons import (
    generate_domain_comparisons, generate_sous_domaine_comparisons, generate_interdomaine_comparisons,
)


def create_pdf_styles():
    """Crée et retourne les styles nécessaires pour le PDF."""
    styles = getSampleStyleSheet()

    # Style pour les questions
    question_style = ParagraphStyle(
        name='QuestionStyle',
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        wordWrap='CJK',
        alignment=0
    )

    # Style pour les cellules compactes
    compact_cell_style = ParagraphStyle(
        name='CompactCell',
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        wordWrap='CJK',
        alignment=0
    )

    return {
        'title': styles["Heading1"],
        'subtitle': styles["Heading2"],
        'heading3': styles["Heading3"],
        'normal': styles["Normal"],
        'question': question_style,
        'compact': compact_cell_style
    }


def create_cover_page(elements, patient, test, age_info, styles, niveau_confiance=90, niveau_significativite='.05'):
    """Crée la page de couverture du rapport."""
    elements.append(Paragraph("Rapport d'évaluation Vineland-II", styles['title']))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(f"Patient: {patient.nom_complet}", styles['subtitle']))
    elements.append(Paragraph(f"Date de naissance: {patient.date_naissance.strftime('%d/%m/%Y')}", styles['normal']))
    elements.append(Paragraph(
        f"Âge au moment du test: {age_info['years']} ans, {age_info['months']} mois, {age_info['days']} jours",
        styles['normal']
    ))
    elements.append(Paragraph(f"Date d'évaluation: {test.date_passation.strftime('%d/%m/%Y')}", styles['normal']))
    evaluateur = "Non assigné"
    if test.psychologue:
        evaluateur = test.psychologue.get_full_name() or test.psychologue.username
    elements.append(Paragraph(f"Évaluateur: {evaluateur}", styles['normal']))

    # Paramètres d'analyse
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph("Paramètres d'analyse", styles['subtitle']))
    elements.append(Paragraph(f"Niveau de confiance: {niveau_confiance}%", styles['normal']))
    elements.append(Paragraph(f"Niveau de significativité: {niveau_significativite}", styles['normal']))

    elements.append(PageBreak())


def create_scores_summary(elements, test, complete_scores, styles):
    """Crée la section de synthèse des résultats."""
    elements.append(Paragraph("Synthèse des Résultats", styles['title']))
    elements.append(Spacer(1, 0.5*cm))

    for domain in complete_scores:
        elements.append(Paragraph(f"Domaine: {domain['name']}", styles['subtitle']))

        # Tableau du score de domaine
        if domain['domain_score']:
            create_domain_score_table(elements, domain, styles)
            elements.append(Spacer(1, 0.5*cm))

        # Tableau des sous-domaines
        create_subdomain_score_table(elements, domain, styles)
        elements.append(Spacer(1, 1*cm))

    elements.append(PageBreak())


def create_domain_score_table(elements, domain, styles):
    """Crée le tableau des scores de domaine."""
    domain_score_data = [
        ["Somme notes-V", "Note standard", "Rang percentile", "Intervalle", "Niveau adaptatif"],
        [
            str(domain['domain_score']['somme_notes_v']),
            str(domain['domain_score']['note_standard'] or "-"),
            str(domain['domain_score']['rang_percentile'] or "-"),
            f"±{domain['domain_score'].get('intervalle', '-')}" if domain['domain_score'].get('intervalle') else "-",
            domain['domain_score'].get('niveau_adaptatif', 'Non disponible')
        ]
    ]

    table = Table(domain_score_data, colWidths=[3*cm, 3*cm, 3*cm, 2.5*cm, 3.5*cm])
    table.setStyle(get_score_table_style())
    elements.append(table)


def create_subdomain_score_table(elements, domain, styles):
    """Crée le tableau des scores de sous-domaines."""
    data = [["Sous-domaine", "Note brute", "Note échelle-V", "Intervalle", "Niveau adaptatif", "Âge équivalent"]]

    for sous_domain in domain['sous_domaines']:
        data.append([
            sous_domain['name'],
            str(sous_domain['note_brute']),
            str(sous_domain['note_echelle_v']),
            f"±{sous_domain.get('intervalle', '-')}" if sous_domain.get('intervalle') else "-",
            sous_domain.get('niveau_adaptatif', 'Non disponible'),
            sous_domain.get('age_equivalent', '-')
        ])

    table = Table(data, colWidths=[4*cm, 2*cm, 2*cm, 2*cm, 3*cm, 2.5*cm])
    table.setStyle(get_score_table_style())
    elements.append(table)


def get_score_table_style():
    """Retourne le style pour les tableaux de scores."""
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])


def create_comparisons_section(elements, test, scores, age_info, styles, niveau_significativite='.05'):
    """Crée la section des comparaisons par paires."""
    elements.append(Paragraph("Comparaisons par paires", styles['title']))
    elements.append(Spacer(1, 0.5*cm))

    # Ajouter une note sur le niveau de significativité utilisé
    elements.append(Paragraph(f"Niveau de significativité utilisé: {niveau_significativite}", styles['normal']))
    elements.append(Spacer(1, 0.3*cm))

    tranche_age, _ = get_age_tranches(age_info['years'])
    tranche_age_simple = get_simple_age_range(age_info['years'])

    # Collecter les scores
    domaine_scores = {}
    sous_domaine_scores = {}

    for domain_name, domain_data in scores.items():
        if domain_name != "Comportements problématiques":
            domain_note_v_sum = 0

            for sous_domain, score in domain_data.items():
                sous_domain_obj = SousDomain.objects.get(name=sous_domain)
                echelle_v = find_echelle_v_mapping(sous_domain_obj, score['note_brute'], age_info)

                if echelle_v:
                    sous_domaine_scores[sous_domain] = {
                        'note_echelle_v': echelle_v.note_echelle_v,
                        'domaine': domain_name,
                        'sous_domaine_obj': sous_domain_obj
                    }
                    domain_note_v_sum += echelle_v.note_echelle_v

            # Obtenir la note standard du domaine
            domain_mapping = get_domain_mapping(domain_name, domain_note_v_sum, tranche_age)
            if domain_mapping:
                domaine_scores[domain_name] = {
                    'note_standard': domain_mapping.note_standard,
                    'domaine_obj': Domain.objects.get(name=domain_name),
                    'somme_notes_v': domain_note_v_sum
                }

    # Générer et afficher les comparaisons de domaines
    domain_comparisons = generate_domain_comparisons(
        domaine_scores, tranche_age_simple, tranche_age, niveau_significativite
    )
    if domain_comparisons:
        create_domain_comparison_table(elements, domain_comparisons, styles)
        elements.append(Spacer(1, 1*cm))

    # Générer et afficher les comparaisons de sous-domaines
    sous_domaine_comparisons = generate_sous_domaine_comparisons(
        sous_domaine_scores, tranche_age, niveau_significativite
    )
    for domaine, comparisons in sous_domaine_comparisons.items():
        if comparisons:
            create_subdomain_comparison_table(elements, domaine, comparisons, styles)
            elements.append(Spacer(1, 1*cm))

    # Générer et afficher les comparaisons inter-domaines
    interdomaine_comparisons = generate_interdomaine_comparisons(
        sous_domaine_scores, tranche_age, niveau_significativite
    )
    if interdomaine_comparisons:
        create_interdomain_comparison_table(elements, interdomaine_comparisons, styles)


def get_simple_age_range(age_years):
    """Détermine la tranche d'âge simple pour les comparaisons."""
    if age_years < 3:
        return '1' if age_years < 2 else '2'
    elif age_years < 7:
        return str(age_years)
    elif age_years < 9:
        return '7-8'
    elif age_years < 12:
        return '9-11'
    elif age_years < 15:
        return '12-14'
    elif age_years < 19:
        return '15-18'
    elif age_years < 30:
        return '19-29'
    elif age_years < 50:
        return '30-49'
    else:
        return '50-90'


def create_domain_comparison_table(elements, comparisons, styles):
    """Crée le tableau des comparaisons de domaines."""
    elements.append(Paragraph("Comparaisons des domaines", styles['subtitle']))
    elements.append(Spacer(1, 0.3*cm))

    data = [["Domaine 1", "Note", "<,>,=", "Note", "Domaine 2", "Diff.", "Signif.", "Fréq."]]

    for comp in comparisons:
        data.append([
            comp['domaine1'],
            str(comp['note1']),
            comp['signe'],
            str(comp['note2']),
            comp['domaine2'],
            str(comp['difference']),
            "✓" if comp['est_significatif'] else "-",
            comp['frequence'] if comp['frequence'] else "-"
        ])

    table = Table(data, colWidths=[3*cm, 1.5*cm, 1*cm, 1.5*cm, 3*cm, 1.5*cm, 1.5*cm, 1.5*cm])
    table.setStyle(get_comparison_table_style())
    elements.append(table)


def create_subdomain_comparison_table(elements, domaine, comparisons, styles):
    """Crée le tableau des comparaisons de sous-domaines."""
    elements.append(Paragraph(f"Comparaisons - {domaine}", styles['subtitle']))
    elements.append(Spacer(1, 0.3*cm))

    data = [["Sous-domaine 1", "Note", "<,>,=", "Note", "Sous-domaine 2", "Diff.", "Signif.", "Fréq."]]

    for comp in comparisons:
        data.append([
            comp['sous_domaine1'],
            str(comp['note1']),
            comp['signe'],
            str(comp['note2']),
            comp['sous_domaine2'],
            str(comp['difference']),
            "✓" if comp['est_significatif'] else "-",
            comp['frequence'] if comp['frequence'] else "-"
        ])

    table = Table(data, colWidths=[3*cm, 1.5*cm, 1*cm, 1.5*cm, 3*cm, 1.5*cm, 1.5*cm, 1.5*cm])
    table.setStyle(get_comparison_table_style())
    elements.append(table)


def create_interdomain_comparison_table(elements, comparisons, styles):
    """Crée le tableau des comparaisons inter-domaines."""
    elements.append(Paragraph("Comparaisons inter-domaines", styles['subtitle']))
    elements.append(Spacer(1, 0.3*cm))

    data = [[
        Paragraph("<b>SD 1</b>", styles['compact']),
        Paragraph("<b>Dom.</b>", styles['compact']),
        Paragraph("<b>Note</b>", styles['compact']),
        Paragraph("<b><,>,=</b>", styles['compact']),
        Paragraph("<b>Note</b>", styles['compact']),
        Paragraph("<b>SD 2</b>", styles['compact']),
        Paragraph("<b>Dom.</b>", styles['compact']),
        Paragraph("<b>Diff.</b>", styles['compact']),
        Paragraph("<b>Sign.</b>", styles['compact']),
        Paragraph("<b>Fréq.</b>", styles['compact'])
    ]]

    for comp in comparisons:
        data.append([
            Paragraph(comp['sous_domaine1'], styles['compact']),
            Paragraph(comp['domaine1'], styles['compact']),
            Paragraph(str(comp['note1']), styles['compact']),
            Paragraph(comp['signe'], styles['compact']),
            Paragraph(str(comp['note2']), styles['compact']),
            Paragraph(comp['sous_domaine2'], styles['compact']),
            Paragraph(comp['domaine2'], styles['compact']),
            Paragraph(str(comp['difference']), styles['compact']),
            Paragraph("✓" if comp['est_significatif'] else "-", styles['compact']),
            Paragraph(comp['frequence'] if comp['frequence'] else "-", styles['compact'])
        ])

    table = Table(data, colWidths=[2.2*cm, 2.2*cm, 1*cm, 0.8*cm, 1*cm, 2.2*cm, 2.2*cm, 1.2*cm, 1.2*cm, 1.2*cm])
    table.setStyle(get_comparison_table_style())
    elements.append(table)


def get_comparison_table_style():
    """Retourne le style pour les tableaux de comparaisons."""
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (3, -1), 'CENTER'),
        ('ALIGN', (5, 1), (7, -1), 'CENTER'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (2, 1), (2, -1), colors.lightgrey),
    ])
