from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Organization, License, User
from cabinet.models import Patient, Consultation


class ConsultationTestCaseBase(TestCase):
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


class ConsultationCreateTests(ConsultationTestCaseBase):

    def test_creation_redirige_vers_le_detail(self):
        response = self.client.post(reverse('cabinet:consultation_create'), {
            'patient': self.patient.id,
            'date_seance': '2024-06-15T10:00',
            'duree_minutes': 60,
            'type_consultation': 'individuelle',
            'lieu_consultation': 'visio',
            'tarif': '400',
            'statut_paiement': 'attente',
        })

        consultation = Consultation.objects.get(patient=self.patient)
        self.assertRedirects(response, reverse('cabinet:consultation_detail', kwargs={'consultation_id': consultation.id}))
        self.assertEqual(consultation.organization, self.organization)


class ConsultationReporterTests(ConsultationTestCaseBase):
    """
    Régression : la vue mettait 'reportee' au lieu de 'reporte' (valeur du
    modèle), cassant consultation.est_reporte et peut_etre_reporte.
    """

    def setUp(self):
        super().setUp()
        self.consultation = Consultation.objects.create(
            organization=self.organization, patient=self.patient,
            date_seance=timezone.now(), tarif=400,
        )

    def test_report_utilise_la_bonne_valeur_de_statut(self):
        response = self.client.post(
            reverse('cabinet:consultation_reporter', kwargs={'consultation_id': self.consultation.id}),
            {'nouvelle_date': '2024-07-01T14:00:00', 'motif_report': 'Empêchement patient'},
        )

        self.consultation.refresh_from_db()
        self.assertRedirects(
            response, reverse('cabinet:consultation_detail', kwargs={'consultation_id': self.consultation.id})
        )
        self.assertEqual(self.consultation.statut_consultation, 'reporte')
        self.assertTrue(self.consultation.est_reporte)
        self.assertEqual(self.consultation.nombre_reports, 1)

    def test_date_invalide_ne_modifie_rien(self):
        date_avant = self.consultation.date_seance
        response = self.client.post(
            reverse('cabinet:consultation_reporter', kwargs={'consultation_id': self.consultation.id}),
            {'nouvelle_date': 'pas-une-date', 'motif_report': ''},
        )

        self.consultation.refresh_from_db()
        self.assertEqual(self.consultation.date_seance, date_avant)
        self.assertEqual(self.consultation.statut_consultation, 'planifie')


class ConsultationAnnulerTests(ConsultationTestCaseBase):
    """
    Régression : la vue mettait 'annulee' au lieu de 'annule', cassant
    consultation.est_annule.
    """

    def setUp(self):
        super().setUp()
        self.consultation = Consultation.objects.create(
            organization=self.organization, patient=self.patient,
            date_seance=timezone.now(), tarif=400,
        )

    def test_annulation_utilise_la_bonne_valeur_de_statut(self):
        response = self.client.post(
            reverse('cabinet:consultation_annuler', kwargs={'consultation_id': self.consultation.id}),
            {'motif_annulation': 'Patient malade'},
        )

        self.consultation.refresh_from_db()
        self.assertRedirects(
            response, reverse('cabinet:consultation_detail', kwargs={'consultation_id': self.consultation.id})
        )
        self.assertEqual(self.consultation.statut_consultation, 'annule')
        self.assertTrue(self.consultation.est_annule)
        self.assertEqual(self.consultation.motif_report, 'Patient malade')


class ConsultationConfirmerPaiementTests(ConsultationTestCaseBase):

    def test_confirmation_marque_paye_avec_date(self):
        consultation = Consultation.objects.create(
            organization=self.organization, patient=self.patient,
            date_seance=timezone.now(), tarif=400, statut_paiement='attente',
        )

        self.client.post(reverse('cabinet:consultation_confirmer_paiement', kwargs={'consultation_id': consultation.id}))

        consultation.refresh_from_db()
        self.assertEqual(consultation.statut_paiement, 'paye')
        self.assertEqual(consultation.date_paiement, date.today())


class ConsultationDeleteTests(ConsultationTestCaseBase):

    def test_suppression_via_post(self):
        consultation = Consultation.objects.create(
            organization=self.organization, patient=self.patient, date_seance=timezone.now(), tarif=400,
        )

        response = self.client.post(reverse('cabinet:consultation_delete', kwargs={'consultation_id': consultation.id}))

        self.assertRedirects(response, reverse('cabinet:consultations_list'))
        self.assertFalse(Consultation.objects.filter(id=consultation.id).exists())
