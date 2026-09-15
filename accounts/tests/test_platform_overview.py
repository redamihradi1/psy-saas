from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, License, User
from cabinet.models import Patient


class SuperadminLoginRedirectTests(TestCase):

    def setUp(self):
        self.superadmin = User.objects.create_user(username='super', password='motdepasse123', role='superadmin')
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.org, plan='lifetime', status='active')
        self.psychologue = User.objects.create_user(
            username='psy', password='motdepasse123', role='psychologist', organization=self.org,
        )

    def test_superadmin_atterrit_sur_clients_list(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'super', 'password': 'motdepasse123',
        })
        self.assertRedirects(response, reverse('accounts:clients_list'))

    def test_psychologue_atterrit_sur_le_dashboard_cabinet(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'psy', 'password': 'motdepasse123',
        })
        self.assertRedirects(response, reverse('cabinet:dashboard'))


class SuperadminSansOrganisationPeutAccederAuxTestsTests(TestCase):
    """Régression : le super admin n'a pas d'organisation propre (il navigue à travers tous
    les cabinets) - require_test_access ne doit pas le bloquer avec "pas associé à une
    organisation" avant même de vérifier son rôle."""

    def setUp(self):
        self.superadmin = User.objects.create_user(username='super', password='motdepasse123', role='superadmin')
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.org, plan='lifetime', status='active', has_vineland=True)
        self.psychologue = User.objects.create_user(
            username='psy', password='motdepasse123', role='psychologist', organization=self.org,
        )
        self.patient = Patient.objects.create(
            organization=self.org, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1),
        )

    def test_superadmin_accede_a_la_liste_vineland_dune_autre_organisation(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse('tests_psy:vineland_liste'))
        self.assertEqual(response.status_code, 200)

    def test_superadmin_accede_aux_resultats_et_passation_beck_dune_autre_organisation(self):
        """Régression : beck_passation/beck_resultats filtraient par
        organization=request.user.organization - toujours None pour le super admin, donc 404
        systématique sur le test de N'IMPORTE quelle organisation."""
        from tests_psy.models import TestBeck

        test = TestBeck.objects.create(organization=self.org, patient=self.patient, psychologue=self.psychologue)

        self.client.force_login(self.superadmin)
        response = self.client.get(reverse('tests_psy:beck_resultats', args=[test.id]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('tests_psy:beck_passation', args=[test.id]))
        self.assertEqual(response.status_code, 200)

    def test_superadmin_accede_aux_resultats_et_passation_stai_dune_autre_organisation(self):
        from tests_psy.models import TestSTAI

        test = TestSTAI.objects.create(organization=self.org, patient=self.patient, psychologue=self.psychologue)

        self.client.force_login(self.superadmin)
        response = self.client.get(reverse('tests_psy:stai_resultats', args=[test.id]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('tests_psy:stai_passation', args=[test.id]))
        self.assertEqual(response.status_code, 200)

    def test_superadmin_accede_aux_resultats_et_passation_d2r_dune_autre_organisation(self):
        from tests_psy.models import TestD2R

        test = TestD2R.objects.create(
            organization=self.org, patient=self.patient, psychologue=self.psychologue,
            code='D2R-1', date=date(2026, 1, 15), age=26, sexe='M',
            correction_vue='NO', lateralite='D',
        )

        self.client.force_login(self.superadmin)
        response = self.client.get(reverse('tests_psy:d2r_resultats', args=[test.id]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('tests_psy:d2r_passation', args=[test.id]))
        self.assertEqual(response.status_code, 200)


class ClientsListStatsTests(TestCase):

    def setUp(self):
        self.superadmin = User.objects.create_user(username='super', password='motdepasse123', role='superadmin')
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.org, plan='lifetime', status='active')
        Patient.objects.create(organization=self.org, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1))
        self.client.force_login(self.superadmin)

    def test_stats_globales_dans_le_contexte(self):
        response = self.client.get(reverse('accounts:clients_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_clients'], 1)
        self.assertEqual(response.context['total_patients'], 1)
        self.assertEqual(response.context['licences_actives'], 1)


class ClientPatientsHistoryTests(TestCase):

    def setUp(self):
        self.superadmin = User.objects.create_user(username='super', password='motdepasse123', role='superadmin')
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.org, plan='lifetime', status='active', has_vineland=True)
        self.psychologue = User.objects.create_user(
            username='psy', password='motdepasse123', role='psychologist', organization=self.org,
        )
        self.patient = Patient.objects.create(
            organization=self.org, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1),
        )
        self.client.force_login(self.superadmin)

    def test_liste_les_patients_du_cabinet(self):
        response = self.client.get(reverse('accounts:client_patients', args=[self.org.id]))
        self.assertEqual(response.status_code, 200)
        noms = [entry['patient'].nom for entry in response.context['patients_avec_tests']]
        self.assertEqual(noms, ['Dupont'])

    def test_regroupe_les_tests_par_categorie_avec_liens_resultats_et_edition(self):
        from tests_psy.models import TestVineland, TestBeck
        vineland = TestVineland.objects.create(organization=self.org, patient=self.patient, psychologue=self.psychologue)
        beck = TestBeck.objects.create(organization=self.org, patient=self.patient, psychologue=self.psychologue)

        response = self.client.get(reverse('accounts:client_patients', args=[self.org.id]))
        entry = response.context['patients_avec_tests'][0]
        categories = {cat['label']: cat['tests'] for cat in entry['categories']}

        self.assertEqual(set(categories.keys()), {'Vineland', 'Beck'})
        self.assertEqual(len(categories['Vineland']), 1)
        self.assertEqual(categories['Vineland'][0]['resultats_url'], reverse('tests_psy:vineland_resultats', args=[vineland.id]))
        self.assertEqual(categories['Vineland'][0]['edit_url'], reverse('tests_psy:vineland_questionnaire', args=[vineland.id]))
        self.assertEqual(categories['Beck'][0]['resultats_url'], reverse('tests_psy:beck_resultats', args=[beck.id]))
        self.assertEqual(categories['Beck'][0]['edit_url'], reverse('tests_psy:beck_passation', args=[beck.id]))

    def test_psychologue_ne_peut_pas_acceder_a_cette_vue(self):
        self.client.force_login(self.psychologue)
        response = self.client.get(reverse('accounts:client_patients', args=[self.org.id]))
        self.assertRedirects(response, reverse('cabinet:dashboard'))
