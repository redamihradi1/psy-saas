from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, License, User
from cabinet.models import Patient


class CabinetTestCaseBase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        self.license = License.objects.create(
            organization=self.organization, plan='lifetime', status='active', max_patients=10,
        )
        self.user = User.objects.create_user(
            username="psy", password="test-pass-123", role='psychologist', organization=self.organization
        )
        self.client.force_login(self.user)


class PatientListIsolationTests(CabinetTestCaseBase):

    def test_ne_voit_que_les_patients_de_sa_propre_organisation(self):
        Patient.objects.create(organization=self.organization, nom="Alpha", prenom="A", date_naissance=date(1990, 1, 1))

        autre_org = Organization.objects.create(name="Autre Cabinet", slug="autre-cabinet")
        Patient.objects.create(organization=autre_org, nom="Beta", prenom="B", date_naissance=date(1990, 1, 1))

        response = self.client.get(reverse('cabinet:patients_list'))

        noms = [p.nom for p in response.context['page_obj']]
        self.assertEqual(noms, ["Alpha"])

    def test_recherche_filtre_par_nom_prenom_telephone(self):
        Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean",
            date_naissance=date(1990, 1, 1), telephone="0600000000",
        )
        Patient.objects.create(
            organization=self.organization, nom="Martin", prenom="Alice",
            date_naissance=date(1990, 1, 1), telephone="0611111111",
        )

        response = self.client.get(reverse('cabinet:patients_list'), {'search': 'dupont'})

        noms = [p.nom for p in response.context['page_obj']]
        self.assertEqual(noms, ["Dupont"])


class PatientCreateTests(CabinetTestCaseBase):

    def test_creation_reussie(self):
        response = self.client.post(reverse('cabinet:patient_create'), {
            'nom': 'Dupont', 'prenom': 'Jean', 'date_naissance': '1990-01-01',
            'categorie_age': 'adulte', 'telephone': '0600000000', 'email': 'jean@example.com',
        })

        patient = Patient.objects.get(nom='Dupont')
        self.assertRedirects(response, reverse('cabinet:patient_detail', kwargs={'patient_id': patient.id}))
        self.assertEqual(patient.organization, self.organization)

    def test_quota_patients_atteint_bloque_la_creation(self):
        self.license.max_patients = 1
        self.license.save()
        Patient.objects.create(organization=self.organization, nom="Existant", prenom="X", date_naissance=date(1990, 1, 1))

        response = self.client.post(reverse('cabinet:patient_create'), {
            'nom': 'Dupont', 'prenom': 'Jean', 'date_naissance': '1990-01-01',
            'categorie_age': 'adulte',
        }, follow=True)

        self.assertRedirects(response, reverse('cabinet:patients_list'))
        self.assertEqual(Patient.objects.count(), 1)

    def test_date_naissance_dans_le_futur_est_rejetee(self):
        response = self.client.post(reverse('cabinet:patient_create'), {
            'nom': 'Dupont', 'prenom': 'Jean', 'date_naissance': '2999-01-01',
            'categorie_age': 'adulte',
        })

        self.assertEqual(Patient.objects.count(), 0)
        self.assertEqual(response.status_code, 200)  # ré-affiche le formulaire avec erreur


class PatientDetailTests(CabinetTestCaseBase):

    def setUp(self):
        super().setUp()
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1)
        )

    def test_page_saffiche(self):
        response = self.client.get(reverse('cabinet:patient_detail', kwargs={'patient_id': self.patient.id}))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['anamnese'])


class PatientDeleteTests(CabinetTestCaseBase):

    def test_suppression_via_post(self):
        patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1)
        )

        response = self.client.post(reverse('cabinet:patient_delete', kwargs={'patient_id': patient.id}))

        self.assertRedirects(response, reverse('cabinet:patients_list'))
        self.assertFalse(Patient.objects.filter(id=patient.id).exists())

    def test_get_naffiche_que_la_confirmation_sans_supprimer(self):
        patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1)
        )

        response = self.client.get(reverse('cabinet:patient_delete', kwargs={'patient_id': patient.id}))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Patient.objects.filter(id=patient.id).exists())
