"""Relecture de cohérence d'un bilan, sans IA : repère dans le texte rédigé (hors tableaux)
les scores cités qui ne correspondent pas aux scores saisis, les niveaux annoncés qui
contredisent le score (« dépression modérée » pour un BDI de 12, « seuil clinique » pour un T
de 41), une mauvaise édition de test et les textes d'attente oubliés.

Les contrôles sont volontairement prudents : une alerte est un point à relire, pas une erreur
certaine (le psychologue peut citer un score d'un bilan antérieur, par exemple)."""
import re

from . import html_blocs as hb
from . import tests_externes as te
from .modeles import PLACEHOLDER_IA, PLACEHOLDER_LIBRE

RE_PHRASE = re.compile(r'(?<=[.!?…])\s+(?=[A-ZÀ-ÖØ-Þ«(])')
RE_NOMBRE = r'(\d+(?:[.,]\d+)?)'
RE_NEGATION = re.compile(r"\b(pas|sans|aucun|aucune|non|ni|n'|ne)\b", re.IGNORECASE)
RE_CLINIQUE = re.compile(r'seuil clinique|cliniquement significati|zone clinique|pathologique', re.IGNORECASE)
RE_NORME = re.compile(r'dans la norme|dans la moyenne|non significati', re.IGNORECASE)

NIVEAUX = {
    'minimal': re.compile(r'\bminimal', re.IGNORECASE),
    'leger': re.compile(r'\bl[ée]g[eè]re?s?\b', re.IGNORECASE),
    'modere': re.compile(r'\bmod[ée]r[ée]e?s?\b', re.IGNORECASE),
    'severe': re.compile(r'\bs[ée]v[eè]re', re.IGNORECASE),
}
NIVEAU_NORMALISE = {'Minimale': 'minimal', 'Légère': 'leger', 'Modérée': 'modere', 'Sévère': 'severe',
                    'Minimal': 'minimal', 'Léger': 'leger', 'Modéré': 'modere', 'Légère ': 'leger'}

EDITIONS = {
    'wais4': (re.compile(r'\bWAIS[- ]?(V|5)\b'), "Le texte cite la WAIS-V alors que les scores saisis sont ceux de la WAIS-IV."),
    'wisc5': (re.compile(r'\bWISC[- ]?(IV|4)\b'), "Le texte cite le WISC-IV alors que les scores saisis sont ceux du WISC-V."),
}


def _phrases(contenu):
    """-> [(titre de section, clé de section, phrase)] du texte rédigé, hors tableaux."""
    resultat = []
    titre, cle = '', ''
    calcule = False  # sections « Données » et partie calculée des chapitres de test : texte généré, ignoré
    for bloc in hb.lire(contenu):
        if bloc['type'] == 'h2':
            titre, cle = hb.texte_runs(bloc['runs']), bloc.get('section') or cle
            if bloc.get('section'):
                calcule = bloc.get('section_type') in ('auto', 'test')
            continue
        if bloc['type'] == 'h3' and hb.texte_runs(bloc['runs']).strip().rstrip(' :').lower() == 'interprétation':
            calcule = False
            continue
        if calcule:
            continue
        if bloc['type'] in ('p', 'h3'):
            textes = [hb.texte_runs(bloc['runs'])]
        elif bloc['type'] in ('ul', 'ol'):
            textes = [hb.texte_runs(item) for item in bloc['items']]
        else:
            continue
        for texte in textes:
            for phrase in RE_PHRASE.split(texte.replace('\n', ' ')):
                if phrase.strip():
                    resultat.append((titre, cle, phrase.strip()))
    return resultat


def _court(phrase, limite=220):
    return phrase if len(phrase) <= limite else phrase[:limite].rstrip() + '...'


def _motif_valeur(nom):
    nom_re = re.escape(nom).replace(r'\ ', r'\s+')
    if re.fullmatch(r'[A-Z][A-Z0-9-]{1,6}', nom):  # sigle : ICV = 129 ; IVT (86) ; TMT-A = 56 s
        return re.compile(rf'(?<![\w-]){nom_re}\s*(?:=|:|\()\s*{RE_NOMBRE}(?:\s*[,;]\s*P\s*{RE_NOMBRE})?')
    # nom : Similitudes (NS = 17) ; Flexibilité (T = 86 ; P99) ; Mémoire des chiffres (14)
    return re.compile(rf'(?<!\w){nom_re}\s*\(\s*(?:NS|note standard|note T|score T|T)?\s*[=:]?\s*{RE_NOMBRE}'
                      rf'(?:\s*[,;]\s*P\s*{RE_NOMBRE})?', re.IGNORECASE)


