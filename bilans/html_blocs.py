"""Contenu d'un bilan : HTML de l'éditeur <-> liste de blocs simples.

L'éditeur (contenteditable) renvoie du HTML arbitraire. On ne le stocke jamais tel quel : il
est relu en blocs (titres, paragraphes, listes, tableaux, avec gras/italique/souligné), puis
réécrit. Tout ce qui n'est pas prévu (scripts, styles, liens, attributs) disparaît : c'est à la
fois le nettoyage anti-XSS et la structure qu'utilisent les exports Word/PDF et l'IA.

Bloc :
  {'type': 'h1'|'h2'|'h3'|'p', 'runs': [...], 'section': str|None, 'section_type': str|None}
  {'type': 'ul'|'ol', 'items': [[runs], ...]}
  {'type': 'table', 'rows': [{'header': bool, 'cells': [[runs], ...]}, ...]}
  {'type': 'figure', 'ref': 'wisc5.indices'}   (graphique calculé à partir des scores, ou signature)
Run : {'t': texte, 'b': bool, 'i': bool, 'u': bool} ou {'br': True}
"""
import re
from html import escape
from html.parser import HTMLParser

TITRES = {'h1', 'h2', 'h3'}
TITRES_RAMENES = {'h4': 'h3', 'h5': 'h3', 'h6': 'h3'}
BLOCS_PARAGRAPHE = {'p', 'div', 'blockquote', 'pre', 'section', 'article', 'header', 'footer'}
GRAS = {'b', 'strong'}
ITALIQUE = {'i', 'em'}
SOULIGNE = {'u', 'ins'}
IGNORES = {'script', 'style', 'head', 'title', 'template', 'noscript', 'iframe', 'object', 'svg'}
RE_CLE_SECTION = re.compile(r'^[a-z0-9_]{1,40}$')
TYPES_SECTION = {'auto', 'ia', 'libre', 'test'}
RE_REF_FIGURE = re.compile(r'^[a-z0-9_]{1,30}(\.[a-z0-9_]{1,30})?$')


