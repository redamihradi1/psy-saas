"""Rapport PDF BRIEF (reportlab) : identité, tableau résumé des cotations, validité,
alertes et profil des scores T (même lecture que la Feuille de profil du manuel)."""
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from reportlab.graphics.shapes import Drawing, Line, PolyLine, Circle, String, Rect
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from accounts.decorators import require_test_access
from .scoring import calculer_resultats
from .views import _get_test

VIOLET = colors.HexColor('#c026d3')
GRIS_CLAIR = colors.HexColor('#F3F4F6')
ROUGE_CLAIR = colors.HexColor('#FEE2E2')


def _fmt(valeur):
    return '-' if valeur is None else str(valeur)


def _profil_drawing(resultats, largeur=17 * cm, hauteur=7 * cm):
    """Profil des scores T : axe 30-100, zone >= 65 grisée, ligne de moyenne à 50."""
    lignes = resultats['lignes']
    marge_g, marge_b, marge_h = 1.2 * cm, 1.2 * cm, 0.4 * cm
    zone_l, zone_h = largeur - marge_g - 0.3 * cm, hauteur - marge_b - marge_h
    t_min, t_max = 30, 100

    def y(t):
        t = max(t_min, min(t_max, t))
        return marge_b + (t - t_min) / (t_max - t_min) * zone_h

    pas = zone_l / len(lignes)
    d = Drawing(largeur, hauteur)
    d.add(Rect(marge_g, y(65), zone_l, y(t_max) - y(65), fillColor=colors.HexColor('#E5E7EB'), strokeColor=None))
    for t in range(t_min, t_max + 1, 10):
        d.add(Line(marge_g, y(t), marge_g + zone_l, y(t), strokeColor=colors.HexColor('#D1D5DB'), strokeWidth=0.3))
        d.add(String(marge_g - 0.2 * cm, y(t) - 3, str(t), fontSize=7, textAnchor='end'))
    d.add(Line(marge_g, y(50), marge_g + zone_l, y(50), strokeColor=colors.grey, strokeWidth=0.8))
    d.add(Line(marge_g, y(65), marge_g + zone_l, y(65), strokeColor=colors.HexColor('#DC2626'), strokeWidth=0.8, strokeDashArray=[3, 2]))

    # Les échelles et les indices sont deux profils distincts (comme sur la feuille de profil).
    segments, courant = [], []
    for i, ligne in enumerate(lignes):
        x = marge_g + pas * (i + 0.5)
        d.add(String(x, marge_b - 0.45 * cm, ligne['libelle_court'][:12], fontSize=5.5, textAnchor='middle'))
        if ligne['score_t'] is not None:
            courant.append((x, y(ligne['score_t'])))
            d.add(Circle(x, y(ligne['score_t']), 2, fillColor=VIOLET, strokeColor=VIOLET))
        if ligne['code'] == 'controle' or ligne['score_t'] is None:
            segments.append(courant)
            courant = []
    segments.append(courant)
    for segment in segments:
        if len(segment) > 1:
            d.add(PolyLine([coord for point in segment for coord in point], strokeColor=VIOLET, strokeWidth=1.2))
    return d


