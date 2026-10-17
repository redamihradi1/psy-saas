"""Export d'un bilan en Word (.docx, python-docx) et en PDF (reportlab), à partir des mêmes
blocs que l'éditeur (html_blocs). En-tête : cabinet et coordonnées."""
import io
from xml.sax.saxutils import escape

from django.utils.text import slugify

from . import html_blocs as hb

COULEUR_TITRE = (0x6B, 0x21, 0xA8)  # violet foncé, proche de la charte de l'app


def nom_fichier(bilan, extension):
    base = slugify(f"bilan-{bilan.patient.nom}-{bilan.patient.prenom}-{bilan.date_modification:%Y%m%d}")
    return f"{base or 'bilan'}.{extension}"


def _lignes_entete(bilan):
    org = bilan.organization
    lignes = [org.name]
    coordonnees = ' - '.join(x for x in [org.address.replace('\n', ', ') if org.address else '', org.city, org.phone] if x)
    if coordonnees:
        lignes.append(coordonnees)
    return lignes


# --- Word ------------------------------------------------------------------------------------

def exporter_docx(bilan):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor, Cm

    document = Document()
    section = document.sections[0]
    section.left_margin = section.right_margin = Cm(2.2)
    style = document.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(11)

    entete = section.header.paragraphs[0]
    for n, ligne in enumerate(_lignes_entete(bilan)):
        if n:
            entete.add_run().add_break()
        r = entete.add_run(ligne)
        r.font.size = Pt(9 if n else 10)
        r.bold = n == 0
        r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    def ajouter_runs(paragraphe, runs):
        for run in runs:
            if 'br' in run:
                paragraphe.add_run().add_break()
                continue
            r = paragraphe.add_run(run['t'])
            r.bold, r.italic, r.underline = run.get('b'), run.get('i'), run.get('u')

    for bloc in hb.lire(bilan.contenu):
        t = bloc['type']
        if t in ('h1', 'h2', 'h3'):
            niveau = int(t[1])
            p = document.add_heading(level=0 if niveau == 1 else niveau - 1)
            ajouter_runs(p, bloc['runs'])
            for r in p.runs:
                r.font.color.rgb = RGBColor(*COULEUR_TITRE)
            if niveau == 1:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif t == 'p':
            ajouter_runs(document.add_paragraph(), bloc['runs'])
        elif t in ('ul', 'ol'):
            for item in bloc['items']:
                ajouter_runs(document.add_paragraph(style='List Bullet' if t == 'ul' else 'List Number'), item)
        elif t == 'table':
            nb_colonnes = max(len(row['cells']) for row in bloc['rows'])
            table = document.add_table(rows=0, cols=nb_colonnes)
            table.style = 'Table Grid'
            for row in bloc['rows']:
                cellules = table.add_row().cells
                for n, cellule_runs in enumerate(row['cells']):
                    p = cellules[n].paragraphs[0]
                    ajouter_runs(p, cellule_runs)
                    for r in p.runs:
                        r.font.size = Pt(9.5)
                        if row.get('header'):
                            r.bold = True
            document.add_paragraph()

    tampon = io.BytesIO()
    document.save(tampon)
    return tampon.getvalue()


# --- PDF -------------------------------------------------------------------------------------

# Polices standard PDF (Helvetica) = encodage WinAnsi : on remplace les quelques caractères
# hors de cet encodage que l'IA ou le psy peuvent taper.
REMPLACEMENTS_PDF = {'≥': '>=', '≤': '<=', '→': '->', '←': '<-', '≠': '!=', '−': '-', ' ': ' ', ' ': ' '}


def _texte_pdf(texte):
    for a, b in REMPLACEMENTS_PDF.items():
        texte = texte.replace(a, b)
    return texte.encode('cp1252', 'replace').decode('cp1252')


def _markup(runs):
    morceaux = []
    for run in runs:
        if 'br' in run:
            morceaux.append('<br/>')
            continue
        texte = escape(_texte_pdf(run['t']))
        if run.get('u'):
            texte = f'<u>{texte}</u>'
        if run.get('i'):
            texte = f'<i>{texte}</i>'
        if run.get('b'):
            texte = f'<b>{texte}</b>'
        morceaux.append(texte)
    return ''.join(morceaux)


def exporter_pdf(bilan):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    violet = colors.Color(*(c / 255 for c in COULEUR_TITRE))
    base = getSampleStyleSheet()
    styles = {
        'h1': ParagraphStyle('h1', parent=base['Title'], fontSize=17, textColor=violet, spaceAfter=10, alignment=TA_CENTER),
        'h2': ParagraphStyle('h2', parent=base['Heading2'], fontSize=13, textColor=violet, spaceBefore=12, spaceAfter=6),
        'h3': ParagraphStyle('h3', parent=base['Heading3'], fontSize=11, spaceBefore=8, spaceAfter=4),
        'p': ParagraphStyle('p', parent=base['BodyText'], fontSize=10.5, leading=14.5, spaceAfter=6),
        'cellule': ParagraphStyle('cellule', parent=base['BodyText'], fontSize=8.5, leading=10.5),
    }

    lignes_entete = [_texte_pdf(l) for l in _lignes_entete(bilan)]

    def entete_pied(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 9)
        canvas.setFillColor(colors.grey)
        y = A4[1] - 1.2 * cm
        for n, ligne in enumerate(lignes_entete):
            canvas.setFont('Helvetica-Bold' if n == 0 else 'Helvetica', 9 if n == 0 else 8)
            canvas.drawString(2 * cm, y, ligne)
            y -= 0.4 * cm
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
        canvas.drawString(2 * cm, 1.2 * cm, _texte_pdf("Document confidentiel - " + bilan.patient.nom_complet))
        canvas.restoreState()

    largeur = A4[0] - 4 * cm
    elements = []
    for bloc in hb.lire(bilan.contenu):
        t = bloc['type']
        if t in styles:
            elements.append(Paragraph(_markup(bloc['runs']) or '&nbsp;', styles[t]))
        elif t in ('ul', 'ol'):
            items = [ListItem(Paragraph(_markup(item), styles['p']), leftIndent=12) for item in bloc['items']]
            elements.append(ListFlowable(items, bulletType='bullet' if t == 'ul' else '1', start='•' if t == 'ul' else None,
                                         leftIndent=14, bulletFontSize=8))
        elif t == 'table':
            nb_colonnes = max(len(row['cells']) for row in bloc['rows'])
            donnees, entetes = [], []
            for n, row in enumerate(bloc['rows']):
                cellules = [Paragraph(_markup(c), styles['cellule']) for c in row['cells']]
                donnees.append(cellules + [''] * (nb_colonnes - len(cellules)))
                if row.get('header'):
                    entetes.append(n)
            table = Table(donnees, colWidths=[largeur / nb_colonnes] * nb_colonnes, repeatRows=1 if 0 in entetes else 0)
            style = [('GRID', (0, 0), (-1, -1), 0.4, colors.lightgrey), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                     ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
            style += [('BACKGROUND', (0, n), (-1, n), colors.Color(0.96, 0.93, 0.98)) for n in entetes]
            table.setStyle(TableStyle(style))
            elements.extend([table, Spacer(1, 0.3 * cm)])

    tampon = io.BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2.6 * cm, bottomMargin=2 * cm, title=_texte_pdf(bilan.titre))
    doc.build(elements or [Spacer(1, 1)], onFirstPage=entete_pied, onLaterPages=entete_pied)
    return tampon.getvalue()
