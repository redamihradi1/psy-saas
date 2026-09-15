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

    def test_assistant_patients_uniquement_ne_voit_pas_le_suivi_clinique(self):
        """Régression : anamnèse/consultations/fichiers/statistiques/journal clinique sont du
        suivi clinique (module Consultations), pas juste de l'identité patient (module Patients).
        Les montants payés ne doivent même pas apparaître dans le HTML (pas juste être cachés en CSS/JS)."""
        from accounts.models import User
        from cabinet.models import Consultation

        Consultation.objects.create(
            organization=self.organization, patient=self.patient,
            date_seance='2026-01-15T10:00:00Z', tarif=500, statut_paiement='paye',
        )
        assistant = User.objects.create_user(
            username='assist', password='motdepasse123', role='assistant', organization=self.organization,
            can_access_patients=True, can_access_consultations=False, can_access_tags=False,
        )
        self.client.force_login(assistant)

        response = self.client.get(reverse('cabinet:patient_detail', kwargs={'patient_id': self.patient.id}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['can_consultations'])
        self.assertEqual(response.context['total_consultations'], 0)
        self.assertEqual(response.context['total_paye'], 0)

        content = response.content.decode()
        self.assertNotIn('DHS', content)
        self.assertNotIn('Anamnèse', content)
        self.assertNotIn('Journal clinique', content)
        self.assertNotIn('Gérer les tags', content)

    def test_avec_acces_consultations_voit_le_suivi_clinique(self):
        from accounts.models import User
        from cabinet.models import Consultation

        Consultation.objects.create(
            organization=self.organization, patient=self.patient,
            date_seance='2026-01-15T10:00:00Z', tarif=500, statut_paiement='paye',
        )
        assistant = User.objects.create_user(
            username='assist', password='motdepasse123', role='assistant', organization=self.organization,
            can_access_patients=True, can_access_consultations=True,
        )
        self.client.force_login(assistant)

        response = self.client.get(reverse('cabinet:patient_detail', kwargs={'patient_id': self.patient.id}))
        self.assertTrue(response.context['can_consultations'])
        self.assertEqual(response.context['total_consultations'], 1)
        self.assertContains(response, 'DHS')
        self.assertContains(response, 'Journal clinique')

    def test_onglet_tests_visible_si_licence_et_permission_ok(self):
        """La fiche patient doit permettre au psychologue de revoir l'historique de tests
        directement, comme sur la vue d'ensemble du super admin (groupée par catégorie)."""
        from tests_psy.models import TestVineland

        self.license.has_vineland = True
        self.license.save()
        test = TestVineland.objects.create(
            organization=self.organization, patient=self.patient, psychologue=self.user,
        )

        response = self.client.get(reverse('cabinet:patient_detail', kwargs={'patient_id': self.patient.id}))
        self.assertContains(response, 'Tests psychométriques')
        categories = {cat['label']: cat['tests'] for cat in response.context['tests_categories']}
        self.assertIn('Vineland', categories)
        self.assertEqual(categories['Vineland'][0]['resultats_url'], reverse('tests_psy:vineland_resultats', args=[test.id]))
        self.assertEqual(categories['Vineland'][0]['edit_url'], reverse('tests_psy:vineland_questionnaire', args=[test.id]))

    def test_onglet_tests_absent_si_licence_desactivee(self):
        response = self.client.get(reverse('cabinet:patient_detail', kwargs={'patient_id': self.patient.id}))
        self.assertEqual(response.context['tests_categories'], [])
        self.assertNotContains(response, 'Tests psychométriques')

    def test_onglet_tests_absent_pour_assistant_sans_permission_test(self):
        from accounts.models import User

        self.license.has_vineland = True
        self.license.save()
        assistant = User.objects.create_user(
            username='assist', password='motdepasse123', role='assistant', organization=self.organization,
            can_access_patients=True, can_access_vineland=False,
        )
        self.client.force_login(assistant)

        response = self.client.get(reverse('cabinet:patient_detail', kwargs={'patient_id': self.patient.id}))
        self.assertEqual(response.context['tests_categories'], [])
        self.assertNotContains(response, 'Tests psychométriques')


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