def verifier(contenu, reference):
    """reference : donnees.valeurs_de_reference(...) -> [{'section', 'passage', 'message'}]."""
    alertes = []
    phrases = _phrases(contenu)

    def alerte(titre, phrase, message):
        entree = {'section': titre, 'passage': _court(phrase), 'message': message}
        if entree not in alertes:
            alertes.append(entree)

    # 1. Textes d'attente restés dans le document
    for titre, _, phrase in phrases:
        if PLACEHOLDER_IA[:30] in phrase or PLACEHOLDER_LIBRE[:20] in phrase or '[à compléter' in phrase.lower():
            alerte(titre, phrase, "Texte d'attente à remplacer.")

    # 2. Scores cités différents des scores saisis
    for valeur in reference.get('valeurs', []):
        for nom in valeur['noms']:
            motif = _motif_valeur(nom)
            for titre, _, phrase in phrases:
                for m in motif.finditer(phrase):
                    cite = te.nombre(m.group(1))
                    if cite is not None and cite != valeur['valeur']:
                        alerte(titre, phrase, f"{nom} ({valeur['test']}) vaut {te.fmt(valeur['valeur'])} dans les "
                                              f"scores, mais {te.fmt(cite)} dans le texte.")
                    pct = te.nombre(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else None
                    if pct is not None and valeur.get('percentile') is not None and pct != valeur['percentile']:
                        alerte(titre, phrase, f"Percentile de {nom} : {te.fmt(valeur['percentile'])} dans les "
                                              f"scores, {te.fmt(pct)} dans le texte.")

    # 3. Niveau clinique contredit par le score (échelles en score T : BRIEF, RCADS...)
    for valeur in reference.get('valeurs', []):
        if valeur.get('type') != 'T':
            continue
        nom = valeur['noms'][0]
        motif_nom = re.compile(rf'(?<!\w){re.escape(nom)}(?!\w)', re.IGNORECASE)
        autres = [v['noms'][0] for v in reference['valeurs'] if v.get('type') == 'T' and v['noms'][0] != nom]
        for titre, _, phrase in phrases:
            if not motif_nom.search(phrase) or any(re.search(rf'(?<!\w){re.escape(a)}(?!\w)', phrase, re.IGNORECASE)
                                                  for a in autres):
                continue
            if valeur['valeur'] < 65 and RE_CLINIQUE.search(phrase) and not RE_NEGATION.search(phrase):
                alerte(titre, phrase, f"{nom} : score T de {te.fmt(valeur['valeur'])}, inférieur au seuil clinique "
                                      "(65), alors que le texte parle de seuil clinique.")
            if valeur['valeur'] >= 65 and RE_NORME.search(phrase):
                alerte(titre, phrase, f"{nom} : score T de {te.fmt(valeur['valeur'])}, cliniquement significatif, "
                                      "alors que le texte le situe dans la norme.")

    # RCADS : « seuil clinique » dans le chapitre alors qu'aucune échelle ne l'atteint
    t_rcads = [v['valeur'] for v in reference.get('valeurs', []) if v.get('test') == 'RCADS']
    if t_rcads and max(t_rcads) < 70:
        for titre, cle, phrase in phrases:
            if (cle == 'ext_rcads' or 'RCADS' in phrase) and RE_CLINIQUE.search(phrase) and not RE_NEGATION.search(phrase):
                alerte(titre, phrase, f"RCADS : aucun score T n'atteint le seuil clinique (70) - le plus élevé "
                                      f"est {te.fmt(max(t_rcads))}.")

    # 4. Niveaux des inventaires (BAI, BDI) : le texte annonce un autre niveau
    for entree in reference.get('niveaux', []):
        attendu = NIVEAU_NORMALISE.get(entree.get('niveau', '').strip())
        if not attendu or 'echelle' in entree:
            continue
        motifs = [re.compile(rf'(?<!\w){re.escape(n)}(?!\w)', re.IGNORECASE) for n in entree['noms']]
        for titre, _, phrase in phrases:
            if not any(m.search(phrase) for m in motifs):
                continue
            annonces = {niveau for niveau, motif in NIVEAUX.items() if motif.search(phrase)}
            # Une phrase qui cite deux inventaires (« anxiété légère et dépression modérée ») reste ambiguë
            autres_inventaires = sum(1 for e in reference['niveaux'] if 'echelle' not in e
                                     and any(re.search(rf'(?<!\w){re.escape(n)}(?!\w)', phrase, re.IGNORECASE)
                                             for n in e['noms']))
            if annonces and attendu not in annonces and autres_inventaires == 1:
                alerte(titre, phrase, f"{entree['test']} : le score correspond à un niveau « {entree['niveau'].lower()} », "
                                      "le texte annonce un autre niveau.")

    # 5. Édition du test
    texte_complet = ' '.join(p for _, _, p in phrases)
    for cle in reference.get('tests', []):
        if cle in EDITIONS:
            motif, message = EDITIONS[cle]
            m = motif.search(texte_complet)
            if m:
                phrase = next((p for _, _, p in phrases if motif.search(p)), m.group(0))
                titre = next((t for t, _, p in phrases if motif.search(p)), '')
                alerte(titre, phrase, message)
    return alertes
