"""Graphiques de profil (PNG) dessinés avec Pillow : courbe des notes composites ou des notes
standard, bande de la moyenne, intervalles de confiance. Utilisés par l'éditeur (image), et
par les exports Word et PDF."""
import io
import os

from PIL import Image, ImageDraw, ImageFont

ECHELLE = 2  # dessin en double résolution pour un rendu net à l'impression
LARGEUR, HAUTEUR = 900, 380
MARGE_G, MARGE_D, MARGE_H, MARGE_B = 60, 25, 45, 70

ENCRE = (31, 58, 95)
GRILLE = (226, 232, 240)
BANDE = (225, 236, 248)
TEXTE = (55, 65, 81)
MOYENNE = (148, 163, 184)


def _police(taille, gras=False):
    """Bitstream Vera, livrée avec reportlab (accents français garantis, partout)."""
    import reportlab
    chemin = os.path.join(os.path.dirname(reportlab.__file__), 'fonts', 'VeraBd.ttf' if gras else 'Vera.ttf')
    try:
        return ImageFont.truetype(chemin, taille * ECHELLE)
    except OSError:
        return ImageFont.load_default()


def profil_png(donnees):
    """donnees : tests_externes.donnees_figure(...) -> bytes PNG."""
    s = ECHELLE
    image = Image.new('RGB', (LARGEUR * s, HAUTEUR * s), 'white')
    d = ImageDraw.Draw(image)
    police, petite, titre = _police(11), _police(10), _police(13, gras=True)

    x0, x1 = MARGE_G * s, (LARGEUR - MARGE_D) * s
    y0, y1 = MARGE_H * s, (HAUTEUR - MARGE_B) * s
    vmin, vmax = donnees['min'], donnees['max']

    def y(v):
        return y1 - (v - vmin) / (vmax - vmin) * (y1 - y0)

    d.text(((LARGEUR * s) / 2, 14 * s), donnees['titre'], fill=ENCRE, font=titre, anchor='mt')

    bas, haut = donnees['bande']
    d.rectangle([x0, y(haut), x1, y(bas)], fill=BANDE)
    pas = donnees['pas'] if (vmax - vmin) / donnees['pas'] <= 20 else donnees['pas'] * 2
    v = vmin
    while v <= vmax:
        d.line([x0, y(v), x1, y(v)], fill=GRILLE, width=s)
        d.text((x0 - 8 * s, y(v)), str(v), fill=TEXTE, font=petite, anchor='rm')
        v += pas
    milieu = (bas + haut) / 2
    for xx in range(x0, x1, 12 * s):
        d.line([xx, y(milieu), xx + 6 * s, y(milieu)], fill=MOYENNE, width=s)
    d.rectangle([x0, y0, x1, y1], outline=(148, 163, 184), width=s)

    points = donnees['points']
    n = len(points)
    largeur_pas = (x1 - x0) / n
    coords = []
    for i, (libelle, valeur, ic_bas, ic_haut) in enumerate(points):
        cx = x0 + largeur_pas * (i + 0.5)
        valeur_bornee = max(vmin, min(vmax, valeur))
        coords.append((cx, y(valeur_bornee)))
        if ic_bas is not None and ic_haut is not None:
            d.line([cx, y(max(vmin, ic_bas)), cx, y(min(vmax, ic_haut))], fill=MOYENNE, width=3 * s)
        _libelle_axe(d, cx, y1 + 10 * s, libelle, police, n)
    d.line(coords, fill=ENCRE, width=3 * s)
    for (cx, cy), (_, valeur, _, _) in zip(coords, points):
        r = 5 * s
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ENCRE)
        texte = str(int(valeur)) if float(valeur).is_integer() else str(valeur).replace('.', ',')
        d.text((cx, cy - 10 * s), texte, fill=ENCRE, font=police, anchor='mb')

    tampon = io.BytesIO()
    image.save(tampon, format='PNG', optimize=True)
    return tampon.getvalue()


def _libelle_axe(d, cx, ytexte, libelle, police, nb_points):
    """Libellé sous l'axe, coupé sur deux lignes s'il est long et que la place manque."""
    if nb_points > 6 and len(libelle) > 10 and ' ' in libelle:
        mots = libelle.split(' ')
        coupe = max(1, len(mots) // 2)
        lignes = [' '.join(mots[:coupe]), ' '.join(mots[coupe:])]
    else:
        lignes = [libelle]
    for n, ligne in enumerate(lignes):
        d.text((cx, ytexte + n * 15 * ECHELLE), ligne, fill=TEXTE, font=police, anchor='mt')


def image_png(fichier):
    """Fichier image téléversé (signature, logo) -> bytes PNG, ou None s'il est illisible."""
    try:
        fichier.open('rb')
        with Image.open(fichier) as img:
            img = img.convert('RGBA')
            fond = Image.new('RGBA', img.size, (255, 255, 255, 255))
            fond.alpha_composite(img)
            tampon = io.BytesIO()
            fond.convert('RGB').save(tampon, format='PNG')
            return tampon.getvalue()
    except (OSError, ValueError):
        return None
    finally:
        try:
            fichier.close()
        except Exception:
            pass
