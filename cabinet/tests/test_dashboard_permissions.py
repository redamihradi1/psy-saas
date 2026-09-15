from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, License, User


class DashboardPermissionAwareTests(TestCase):
    """Le dashboard ne doit afficher (et calculer) que ce que l'utilisateur peut voir - un(e)
    assistant(e) sans accès à un module ne doit pas voir son widget, même en lecture seule."""

    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.org, plan='lifetime', status='active')

    def test_assistant_patients_uniquement_ne_voit_pas_les_autres_widgets(self):
        user = User.objects.create_user(
            username='assist', password='motdepasse123', role='assistant', organization=self.org,
            can_access_patients=True, can_access_consultations=False, can_access_comptabilite=False,
            can_access_agenda=False,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('cabinet:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['can_patients'])
        self.assertFalse(response.context['can_consultations'])
        self.assertFalse(response.context['can_comptabilite'])
        self.assertContains(response, 'Patients actifs')
        self.assertNotContains(response, "Chiffre d'affaires")
        self.assertNotContains(response, 'Nouvelle consultation')

    def test_psychologue_avec_acces_complet_voit_tout(self):
        user = User.objects.create_user(
            username='psy', password='motdepasse123', role='psychologist', organization=self.org,
            can_access_patients=True, can_access_consultations=True, can_access_comptabilite=True,
            can_access_agenda=True,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('cabinet:dashboard'))
        self.assertContains(response, 'Patients actifs')
        self.assertContains(response, "Chiffre d'affaires")
        self.assertContains(response, 'Nouvelle consultation')

    def test_aucun_module_affiche_etat_vide(self):
        user = User.objects.create_user(
            username='assist', password='motdepasse123', role='assistant', organization=self.org,
            can_access_patients=False, can_access_consultations=False, can_access_comptabilite=False,
            can_access_agenda=False,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('cabinet:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aucun module accessible')
