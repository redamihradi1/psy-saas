from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Organization, License, User
from cabinet.models import Indisponibilite


class IndisponibiliteTestCaseBase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.organization, plan='lifetime', status='active')
        self.user = User.objects.create_user(
            username="psy", password="test-pass-123", role='psychologist', organization=self.organization
        )
        self.client.force_login(self.user)


class IndisponibiliteCreateTests(IndisponibiliteTestCaseBase):

    def test_creation(self):
        response = self.client.post(reverse('cabinet:indisponibilite_create'), {
            'titre': 'Formation TCC',
            'type_absence': 'formation',
            'date_debut': '2026-10-01T09:00',
            'date_fin': '2026-10-03T18:00',
            'note': 'À Rabat',
        })
        self.assertRedirects(response, reverse('cabinet:agenda'))
        indispo = Indisponibilite.objects.get(titre='Formation TCC')
        self.assertEqual(indispo.organization, self.organization)
        self.assertEqual(indispo.type_absence, 'formation')


class IndisponibiliteDeleteTests(IndisponibiliteTestCaseBase):

    def test_suppression(self):
        indispo = Indisponibilite.objects.create(
            organization=self.organization, titre='Congé', type_absence='conge',
            date_debut=timezone.now(), date_fin=timezone.now(),
        )
        response = self.client.post(reverse('cabinet:indisponibilite_delete', args=[indispo.id]))
        self.assertRedirects(response, reverse('cabinet:agenda'))
        self.assertFalse(Indisponibilite.objects.filter(id=indispo.id).exists())


class IndisponibilitesApiTests(IndisponibiliteTestCaseBase):

    def test_retourne_les_evenements_au_bon_format(self):
        Indisponibilite.objects.create(
            organization=self.organization, titre='Déplacement doctorat', type_absence='deplacement',
            date_debut=timezone.now(), date_fin=timezone.now(),
        )
        response = self.client.get(reverse('cabinet:indisponibilites_api'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['extendedProps']['event_type'], 'indisponibilite')
        self.assertIn('Déplacement doctorat', data[0]['title'])

    def test_isolation_par_organisation(self):
        autre_org = Organization.objects.create(name="Autre Cabinet", slug="autre-cabinet")
        Indisponibilite.objects.create(
            organization=autre_org, titre='Congé autre cabinet', type_absence='conge',
            date_debut=timezone.now(), date_fin=timezone.now(),
        )
        response = self.client.get(reverse('cabinet:indisponibilites_api'))
        self.assertEqual(response.json(), [])
