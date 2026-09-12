from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, License, User
from cabinet.models import Patient, Tag


class TagsTestCaseBase(TestCase):
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


class TagCrudTests(TagsTestCaseBase):

    def test_creation_tag(self):
        response = self.client.post(reverse('cabinet:tag_create'), {'nom': 'Anxiété', 'couleur': '#ff0000'})
        self.assertRedirects(response, reverse('cabinet:tags_list'))
        tag = Tag.objects.get(nom='Anxiété')
        self.assertEqual(tag.organization, self.organization)

    def test_creation_ne_duplique_pas(self):
        Tag.objects.create(organization=self.organization, nom='Anxiété', couleur='#ff0000')
        self.client.post(reverse('cabinet:tag_create'), {'nom': 'Anxiété', 'couleur': '#00ff00'})
        self.assertEqual(Tag.objects.filter(nom='Anxiété').count(), 1)

    def test_suppression_tag(self):
        tag = Tag.objects.create(organization=self.organization, nom='Anxiété', couleur='#ff0000')
        response = self.client.post(reverse('cabinet:tag_delete', args=[tag.id]))
        self.assertRedirects(response, reverse('cabinet:tags_list'))
        self.assertFalse(Tag.objects.filter(id=tag.id).exists())


class PatientTagsUpdateTests(TagsTestCaseBase):

    def test_assigner_des_tags_au_patient(self):
        tag1 = Tag.objects.create(organization=self.organization, nom='Anxiété')
        tag2 = Tag.objects.create(organization=self.organization, nom='Ado')

        response = self.client.post(
            reverse('cabinet:patient_tags_update', args=[self.patient.id]),
            {'tags': [tag1.id, tag2.id]},
        )
        self.assertRedirects(response, reverse('cabinet:patient_detail', kwargs={'patient_id': self.patient.id}))
        self.assertEqual(set(self.patient.tags.all()), {tag1, tag2})

    def test_retirer_tous_les_tags(self):
        tag1 = Tag.objects.create(organization=self.organization, nom='Anxiété')
        self.patient.tags.add(tag1)

        self.client.post(reverse('cabinet:patient_tags_update', args=[self.patient.id]), {})
        self.assertEqual(self.patient.tags.count(), 0)


class PatientsListFiltreTagTests(TagsTestCaseBase):

    def test_filtre_par_tag(self):
        tag = Tag.objects.create(organization=self.organization, nom='Anxiété')
        self.patient.tags.add(tag)
        autre_patient = Patient.objects.create(
            organization=self.organization, nom="Martin", prenom="Paul", date_naissance=date(1985, 1, 1)
        )

        response = self.client.get(reverse('cabinet:patients_list'), {'tag': tag.id})
        noms = [p.nom for p in response.context['page_obj']]
        self.assertIn('Dupont', noms)
        self.assertNotIn('Martin', noms)