@login_required
@require_test_access('brief')
def brief_pdf(request, test_id):
    test = _get_test(request, test_id)
    resultats = calculer_resultats(test)
    patient = test.patient

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    titre = ParagraphStyle('Titre', parent=styles['Heading1'], fontSize=16, textColor=VIOLET, alignment=TA_CENTER, spaceAfter=4)
    sous_titre = ParagraphStyle('SousTitre', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=TA_CENTER, spaceAfter=12)
    section = ParagraphStyle('Section', parent=styles['Heading2'], fontSize=12, textColor=VIOLET, spaceBefore=12, spaceAfter=6)
    normal = styles['Normal']
    petit = ParagraphStyle('Petit', parent=normal, fontSize=8, textColor=colors.HexColor('#374151'))

    elements = [
        Paragraph("BRIEF - Inventaire d'évaluation comportementale des fonctions exécutives", titre),
        Paragraph(f"Forme Parent - passation du {test.date_passation.strftime('%d/%m/%Y')}", sous_titre),
    ]

    evaluateur = (test.psychologue.get_full_name() or test.psychologue.username) if test.psychologue else "Non assigné"
    identite = [
        ['Enfant', patient.nom_complet, 'Sexe', test.get_sexe_display()],
        ['Date de naissance', patient.date_naissance.strftime('%d/%m/%Y'), 'Âge au test', f"{resultats['age']} ans"],
        ['Répondant', test.repondant or '-', 'Psychologue', evaluateur],
    ]
    table = Table(identite, colWidths=[3.2 * cm, 5.3 * cm, 2.8 * cm, 5.7 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), GRIS_CLAIR), ('BACKGROUND', (2, 0), (2, -1), GRIS_CLAIR),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'), ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9), ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(table)

    avertissements = []
    if not resultats['protocole_cotable']:
        avertissements.append(f"Protocole non cotable : {resultats['manquants_total']} items manquants (maximum 14). Scores T non calculés.")
    if resultats['hors_etalonnage']:
        avertissements.append("Âge hors de l'étalonnage BRIEF (5 à 18 ans) : scores T non calculés.")
    elif resultats['protocole_cotable'] and not resultats['normes_disponibles']:
        avertissements.append("Tables d'étalonnage non chargées pour ce sexe/âge : scores T non calculés.")
    if resultats['alerte_ecart_irc_im']:
        avertissements.append(
            f"Écart IRC-IM de {resultats['ecart_irc_im']} points T (seuil {resultats['seuil_ecart_irc_im']}) : "
            "le CEG peut masquer des différences importantes et ne doit pas être utilisé comme mesure résumée."
        )

    elements.append(Paragraph("Tableau résumé des cotations", section))
    donnees = [['Échelle / Indice', 'Score brut', 'Score T', 'Percentile', 'IC 90 %']]
    lignes_indices = []
    for i, ligne in enumerate(resultats['lignes'], start=1):
        ic = f"{ligne['ic_bas']} - {ligne['ic_haut']}" if ligne['ic_bas'] is not None else '-'
        donnees.append([ligne['libelle'], _fmt(ligne['note_brute']), _fmt(ligne['score_t']), _fmt(ligne['percentile']), ic])
        if ligne['est_indice']:
            lignes_indices.append(i)
    table = Table(donnees, colWidths=[7.5 * cm, 2.3 * cm, 2.2 * cm, 2.3 * cm, 2.7 * cm])
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), VIOLET), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'), ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
    ]
    for i in lignes_indices:
        style += [('BACKGROUND', (0, i), (-1, i), GRIS_CLAIR), ('FONTNAME', (0, i), (0, i), 'Helvetica-Bold')]
    for i, ligne in enumerate(resultats['lignes'], start=1):
        if ligne['significatif']:
            style += [('BACKGROUND', (2, i), (2, i), ROUGE_CLAIR), ('FONTNAME', (2, i), (2, i), 'Helvetica-Bold')]
    table.setStyle(TableStyle(style))
    elements.append(table)
    elements.append(Spacer(1, 0.15 * cm))
    elements.append(Paragraph(
        f"Score T moyen = 50, écart-type = 10. Un score T >= {resultats['seuil_t_clinique']} (surligné) a une signification clinique potentielle.",
        petit,
    ))

    if resultats['normes_disponibles']:
        elements.append(Paragraph("Profil des scores T", section))
        elements.append(_profil_drawing(resultats))

    elements.append(Paragraph("Échelles de validité", section))
    neg, inc = resultats['negativite'], resultats['incoherence']
    validite = [
        ['Échelle', 'Score', 'Classification'],
        ['Négativité (0 à 9)', _fmt(neg['score']), neg['classification'] or '-'],
        ['Incohérence (0 à 20)', _fmt(inc['score']), inc['classification'] or 'Seuils à renseigner'],
    ]
    table = Table(validite, colWidths=[7.5 * cm, 3 * cm, 6.5 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_CLAIR), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9), ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
    ]))
    elements.append(table)

    if avertissements:
        elements.append(Paragraph("Points d'attention", section))
        for texte in avertissements:
            elements.append(Paragraph(f"• {texte}", normal))

    if test.notes:
        elements.append(Paragraph("Notes du psychologue", section))
        elements.append(Paragraph(test.notes.replace('\n', '<br/>'), normal))

    doc.build(elements)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    buffer.close()
    filename = f"BRIEF_{patient.nom}_{patient.prenom}_{test.date_passation.strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
