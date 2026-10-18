"""Pseudonymisation de tout texte envoyé à l'IA externe.

Avant envoi : le prénom/nom du patient deviennent [PRÉNOM]/[NOM], le psychologue
[PSYCHOLOGUE], le cabinet [CABINET], les noms des autres patients du cabinet (frère, sœur,
parent suivi au même cabinet...), l'établissement scolaire et la personne qui adresse le patient
[PERSONNE_1], [PERSONNE_2]..., les emails [EMAIL] et numéros
de téléphone [TÉLÉPHONE]. Au retour, chaque étiquette retrouve sa valeur (le texte exact masqué
pour les [PERSONNE_n] : un faux positif comme « grâce » pour une patiente « Grace » est donc
restauré à l'identique) - le psychologue voit toujours les vrais noms. La date de naissance,
elle, est volontairement transmise (décision du 2026-10-17 : donnée utile à l'analyse).
"""
import re

PRENOM, NOM, PSYCHOLOGUE, CABINET = '[PRÉNOM]', '[NOM]', '[PSYCHOLOGUE]', '[CABINET]'
EMAIL, TELEPHONE = '[EMAIL]', '[TÉLÉPHONE]'

LONGUEUR_MIN_NOM = 2
LONGUEUR_MIN_AUTRE_NOM = 3  # noms d'autres patients : évite de masquer « Al », « Ba »...
VARIANTES = {
    'a': 'aàâäáã', 'e': 'eéèêë', 'i': 'iîïí', 'o': 'oôöó', 'u': 'uùûüú', 'c': 'cç', 'y': 'yÿ', 'n': 'nñ',
}
RE_EMAIL = re.compile(r'[\w.+-]+@[\w-]+(\.[\w-]+)+')
# 9 chiffres ou plus, séparés au plus par un espace/point/tiret : 06 12 34 56 78, +212 6...
RE_TELEPHONE = re.compile(r'(?<![\w])(?:\+|00)?\d(?:[ .-]?\d){8,}(?![\w])')


def _motif_nom(nom):
    """Regex insensible à la casse et aux accents, sur mots entiers ("Sara" ≠ "Saranda")."""
    return r'(?<![\w])' + _motif_lettres(nom) + r'(?![\w])'


def _motif_lettres(nom):
    morceaux = []
    for car in nom.strip():
        base = _sans_accent(car.lower())
        if base in VARIANTES:
            classe = VARIANTES[base]
            morceaux.append(f'[{classe}{classe.upper()}]')
        elif car.isspace() or car in "-'’":
            morceaux.append(r"[\s'’-]+")
        else:
            morceaux.append(re.escape(car))
    return ''.join(morceaux)


MOTS_GENERIQUES = {
    'docteur', 'professeur', 'madame', 'monsieur', 'pedopsychiatre', 'psychiatre', 'neurologue', 'pediatre',
    'neuropediatre', 'orthophoniste', 'medecin', 'psychologue', 'psychomotricien', 'psychomotricienne',
    'ergotherapeute', 'ecole', 'parents', 'mere', 'pere', 'famille', 'enseignant', 'enseignante', 'institutrice',
    'maitresse', 'directeur', 'directrice', 'traitant', 'scolaire', 'hopital', 'clinique', 'centre',
}


def _sans_accents(texte):
    return ''.join(_sans_accent(c) for c in texte)


def _sans_accent(car):
    for base, variantes in VARIANTES.items():
        if car in variantes:
            return base
    return car


