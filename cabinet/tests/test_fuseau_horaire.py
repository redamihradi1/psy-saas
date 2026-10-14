"""Maroc en GMT+0 permanent depuis le 2026-09-20 (IANA 2026c) : lecture des heures + recalage des données."""
import importlib
from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.apps import apps
from django.test import TestCase
from django.utils import timezone

from accounts.models import Organization, License
from cabinet.ics_utils import _dt_utc
from cabinet.models import Patient, Consultation, Indisponibilite

UTC = dt_timezone.utc
migration = importlib.import_module('cabinet.migrations.0011_corrige_fuseau_maroc_gmt0')


class FuseauMarocTests(TestCase):

    def test_casablanca_en_gmt0_apres_le_20_septembre_2026(self):
        tz = timezone.get_default_timezone()
        self.assertEqual(datetime(2026, 6, 1, 12, tzinfo=tz).utcoffset(), timedelta(hours=1))
        self.assertEqual(datetime(2026, 10, 14, 12, tzinfo=tz).utcoffset(), timedelta(0))
        self.assertEqual(datetime(2027, 6, 1, 12, tzinfo=tz).utcoffset(), timedelta(0))

    def test_heure_saisie_stockee_sans_decalage(self):
        seance = timezone.make_aware(datetime(2026, 10, 20, 10, 0))
        self.assertEqual(seance.astimezone(UTC), datetime(2026, 10, 20, 10, 0, tzinfo=UTC))
        self.assertEqual(_dt_utc(seance), '20261020T100000Z')


class RecalageMigrationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.organization, plan='lifetime', status='active')
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1)
        )

    def _seance(self, dt):
        return Consultation.objects.create(
            organization=self.organization, patient=self.patient, date_seance=dt, tarif=0,
        )

    def test_decale_uniquement_les_valeurs_stockees_en_gmt1(self):
        # Saisies « 10:00 » avec l'ancienne règle
        apres_bascule = self._seance(datetime(2026, 10, 20, 9, 0, tzinfo=UTC))      # GMT+1 -> faux
        avant_bascule = self._seance(datetime(2026, 9, 1, 9, 0, tzinfo=UTC))        # GMT+1 correct à l'époque
        ramadan_2027 = self._seance(datetime(2027, 2, 20, 10, 0, tzinfo=UTC))       # ancienne règle déjà GMT+0
        indispo = Indisponibilite.objects.create(
            organization=self.organization, titre='Congé', type_absence='conge',
            date_debut=datetime(2026, 11, 2, 8, 0, tzinfo=UTC), date_fin=datetime(2026, 11, 2, 17, 0, tzinfo=UTC),
        )

        migration.decaler(apps, +1)

        for obj in (apres_bascule, avant_bascule, ramadan_2027, indispo):
            obj.refresh_from_db()
        self.assertEqual(apres_bascule.date_seance, datetime(2026, 10, 20, 10, 0, tzinfo=UTC))
        self.assertEqual(avant_bascule.date_seance, datetime(2026, 9, 1, 9, 0, tzinfo=UTC))
        self.assertEqual(ramadan_2027.date_seance, datetime(2027, 2, 20, 10, 0, tzinfo=UTC))
        self.assertEqual(indispo.date_debut, datetime(2026, 11, 2, 9, 0, tzinfo=UTC))
        self.assertEqual(indispo.date_fin, datetime(2026, 11, 2, 18, 0, tzinfo=UTC))

        migration.decaler(apps, -1)
        apres_bascule.refresh_from_db()
        self.assertEqual(apres_bascule.date_seance, datetime(2026, 10, 20, 9, 0, tzinfo=UTC))

    def test_garde_fou_passe_avec_tzdata_a_jour(self):
        migration.verifier_nouvelle_regle()
