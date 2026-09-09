from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from accounts.models import Organization
from cabinet.models import Patient, Consultation, PatientFichier


class PatientAgeTests(TestCase):

    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")

    def _patient(self, date_naissance):
        return Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date_naissance
        )

    def test_age_anniversaire_deja_passe_cette_annee(self):
        today = date.today()
        naissance = date(today.year - 30, 1, 1)  # anniversaire forcément déjà passé
        patient = self._patient(naissance)
        self.assertEqual(patient.age, 30)

    def test_age_anniversaire_pas_encore_atteint_cette_annee(self):
        today = date.today()
        futur = today + timedelta(days=2)
        naissance = date(today.year - 30, futur.month, futur.day)
        patient = self._patient(naissance)
        self.assertEqual(patient.age, 29)  # anniversaire pas encore passé -> 1 an de moins

    def test_nom_complet(self):
        patient = self._patient(date(1990, 1, 1))
        self.assertEqual(patient.nom_complet, "Jean Dupont")


class ConsultationStatusMethodsTests(TestCase):
    """
    Vérifie reporter()/annuler()/marquer_termine() : ce sont les méthodes que
    les vues doivent utiliser plutôt que de dupliquer la logique à la main
    (régression : les vues avaient les fautes de frappe 'reportee'/'annulee'
    au lieu de 'reporte'/'annule', cassant est_reporte/est_annule).
    """

    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1)
        )
        self.consultation = Consultation.objects.create(
            organization=self.organization, patient=self.patient,
            date_seance=timezone.now(), tarif=400,
        )

    def test_reporter_met_a_jour_le_statut_et_la_date(self):
        nouvelle_date = timezone.now() + timedelta(days=7)
        self.consultation.reporter(nouvelle_date, motif="Patient indisponible")

        self.assertEqual(self.consultation.statut_consultation, 'reporte')
        self.assertTrue(self.consultation.est_reporte)
        self.assertEqual(self.consultation.date_seance, nouvelle_date)
        self.assertEqual(self.consultation.nombre_reports, 1)
        self.assertEqual(self.consultation.motif_report, "Patient indisponible")

    def test_reporter_conserve_la_date_originale_au_premier_report(self):
        date_originale = self.consultation.date_seance
        self.consultation.reporter(timezone.now() + timedelta(days=1))

        self.assertEqual(self.consultation.date_seance_originale, date_originale)

    def test_reporter_deux_fois_incremente_le_compteur(self):
        self.consultation.reporter(timezone.now() + timedelta(days=1))
        self.consultation.reporter(timezone.now() + timedelta(days=2))

        self.assertEqual(self.consultation.nombre_reports, 2)
        self.assertEqual(self.consultation.historique_reports, "Reportée 2 fois")

    def test_annuler_met_a_jour_le_statut(self):
        self.consultation.annuler(motif="Empêchement")

        self.assertEqual(self.consultation.statut_consultation, 'annule')
        self.assertTrue(self.consultation.est_annule)
        self.assertEqual(self.consultation.motif_report, "Empêchement")

    def test_marquer_termine(self):
        self.consultation.marquer_termine()
        self.assertEqual(self.consultation.statut_consultation, 'termine')

    def test_peut_etre_reporte_selon_le_statut(self):
        self.assertTrue(self.consultation.peut_etre_reporte)  # planifie
        self.consultation.annuler()
        self.assertFalse(self.consultation.peut_etre_reporte)

    def test_historique_reports_sans_report(self):
        self.assertEqual(self.consultation.historique_reports, "Aucun report")


class PatientFichierPropertiesTests(TestCase):
    """
    Régression : fichier_preview() appelle fichier.est_pdf, qui n'existait pas
    sur le modèle -> AttributeError garanti pour tout PDF prévisualisé.
    """

    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1)
        )

    def _fichier(self, nom_fichier_disque):
        # L'extension est déterminée à partir du FileField (fichier.name),
        # pas du champ nom_fichier -- on doit donc bien attacher un fichier.
        f = PatientFichier(organization=self.organization, patient=self.patient)
        f.fichier = SimpleUploadedFile(nom_fichier_disque, b"contenu")
        return f

    def test_est_pdf_vrai_pour_extension_pdf(self):
        fichier = self._fichier("rapport.pdf")
        self.assertTrue(fichier.est_pdf)
        self.assertFalse(fichier.est_image)

    def test_est_image_vrai_pour_extensions_image(self):
        for ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
            fichier = self._fichier(f"scan.{ext}")
            self.assertTrue(fichier.est_image, f"{ext} devrait être une image")
            self.assertFalse(fichier.est_pdf)

    def test_ni_pdf_ni_image_pour_docx(self):
        fichier = self._fichier("compte_rendu.docx")
        self.assertFalse(fichier.est_pdf)
        self.assertFalse(fichier.est_image)

    def test_taille_lisible_formats(self):
        fichier = self._fichier("x.pdf")
        fichier.taille_fichier = 512
        self.assertEqual(fichier.taille_lisible, "512.0 octets")
        fichier.taille_fichier = 2048
        self.assertEqual(fichier.taille_lisible, "2.0 Ko")

    def test_taille_lisible_inconnue_si_absente(self):
        fichier = self._fichier("x.pdf")
        fichier.taille_fichier = None
        self.assertEqual(fichier.taille_lisible, "Inconnue")