class _Lecteur(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocs = []
        self.bloc = None          # bloc texte en cours (titre/paragraphe)
        self.liste = None         # bloc liste en cours
        self.item = None          # runs de l'élément de liste en cours
        self.table = None
        self.ligne = None
        self.cellule = None
        self.gras = self.italique = self.souligne = 0
        self.ignore = 0

    # --- destination des runs ---------------------------------------------------------
    def _runs_courants(self, creer=True):
        if self.cellule is not None:
            return self.cellule
        if self.item is not None:
            return self.item
        if self.bloc is None and creer:
            self.bloc = {'type': 'p', 'runs': []}
        return self.bloc['runs'] if self.bloc else None

    def _fermer_bloc(self):
        if self.bloc is not None:
            if _a_du_texte(self.bloc['runs']) or self.bloc['type'] in TITRES:
                self.blocs.append(self.bloc)
            self.bloc = None

    def _fermer_liste(self):
        self._fermer_item()
        if self.liste is not None:
            if self.liste['items']:
                self.blocs.append(self.liste)
            self.liste = None

    def _fermer_item(self):
        if self.item is not None and self.liste is not None:
            if _a_du_texte(self.item):
                self.liste['items'].append(_nettoyer_runs(self.item))
        self.item = None

    def _fermer_table(self):
        self._fermer_ligne()
        if self.table is not None:
            if self.table['rows']:
                self.blocs.append(self.table)
            self.table = None

    def _fermer_ligne(self):
        self._fermer_cellule()
        if self.ligne is not None and self.table is not None:
            if self.ligne['cells']:
                self.table['rows'].append(self.ligne)
        self.ligne = None

    def _fermer_cellule(self):
        if self.cellule is not None and self.ligne is not None:
            self.ligne['cells'].append(_nettoyer_runs(self.cellule))
        self.cellule = None

    # --- balises ------------------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if tag in IGNORES:
            self.ignore += 1
            return
        if self.ignore:
            return
        tag = TITRES_RAMENES.get(tag, tag)
        attrs = dict(attrs)

        if tag in GRAS:
            self.gras += 1
        elif tag in ITALIQUE:
            self.italique += 1
        elif tag in SOULIGNE:
            self.souligne += 1
        elif tag == 'br':
            runs = self._runs_courants()
            runs.append({'br': True})
        elif tag == 'table' and self.table is None:
            self._fermer_bloc()
            self._fermer_liste()
            self.table = {'type': 'table', 'rows': []}
        elif tag == 'tr' and self.table is not None:
            self._fermer_ligne()
            self.ligne = {'header': False, 'cells': []}
        elif tag in ('td', 'th') and self.table is not None:
            if self.ligne is None:
                self.ligne = {'header': False, 'cells': []}
            self._fermer_cellule()
            self.cellule = []
            if tag == 'th':
                self.ligne['header'] = True
        elif self.table is not None:
            return  # pas de blocs imbriqués dans un tableau : le texte va dans la cellule
        elif tag == 'figure':
            ref = attrs.get('data-figure') or ''
            if RE_REF_FIGURE.match(ref):
                self._fermer_bloc()
                self._fermer_liste()
                self.blocs.append({'type': 'figure', 'ref': ref})
        elif tag in ('ul', 'ol'):
            self._fermer_bloc()
            if self.liste is None:
                self.liste = {'type': tag, 'items': []}
        elif tag == 'li' and self.liste is not None:
            self._fermer_item()
            self.item = []
        elif tag in TITRES or tag in BLOCS_PARAGRAPHE:
            if self.liste is not None:
                return  # <p> dans un <li> : on reste dans l'élément de liste
            self._fermer_bloc()
            self.bloc = {'type': tag if tag in TITRES else 'p', 'runs': []}
            if tag == 'h2':
                cle = attrs.get('data-section') or ''
                type_section = attrs.get('data-type') or ''
                if RE_CLE_SECTION.match(cle):
                    self.bloc['section'] = cle
                    self.bloc['section_type'] = type_section if type_section in TYPES_SECTION else 'libre'

    def handle_endtag(self, tag):
        if tag in IGNORES:
            self.ignore = max(0, self.ignore - 1)
            return
        if self.ignore:
            return
        tag = TITRES_RAMENES.get(tag, tag)
        if tag in GRAS:
            self.gras = max(0, self.gras - 1)
        elif tag in ITALIQUE:
            self.italique = max(0, self.italique - 1)
        elif tag in SOULIGNE:
            self.souligne = max(0, self.souligne - 1)
        elif tag == 'table':
            self._fermer_table()
        elif tag == 'tr':
            self._fermer_ligne()
        elif tag in ('td', 'th'):
            self._fermer_cellule()
        elif self.table is not None:
            return
        elif tag in ('ul', 'ol'):
            self._fermer_liste()
        elif tag == 'li':
            self._fermer_item()
        elif tag in TITRES or tag in BLOCS_PARAGRAPHE:
            if self.liste is None:
                self._fermer_bloc()

    def handle_data(self, data):
        if self.ignore or not data:
            return
        if self.table is not None and self.cellule is None:
            return  # espaces entre balises de tableau
        if self.liste is not None and self.item is None:
            return
        data = re.sub(r'\s+', ' ', data)
        if data == ' ' and self._runs_courants(creer=False) is None:
            return
        runs = self._runs_courants()
        runs.append({'t': data, 'b': self.gras > 0, 'i': self.italique > 0, 'u': self.souligne > 0})

    def close(self):
        super().close()
        self._fermer_table()
        self._fermer_liste()
        self._fermer_bloc()


def _a_du_texte(runs):
    return any(r.get('t', '').strip() for r in runs)


def _nettoyer_runs(runs):
    """Fusionne les runs de même style, retire les espaces/sauts de ligne en bord."""
    fusion = []
    for run in runs:
        if 'br' in run:
            fusion.append({'br': True})
            continue
        if not run['t']:
            continue
        precedent = fusion[-1] if fusion else None
        if precedent and 'br' not in precedent and all(precedent[k] == run[k] for k in 'biu'):
            precedent['t'] += run['t']
        else:
            fusion.append(dict(run))
    while fusion and ('br' in fusion[0] or not fusion[0]['t'].strip()):
        fusion.pop(0)
    while fusion and ('br' in fusion[-1] or not fusion[-1]['t'].strip()):
        fusion.pop()
    if fusion:
        fusion[0]['t'] = fusion[0]['t'].lstrip()
        fusion[-1]['t'] = fusion[-1]['t'].rstrip()
    return fusion


def lire(html):
    """HTML (même sale) -> liste de blocs."""
    lecteur = _Lecteur()
    lecteur.feed(html or '')
    lecteur.close()
    for bloc in lecteur.blocs:
        if 'runs' in bloc:
            bloc['runs'] = _nettoyer_runs(bloc['runs'])
    return lecteur.blocs


# --- écriture ------------------------------------------------------------------------------

def _runs_html(runs):
    morceaux = []
    for run in runs:
        if 'br' in run:
            morceaux.append('<br>')
            continue
        texte = escape(run['t'], quote=False)
        if run.get('u'):
            texte = f'<u>{texte}</u>'
        if run.get('i'):
            texte = f'<em>{texte}</em>'
        if run.get('b'):
            texte = f'<strong>{texte}</strong>'
        morceaux.append(texte)
    return ''.join(morceaux)


def ecrire(blocs):
    """Liste de blocs -> HTML propre (seules balises/attributs autorisés)."""
    html = []
    for bloc in blocs:
        t = bloc['type']
        if t in TITRES or t == 'p':
            attrs = ''
            if t == 'h2' and bloc.get('section'):
                attrs = f' data-section="{bloc["section"]}" data-type="{bloc.get("section_type") or "libre"}"'
            html.append(f'<{t}{attrs}>{_runs_html(bloc["runs"])}</{t}>')
        elif t in ('ul', 'ol'):
            items = ''.join(f'<li>{_runs_html(item)}</li>' for item in bloc['items'])
            html.append(f'<{t}>{items}</{t}>')
        elif t == 'table':
            lignes = []
            for row in bloc['rows']:
                balise = 'th' if row.get('header') else 'td'
                cellules = ''.join(f'<{balise}>{_runs_html(c)}</{balise}>' for c in row['cells'])
                lignes.append(f'<tr>{cellules}</tr>')
            html.append(f'<table>{"".join(lignes)}</table>')
        elif t == 'figure' and RE_REF_FIGURE.match(bloc.get('ref', '')):
            html.append(f'<figure data-figure="{bloc["ref"]}" contenteditable="false">'
                        f'<img src="figure/{bloc["ref"]}.png" alt="Graphique"></figure>')
    return '\n'.join(html)


def nettoyer(html):
    return ecrire(lire(html))


# --- texte brut (pour l'IA) ----------------------------------------------------------------

def texte_runs(runs):
    return ''.join('\n' if 'br' in r else r['t'] for r in runs).strip()


def en_texte(blocs):
    lignes = []
    for bloc in blocs:
        t = bloc['type']
        if t == 'h1':
            lignes.append(f"# {texte_runs(bloc['runs'])}")
        elif t == 'h2':
            lignes.append(f"\n## {texte_runs(bloc['runs'])}")
        elif t == 'h3':
            lignes.append(f"### {texte_runs(bloc['runs'])}")
        elif t == 'p':
            lignes.append(texte_runs(bloc['runs']))
        elif t in ('ul', 'ol'):
            for n, item in enumerate(bloc['items'], 1):
                puce = f'{n}.' if t == 'ol' else '-'
                lignes.append(f'{puce} {texte_runs(item)}')
        elif t == 'table':
            for row in bloc['rows']:
                lignes.append('| ' + ' | '.join(texte_runs(c) for c in row['cells']) + ' |')
    return '\n'.join(lignes).strip()


# --- construction (sections du modèle, texte IA) -------------------------------------------

def run(texte, b=False, i=False):
    return {'t': texte, 'b': b, 'i': i, 'u': False}


def paragraphe(texte, b=False, i=False):
    return {'type': 'p', 'runs': [run(texte, b=b, i=i)]}


def titre(niveau, texte, section=None, section_type=None):
    bloc = {'type': f'h{niveau}', 'runs': [run(texte)]}
    if section:
        bloc['section'] = section
        bloc['section_type'] = section_type
    return bloc


def tableau(entetes, lignes):
    rows = [{'header': True, 'cells': [[run(str(c))] for c in entetes]}]
    for ligne in lignes:
        rows.append({'header': False, 'cells': [[run('' if c is None else str(c))] for c in ligne]})
    return {'type': 'table', 'rows': rows}


def liste(items):
    """items : textes, ou listes de runs (ex. [run('WISC-V', b=True), run(' : ...')])."""
    return {'type': 'ul', 'items': [item if isinstance(item, list) else [run(item)] for item in items]}


def figure(ref):
    return {'type': 'figure', 'ref': ref}


RE_GRAS_MD = re.compile(r'\*\*(.+?)\*\*')


RE_PUCE = re.compile(r'^([-*•]|\d+[.)])\s+')
RE_TITRE_MD = re.compile(r'^#{1,6}\s+')


def _normaliser_titre(texte):
    return re.sub(r'[\s:.]+$', '', texte.strip().lower())


def blocs_depuis_texte(texte, titre_a_ignorer=None):
    """Texte rédigé par l'IA (markdown léger) -> blocs : lignes « - »/« 1. » -> liste, « ## » ->
    sous-titre h3, **gras** converti, lignes consécutives -> un paragraphe avec retours à la ligne.
    Un titre identique à `titre_a_ignorer` (titre de la section, que l'IA répète parfois) est retiré."""
    blocs = []
    for morceau in re.split(r'\n\s*\n', (texte or '').strip()):
        paragraphe, liste_courante = None, None
        for ligne in (l.strip() for l in morceau.split('\n')):
            if not ligne:
                continue
            if RE_TITRE_MD.match(ligne):
                titre_md = RE_TITRE_MD.sub('', ligne).strip('*').strip()
                paragraphe = liste_courante = None
                if titre_a_ignorer and _normaliser_titre(titre_md) == _normaliser_titre(titre_a_ignorer):
                    continue
                blocs.append({'type': 'h3', 'runs': [run(titre_md)]})
            elif RE_PUCE.match(ligne):
                paragraphe = None
                if liste_courante is None:
                    liste_courante = {'type': 'ul', 'items': []}
                    blocs.append(liste_courante)
                liste_courante['items'].append(_runs_markdown(RE_PUCE.sub('', ligne)))
            else:
                liste_courante = None
                if paragraphe is None:
                    paragraphe = {'type': 'p', 'runs': []}
                    blocs.append(paragraphe)
                else:
                    paragraphe['runs'].append({'br': True})
                paragraphe['runs'].extend(_runs_markdown(ligne))
    return blocs


def _runs_markdown(ligne):
    runs = []
    position = 0
    for m in RE_GRAS_MD.finditer(ligne):
        if m.start() > position:
            runs.append(run(ligne[position:m.start()]))
        runs.append(run(m.group(1), b=True))
        position = m.end()
    if position < len(ligne):
        runs.append(run(ligne[position:]))
    return runs


# --- sections ------------------------------------------------------------------------------

def decouper_sections(blocs):
    """-> (préambule, [(bloc_titre_h2_section, [blocs du corps])]). Les h2 sans data-section
    restent dans le corps de la section précédente."""
    preambule, sections = [], []
    for bloc in blocs:
        if bloc['type'] == 'h2' and bloc.get('section'):
            sections.append((bloc, []))
        elif sections:
            sections[-1][1].append(bloc)
        else:
            preambule.append(bloc)
    return preambule, sections


def assembler_sections(preambule, sections):
    blocs = list(preambule)
    for titre_bloc, corps in sections:
        blocs.append(titre_bloc)
        blocs.extend(corps)
    return blocs
