from datetime import date, timedelta

from django.test import TestCase

from accounts.models import Organization
from cabinet.forms import PatientForm, ConsultationForm
from cabinet.models import Patient


class PatientFormTests(TestCase):

    def valid_data(self, **overrides):
        data = {
            'nom': 'Dupont',
            'prenom': 'Jean',
            'date_naissance': '1990-01-01',
            'categorie_age': 'adulte',
            'telephone': '0612345678',
            'email': 'jean@example.com',
        }
        data.update(overrides)
        return data

    def test_donnees_valides_acceptees(self):
        form = PatientForm(data=self.valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_date_naissance_future_refusee(self):
        futur = (date.today() + timedelta(days=1)).isoformat()
        form = PatientForm(data=self.valid_data(date_naissance=futur))
        self.assertFalse(form.is_valid())
        self.assertIn('date_naissance', form.errors)

    def test_age_superieur_a_120_ans_refuse(self):
        trop_vieux = date.today().replace(year=date.today().year - 121).isoformat()
        form = PatientForm(data=self.valid_data(date_naissance=trop_vieux))
        self.assertFalse(form.is_valid())
        self.assertIn('date_naissance', form.errors)

    def test_telephone_trop_court_refuse(self):
        form = PatientForm(data=self.valid_data(telephone='123'))
        self.assertFalse(form.is_valid())
        self.assertIn('telephone', form.errors)

    def test_telephone_avec_espaces_et_tirets_nettoye(self):
        form = PatientForm(data=self.valid_data(telephone='06 12-34-56-78'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['telephone'], '0612345678')

    def test_telephone_vide_est_autorise(self):
        form = PatientForm(data=self.valid_data(telephone=''))
        self.assertTrue(form.is_valid(), form.errors)


class ConsultationFormTests(TestCase):

    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        self.patient = Patient.objects.create(
            organization=self.org, nom='Dupont', prenom='Jean',
            date_naissance='1990-01-01',
        )

    def valid_data(self, **overrides):
        data = {
            'patient': self.patient.id,
            'date_seance': '2026-10-01T14:00',
            'duree_minutes': 60,
            'type_consultation': 'individuelle',
            'lieu_consultation': 'visio',
            'tarif': '400.00',
            'statut_paiement': 'attente',
        }
        data.update(overrides)
        return data

    def test_donnees_valides_acceptees(self):
        form = ConsultationForm(data=self.valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_date_paiement_non_requise(self):
        form = ConsultationForm(data=self.valid_data())
        self.assertFalse(form.fields['date_paiement'].required)

    def test_patient_manquant_refuse(self):
        form = ConsultationForm(data=self.valid_data(patient=''))
        self.assertFalse(form.is_valid())
        self.assertIn('patient', form.errors)

    def test_edition_preremplit_date_seance_locale(self):
        from cabinet.models import Consultation
        from django.utils import timezone
        consultation = Consultation.objects.create(
            organization=self.org, patient=self.patient,
            date_seance=timezone.now(), tarif=400,
        )
        form = ConsultationForm(instance=consultation)
        expected = timezone.localtime(consultation.date_seance).strftime('%Y-%m-%dT%H:%M')
        self.assertEqual(form.initial['date_seance'], expected)