class Pseudonymiseur:
    def __init__(self, patient, psychologue=None, organization=None, autres_noms=()):
        self.prenom = (patient.prenom or '').strip()
        self.nom = (patient.nom or '').strip()
        self.nom_psy = (psychologue.get_full_name() or psychologue.username).strip() if psychologue else ''
        self.nom_cabinet = (organization.name or '').strip() if organization else ''

        # Ordre : les expressions les plus longues d'abord (nom complet avant prénom seul).
        remplacements = []
        if self.nom_psy:
            remplacements.append((self.nom_psy, PSYCHOLOGUE))
        if self.nom_cabinet:
            remplacements.append((self.nom_cabinet, CABINET))
        if self.prenom and self.nom:
            remplacements.append((f'{self.prenom} {self.nom}', f'{PRENOM} {NOM}'))
            remplacements.append((f'{self.nom} {self.prenom}', f'{NOM} {PRENOM}'))
        if self.nom:
            remplacements.append((self.nom, NOM))
        if self.prenom:
            remplacements.append((self.prenom, PRENOM))
        if psychologue:
            for partie in (psychologue.first_name, psychologue.last_name):
                if partie and partie.strip():
                    remplacements.append((partie.strip(), PSYCHOLOGUE))
        connus = {self.prenom.lower(), self.nom.lower()}
        for autre in autres_noms:
            autre = (autre or '').strip()
            if len(autre) >= LONGUEUR_MIN_AUTRE_NOM and autre.lower() not in connus:
                remplacements.append((autre, None))  # None : étiquette [PERSONNE_n] attribuée au masquage

        remplacements = [(texte, etiquette) for texte, etiquette in remplacements
                         if len(texte) >= LONGUEUR_MIN_NOM]
        remplacements.sort(key=lambda r: len(r[0]), reverse=True)
        self._regles = [(re.compile(_motif_nom(texte), re.IGNORECASE), etiquette)
                        for texte, etiquette in remplacements]
        self._personnes = {}  # texte exact masqué -> étiquette [PERSONNE_n]

    @classmethod
    def pour_bilan(cls, bilan):
        from cabinet.models import Patient
        autres = Patient.all_objects.filter(organization=bilan.organization).exclude(id=bilan.patient_id)
        autres_noms = set()
        for prenom, nom in autres.values_list('prenom', 'nom'):
            autres_noms.update([prenom, nom])
        autres_noms.update(cls.noms_des_infos(bilan.infos or {}))
        psy = bilan.psychologue if bilan.psychologue and not bilan.psychologue.is_superadmin() else \
            bilan.organization.users.filter(role='psychologist').order_by('id').first()
        return cls(bilan.patient, psy, bilan.organization, autres_noms)

    @staticmethod
    def noms_des_infos(infos):
        """Établissement scolaire et personne qui adresse le patient (« Dr Bennani ») : l'expression
        entière, et pour la personne chaque nom propre isolé (« Bennani » seul)."""
        noms = set()
        from .donnees import INFOS_A_MASQUER
        for cle in INFOS_A_MASQUER:
            valeur = (infos.get(cle) or '').strip()
            if not valeur:
                continue
            noms.add(valeur)
            if cle == 'adresse_par':
                for mot in re.findall(r"[\w'’-]+", valeur):
                    if len(mot) >= 4 and mot[0].isupper() and _sans_accents(mot.lower()) not in MOTS_GENERIQUES:
                        noms.add(mot)
        return noms

    def masquer(self, texte):
        if not texte:
            return texte
        texte = RE_EMAIL.sub(EMAIL, texte)
        texte = RE_TELEPHONE.sub(TELEPHONE, texte)
        for regle, etiquette in self._regles:
            texte = regle.sub(etiquette or self._etiquette_personne, texte)
        return texte

    def _etiquette_personne(self, match):
        trouve = match.group(0)
        if trouve not in self._personnes:
            self._personnes[trouve] = f'[PERSONNE_{len(self._personnes) + 1}]'
        return self._personnes[trouve]

    def restaurer(self, texte):
        if not texte:
            return texte
        texte = texte.replace(PRENOM, self.prenom or 'le patient').replace(NOM, self.nom)
        texte = texte.replace(PSYCHOLOGUE, self.nom_psy or 'le psychologue')
        texte = texte.replace(CABINET, self.nom_cabinet or 'le cabinet')
        # Du plus grand numéro au plus petit : [PERSONNE_12] avant [PERSONNE_1]
        for original, etiquette in sorted(self._personnes.items(), key=lambda p: -len(p[1])):
            texte = texte.replace(etiquette, original)
        # Variantes que l'IA écrit parfois sans accent / en minuscules
        texte = re.sub(r'\[pr[ée]nom\]', self.prenom or 'le patient', texte, flags=re.IGNORECASE)
        return re.sub(r'  +', ' ', texte)
