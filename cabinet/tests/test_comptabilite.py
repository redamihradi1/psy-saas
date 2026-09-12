from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Organization, License, User
from cabinet.models import Patient, Consultation, Depense


class ComptabiliteTestCaseBase(TestCase):
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


class ComptabiliteDashboardTests(ComptabiliteTestCaseBase):

    def test_page_saffiche(self):
        response = self.client.get(reverse('cabinet:comptabilite_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_calcule_le_resultat_net_du_mois(self):
        today = timezone.now()
        Consultation.objects.create(
            organization=self.organization, patient=self.patient, date_seance=today,
            tarif=500, statut_paiement='paye',
        )
        Consultation.objects.create(
            organization=self.organization, patient=self.patient, date_seance=today,
            tarif=300, statut_paiement='attente',
        )
        Depense.objects.create(
            organization=self.organization, categorie='loyer', montant=200,
            date_depense=today.date(),
        )

        response = self.client.get(reverse('cabinet:comptabilite_dashboard'))
        self.assertEqual(response.context['revenus_mois'], 500)
        self.assertEqual(response.context['depenses_mois'], 200)
        self.assertEqual(response.context['resultat_mois'], 300)

    def test_alerte_liste_consultations_impayees_et_a_zero(self):
        today = timezone.now()
        payee = Consultation.objects.create(
            organization=self.organization, patient=self.patient, date_seance=today,
            tarif=400, statut_paiement='paye',
        )
        attente = Consultation.objects.create(
            organization=self.organization, patient=self.patient, date_seance=today,
            tarif=400, statut_paiement='attente',
        )
        gratuite = Consultation.objects.create(
            organization=self.organization, patient=self.patient, date_seance=today,
            tarif=0, statut_paiement='paye',
        )
        annulee_impayee = Consultation.objects.create(
            organization=self.organization, patient=self.patient, date_seance=today,
            tarif=400, statut_paiement='attente', statut_consultation='annule',
        )

        response = self.client.get(reverse('cabinet:comptabilite_dashboard'))
        alertes = list(response.context['alertes_paiement'])
        self.assertNotIn(payee, alertes)
        self.assertIn(attente, alertes)
        self.assertIn(gratuite, alertes)
        self.assertNotIn(annulee_impayee, alertes)

    def test_isolation_par_organisation(self):
        autre_org = Organization.objects.create(name="Autre Cabinet", slug="autre-cabinet")
        Depense.objects.create(
            organization=autre_org, categorie='loyer', montant=999,
            date_depense=timezone.now().date(),
        )

        response = self.client.get(reverse('cabinet:comptabilite_dashboard'))
        self.assertEqual(response.context['depenses_mois'], 0)


class DepenseCrudTests(ComptabiliteTestCaseBase):

    def test_creation_depense(self):
        response = self.client.post(reverse('cabinet:depense_create'), {
            'categorie': 'materiel',
            'montant': '150.50',
            'date_depense': '2026-09-01',
            'description': 'Chaises de bureau',
        })
        self.assertRedirects(response, reverse('cabinet:comptabilite_dashboard'))
        depense = Depense.objects.get(description='Chaises de bureau')
        self.assertEqual(depense.organization, self.organization)
        self.assertEqual(str(depense.montant), '150.50')

    def test_edition_depense(self):
        depense = Depense.objects.create(
            organization=self.organization, categorie='autre', montant=100,
            date_depense='2026-09-01',
        )
        response = self.client.post(reverse('cabinet:depense_edit', args=[depense.id]), {
            'categorie': 'formation',
            'montant': '250',
            'date_depense': '2026-09-05',
            'description': 'Formation TCC',
        })
        self.assertRedirects(response, reverse('cabinet:comptabilite_dashboard'))
        depense.refresh_from_db()
        self.assertEqual(depense.categorie, 'formation')
        self.assertEqual(str(depense.montant), '250.00')

    def test_suppression_depense(self):
        depense = Depense.objects.create(
            organization=self.organization, categorie='autre', montant=100,
            date_depense='2026-09-01',
        )
        response = self.client.post(reverse('cabinet:depense_delete', args=[depense.id]))
        self.assertRedirects(response, reverse('cabinet:comptabilite_dashboard'))
        self.assertFalse(Depense.objects.filter(id=depense.id).exists())


class ComptabiliteExportCsvTests(ComptabiliteTestCaseBase):

    def test_export_contient_revenus_et_depenses(self):
        today = timezone.now()
        Consultation.objects.create(
            organization=self.organization, patient=self.patient, date_seance=today,
            tarif=400, statut_paiement='paye',
        )
        Depense.objects.create(
            organization=self.organization, categorie='loyer', montant=200,
            date_depense=today.date(),
        )

        response = self.client.get(reverse('cabinet:comptabilite_export_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode('utf-8')
        self.assertIn('Dupont', content)
        self.assertIn('Loyer', content)
