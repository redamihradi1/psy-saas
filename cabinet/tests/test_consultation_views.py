from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Organization, License, User
from cabinet.models import Patient, Consultation, PackMindOffice


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

    def test_creation_deduit_une_seance_du_pack_utilise(self):
        pack = PackMindOffice.objects.create(
            organization=self.organization, nombre_seances_total=10, nombre_seances_utilisees=2,
            date_achat=date.today(), prix_pack=1000,
        )

        response = self.client.post(reverse('cabinet:consultation_create'), {
            'patient': self.patient.id,
            'date_seance': '2024-06-15T10:00',
            'duree_minutes': 60,
            'type_consultation': 'individuelle',
            'lieu_consultation': 'visio',
            'pack_mind_office_utilise': pack.id,
            'tarif': '0',
            'statut_paiement': 'attente',
        })

        pack.refresh_from_db()
        consultation = Consultation.objects.get(patient=self.patient)
        self.assertRedirects(response, reverse('cabinet:consultation_detail', kwargs={'consultation_id': consultation.id}))
        self.assertEqual(pack.nombre_seances_utilisees, 3)

    def test_creation_sans_pack_ne_touche_a_aucun_pack(self):
        pack = PackMindOffice.objects.create(
            organization=self.organization, nombre_seances_total=10, nombre_seances_utilisees=2,
            date_achat=date.today(), prix_pack=1000,
        )

        self.client.post(reverse('cabinet:consultation_create'), {
            'patient': self.patient.id,
            'date_seance': '2024-06-15T10:00',
            'duree_minutes': 60,
            'type_consultation': 'individuelle',
            'lieu_consultation': 'visio',
            'tarif': '400',
            'statut_paiement': 'attente',
        })

        pack.refresh_from_db()
        self.assertEqual(pack.nombre_seances_utilisees, 2)


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
    consultation.est_annule. Vérifie aussi le remboursement de séance de pack.
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

    def test_annulation_rembourse_la_seance_au_pack(self):
        pack = PackMindOffice.objects.create(
            organization=self.organization, nombre_seances_total=10, nombre_seances_utilisees=3,
            date_achat=date.today(), prix_pack=1000,
        )
        self.consultation.pack_mind_office_utilise = pack
        self.consultation.save()

        self.client.post(
            reverse('cabinet:consultation_annuler', kwargs={'consultation_id': self.consultation.id}),
            {'motif_annulation': ''},
        )

        pack.refresh_from_db()
        self.assertEqual(pack.nombre_seances_utilisees, 2)


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
