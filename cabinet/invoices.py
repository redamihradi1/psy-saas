"""Génération de la facture PDF d'une consultation."""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

DARK_GREEN = colors.HexColor('#1c2e22')
SAGE = colors.HexColor('#8aa696')
CREAM = colors.HexColor('#f4f1ea')
TEXT_DARK = colors.HexColor('#1f2a24')
TEXT_MUTED = colors.HexColor('#6b7a70')

STATUT_LABELS = {
    'paye': 'PAYÉ',
    'attente': 'EN ATTENTE',
    'annule': 'ANNULÉ',
}
STATUT_COLORS = {
    'paye': colors.HexColor('#2e7d4f'),
    'attente': colors.HexColor('#b8860b'),
    'annule': colors.HexColor('#b03030'),
}


def generate_invoice_pdf(consultation):
    """Retourne les octets du PDF de facture pour une consultation."""
    organization = consultation.organization
    patient = consultation.patient

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # --- En-tête ---
    header_height = 5 * cm
    c.setFillColor(DARK_GREEN)
    c.rect(0, height - header_height, width, header_height, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont('Times-Roman', 24)
    c.drawString(2 * cm, height - 2.1 * cm, organization.name or "Cabinet")

    c.setFont('Helvetica', 9)
    c.setFillColor(SAGE)
    c.drawString(2 * cm, height - 2.9 * cm, "PSYCHOLOGUE CLINICIENNE · PSYCHOTHÉRAPEUTE")

    contact_lines = [line for line in [organization.phone, organization.address] if line]
    y = height - 1.6 * cm
    c.setFont('Helvetica', 9)
    c.setFillColor(colors.white)
    for line in contact_lines:
        c.drawRightString(width - 2 * cm, y, line)
        y -= 0.45 * cm

    # --- Titre facture ---
    y = height - header_height - 1.5 * cm
    c.setFillColor(TEXT_DARK)
    c.setFont('Times-Roman', 20)
    c.drawString(2 * cm, y, f"Facture — Consultation N°{consultation.id}")

    y -= 0.8 * cm
    c.setFont('Helvetica', 10)
    c.setFillColor(TEXT_MUTED)
    c.drawString(2 * cm, y, f"Date de séance : {consultation.date_seance.strftime('%d/%m/%Y à %H:%M')}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Émise le : {consultation.date_seance.strftime('%d/%m/%Y')}")

    # --- Bloc patient ---
    y -= 1.2 * cm
    c.setStrokeColor(SAGE)
    c.setLineWidth(0.8)
    c.line(2 * cm, y, width - 2 * cm, y)

    y -= 0.8 * cm
    c.setFont('Helvetica-Bold', 11)
    c.setFillColor(TEXT_DARK)
    c.drawString(2 * cm, y, "Patient")
    y -= 0.55 * cm
    c.setFont('Helvetica', 10)
    c.drawString(2 * cm, y, patient.nom_complet)
    if patient.telephone:
        y -= 0.45 * cm
        c.drawString(2 * cm, y, patient.telephone)
    if patient.email:
        y -= 0.45 * cm
        c.drawString(2 * cm, y, patient.email)

    # --- Tableau prestation ---
    y -= 1.2 * cm
    table_top = y
    row_height = 1 * cm
    col_x = [2 * cm, 11 * cm, 14.5 * cm, width - 2 * cm]

    c.setFillColor(DARK_GREEN)
    c.rect(2 * cm, table_top - row_height, width - 4 * cm, row_height, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(col_x[0] + 0.2 * cm, table_top - row_height + 0.35 * cm, "PRESTATION")
    c.drawString(col_x[1] + 0.2 * cm, table_top - row_height + 0.35 * cm, "DURÉE")
    c.drawRightString(col_x[3] - 0.2 * cm, table_top - row_height + 0.35 * cm, "MONTANT")

    row_y = table_top - row_height
    c.setFillColor(CREAM)
    c.rect(2 * cm, row_y - row_height, width - 4 * cm, row_height, fill=1, stroke=0)
    c.setFillColor(TEXT_DARK)
    c.setFont('Helvetica', 10)
    c.drawString(col_x[0] + 0.2 * cm, row_y - row_height + 0.35 * cm, consultation.get_type_consultation_display())
    c.drawString(col_x[1] + 0.2 * cm, row_y - row_height + 0.35 * cm, f"{consultation.duree_minutes} min")
    c.setFont('Helvetica-Bold', 10)
    c.drawRightString(col_x[3] - 0.2 * cm, row_y - row_height + 0.35 * cm, f"{consultation.tarif} DHS")

    # --- Total ---
    total_y = row_y - row_height - 1 * cm
    c.setFont('Helvetica-Bold', 12)
    c.setFillColor(TEXT_DARK)
    c.drawString(col_x[1] + 0.2 * cm, total_y, "TOTAL")
    c.drawRightString(col_x[3] - 0.2 * cm, total_y, f"{consultation.tarif} DHS")

    # --- Badge statut ---
    badge_y = total_y - 1.2 * cm
    statut_color = STATUT_COLORS.get(consultation.statut_paiement, TEXT_MUTED)
    statut_label = STATUT_LABELS.get(consultation.statut_paiement, consultation.statut_paiement.upper())
    c.setFillColor(statut_color)
    c.roundRect(2 * cm, badge_y - 0.1 * cm, 3.2 * cm, 0.7 * cm, 0.15 * cm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(2 * cm + 1.6 * cm, badge_y + 0.15 * cm, statut_label)

    if consultation.date_paiement:
        c.setFillColor(TEXT_MUTED)
        c.setFont('Helvetica', 9)
        c.drawString(5.5 * cm, badge_y + 0.15 * cm, f"payé le {consultation.date_paiement.strftime('%d/%m/%Y')}")

    # --- Pied de page ---
    c.setFillColor(TEXT_MUTED)
    c.setFont('Helvetica', 8)
    footer_parts = [p for p in [organization.address, organization.phone] if p]
    c.drawCentredString(width / 2, 1.5 * cm, "  —  ".join(footer_parts))

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()
