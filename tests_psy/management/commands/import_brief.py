"""Charge en base le contenu protégé de la BRIEF depuis des fichiers JSON NON versionnés
(le repo GitHub est public, le questionnaire et les normes sont sous droit d'auteur) :

    python manage.py import_brief                      # fichiers par défaut s'ils existent
    python manage.py import_brief --items chemin.json --normes chemin.json

Format des fichiers : voir tests_psy/data/brief/README.md et les *.example.json.
Idempotent : relancer la commande met à jour les items et remplace chaque table de normes.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tests_psy.models.brief import (
    ECHELLE_CHOICES, INDICE_CHOICES, SEXE_CHOICES, ItemBRIEF, NormeBRIEF, PaireIncoherenceBRIEF,
)

DATA_DIR = Path(settings.BASE_DIR) / 'tests_psy' / 'data' / 'brief'
ECHELLES = {code for code, _ in ECHELLE_CHOICES}
CODES_NORMES = ECHELLES | {code for code, _ in INDICE_CHOICES}
SEXES = {code for code, _ in SEXE_CHOICES}


class Command(BaseCommand):
    help = "Importe les items, paires d'Incohérence et tables d'étalonnage BRIEF (fichiers JSON non versionnés)."

    def add_arguments(self, parser):
        parser.add_argument('--items', default=str(DATA_DIR / 'brief_parent_items.json'))
        parser.add_argument('--normes', default=str(DATA_DIR / 'brief_parent_normes.json'))

    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        importe = False
        for cle, fonction in (('items', self.importer_items), ('normes', self.importer_normes)):
            chemin = Path(options[cle])
            if not chemin.exists():
                self.log(self.style.WARNING(f"{cle} : fichier absent ({chemin}), ignoré."))
                continue
            with open(chemin, encoding='utf-8') as f:
                fonction(json.load(f))
            importe = True
        if not importe:
            raise CommandError("Aucun fichier BRIEF trouvé - voir tests_psy/data/brief/README.md.")

    def log(self, message):
        if self.verbosity > 0:
            self.stdout.write(message)

    @transaction.atomic
    def importer_items(self, data):
        forme = data.get('forme', 'parent')
        items = data['items']
        numeros = [item['numero'] for item in items]
        if len(set(numeros)) != len(numeros):
            raise CommandError("Numéros d'items en double.")
        for item in items:
            if item.get('echelle') and item['echelle'] not in ECHELLES:
                raise CommandError(f"Item {item['numero']} : échelle inconnue '{item['echelle']}'.")
        for item_a, item_b in data.get('paires_incoherence', []):
            if item_a not in numeros or item_b not in numeros:
                raise CommandError(f"Paire d'Incohérence {item_a}/{item_b} : item inconnu.")

        for item in items:
            ItemBRIEF.objects.update_or_create(
                forme=forme, numero=item['numero'],
                defaults={
                    'texte': item['texte'],
                    'echelle': item.get('echelle') or '',
                    'est_negativite': bool(item.get('negativite')),
                },
            )
        ItemBRIEF.objects.filter(forme=forme).exclude(numero__in=numeros).delete()

        PaireIncoherenceBRIEF.objects.filter(forme=forme).delete()
        for item_a, item_b in data.get('paires_incoherence', []):
            PaireIncoherenceBRIEF.objects.create(forme=forme, item_a=item_a, item_b=item_b)

        par_echelle = {code: sum(1 for i in items if i.get('echelle') == code) for code in ECHELLES}
        self.log(self.style.SUCCESS(
            f"Items BRIEF {forme} : {len(items)} items, "
            f"{sum(1 for i in items if i.get('negativite'))} items de Négativité, "
            f"{len(data.get('paires_incoherence', []))} paires d'Incohérence. Items par échelle : {par_echelle}"
        ))

    @transaction.atomic
    def importer_normes(self, data):
        forme = data.get('forme', 'parent')
        nb_lignes = 0
        for table in data['tables']:
            sexe, echelle = table['sexe'], table['echelle']
            age_min, age_max = table['age_min'], table['age_max']
            nom = f"{sexe} {age_min}-{age_max} {echelle}"
            if sexe not in SEXES or echelle not in CODES_NORMES:
                raise CommandError(f"Table {nom} : sexe ou échelle inconnu(e).")

            lignes = sorted((int(brut), valeurs) for brut, valeurs in table['scores'].items())
            # Garde-fous de saisie : score T et percentile ne décroissent jamais quand le
            # score brut augmente (une erreur de recopie se voit presque toujours ici).
            for (brut_prec, (t_prec, p_prec)), (brut, (t, p)) in zip(lignes, lignes[1:]):
                if t < t_prec:
                    raise CommandError(f"Table {nom} : score T décroissant entre brut {brut_prec} ({t_prec}) et {brut} ({t}).")
                if p is not None and p_prec is not None and p < p_prec:
                    raise CommandError(f"Table {nom} : percentile décroissant entre brut {brut_prec} ({p_prec}) et {brut} ({p}).")

            NormeBRIEF.objects.filter(forme=forme, sexe=sexe, age_min=age_min, age_max=age_max, echelle=echelle).delete()
            NormeBRIEF.objects.bulk_create([
                NormeBRIEF(
                    forme=forme, sexe=sexe, age_min=age_min, age_max=age_max, echelle=echelle,
                    score_brut=brut, score_t=t, percentile=p, ic90=table.get('ic90'),
                )
                for brut, (t, p) in lignes
            ])
            nb_lignes += len(lignes)
        self.log(self.style.SUCCESS(
            f"Normes BRIEF {forme} : {len(data['tables'])} tables, {nb_lignes} lignes."
        ))
