import json
from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, License, User
from cabinet.models import Patient, Consultation, Depense


class BackupTestCaseBase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.organization, plan='lifetime', status='active')
        self.user = User.objects.create_user(
            username="psy", password="test-pass-123", role='psychologist', organization=self.organization
        )
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1)
        )
        self.client.force_login(self.user)


class BackupPageTests(BackupTestCaseBase):

    def test_page_saffiche(self):
        response = self.client.get(reverse('cabinet:backup_page'))
        self.assertEqual(response.status_code, 200)


class BackupExportTests(BackupTestCaseBase):

    def test_export_contient_les_patients_et_depenses(self):
        Depense.objects.create(
            organization=self.organization, categorie='loyer', montant=200, date_depense='2026-09-01',
        )

        response = self.client.get(reverse('cabinet:backup_export'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

        data = json.loads(response.content)
        self.assertEqual(len(data['patients']), 1)
        self.assertEqual(len(data['depenses']), 1)
        self.assertEqual(data['organization'], 'Cabinet Test')

    def test_isolation_par_organisation(self):
        autre_org = Organization.objects.create(name="Autre Cabinet", slug="autre-cabinet")
        Patient.objects.create(
            organization=autre_org, nom="Martin", prenom="Paul", date_naissance=date(1985, 1, 1)
        )

        response = self.client.get(reverse('cabinet:backup_export'))
        data = json.loads(response.content)
        noms = [p['fields']['nom'] for p in data['patients']]
        self.assertNotIn('Martin', noms)
