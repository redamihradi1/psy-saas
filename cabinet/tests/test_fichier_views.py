import shutil
import tempfile
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Organization, License, User
from cabinet.models import Patient, PatientFichier

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class FichierTestCaseBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

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


class FichierUploadTests(FichierTestCaseBase):

    def test_upload_reussi(self):
        fichier = SimpleUploadedFile("rapport.pdf", b"%PDF-1.4 contenu", content_type="application/pdf")

        response = self.client.post(
            reverse('cabinet:fichier_upload', kwargs={'patient_id': self.patient.id}),
            {
                'fichier': fichier, 'nom_fichier': 'rapport.pdf',
                'categorie': 'test_psychologique', 'description': 'Bilan initial',
            },
        )

        pf = PatientFichier.objects.get(patient=self.patient)
        self.assertRedirects(response, reverse('cabinet:patient_detail', kwargs={'patient_id': self.patient.id}))
        self.assertEqual(pf.organization, self.organization)
        self.assertGreater(pf.taille_fichier, 0)

    def test_extension_non_autorisee_rejetee(self):
        fichier = SimpleUploadedFile("script.exe", b"MZ...", content_type="application/octet-stream")

        self.client.post(
            reverse('cabinet:fichier_upload', kwargs={'patient_id': self.patient.id}),
            {'fichier': fichier, 'nom_fichier': 'script.exe', 'categorie': 'autre'},
        )

        self.assertEqual(PatientFichier.objects.filter(patient=self.patient).count(), 0)


class FichierDeleteTests(FichierTestCaseBase):

    def test_suppression_via_post(self):
        fichier = PatientFichier.objects.create(
            organization=self.organization, patient=self.patient,
            fichier=SimpleUploadedFile("doc.pdf", b"contenu"), nom_fichier="doc.pdf",
        )

        response = self.client.post(
            reverse('cabinet:fichier_delete', kwargs={'patient_id': self.patient.id, 'fichier_id': fichier.id})
        )

        self.assertRedirects(response, reverse('cabinet:patient_detail', kwargs={'patient_id': self.patient.id}))
        self.assertFalse(PatientFichier.objects.filter(id=fichier.id).exists())


class FichierDownloadPreviewTests(FichierTestCaseBase):

    def test_telechargement_pdf(self):
        fichier = PatientFichier.objects.create(
            organization=self.organization, patient=self.patient,
            fichier=SimpleUploadedFile("doc.pdf", b"%PDF-1.4 contenu"), nom_fichier="doc.pdf",
        )

        response = self.client.get(
            reverse('cabinet:fichier_download', kwargs={'patient_id': self.patient.id, 'fichier_id': fichier.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])

    def test_previsualisation_pdf_ne_plante_pas(self):
        """
        Régression : fichier_preview() appelait fichier.est_pdf, qui n'existait
        pas sur le modèle -> AttributeError garantie pour tout PDF prévisualisé.
        """
        fichier = PatientFichier.objects.create(
            organization=self.organization, patient=self.patient,
            fichier=SimpleUploadedFile("doc.pdf", b"%PDF-1.4 contenu"), nom_fichier="doc.pdf",
        )

        response = self.client.get(
            reverse('cabinet:fichier_preview', kwargs={'patient_id': self.patient.id, 'fichier_id': fichier.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('inline', response['Content-Disposition'])

    def test_previsualisation_image_affichage_inline(self):
        fichier = PatientFichier.objects.create(
            organization=self.organization, patient=self.patient,
            fichier=SimpleUploadedFile("scan.jpg", b"\xff\xd8\xff"), nom_fichier="scan.jpg",
        )

        response = self.client.get(
            reverse('cabinet:fichier_preview', kwargs={'patient_id': self.patient.id, 'fichier_id': fichier.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('inline', response['Content-Disposition'])

    def test_previsualisation_document_non_previewable_telecharge(self):
        fichier = PatientFichier.objects.create(
            organization=self.organization, patient=self.patient,
            fichier=SimpleUploadedFile("compte_rendu.docx", b"contenu"), nom_fichier="compte_rendu.docx",
        )

        response = self.client.get(
            reverse('cabinet:fichier_preview', kwargs={'patient_id': self.patient.id, 'fichier_id': fichier.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])

    def test_fichier_dun_autre_patient_est_inaccessible(self):
        autre_patient = Patient.objects.create(
            organization=self.organization, nom="Martin", prenom="Alice", date_naissance=date(1990, 1, 1)
        )
        fichier = PatientFichier.objects.create(
            organization=self.organization, patient=autre_patient,
            fichier=SimpleUploadedFile("doc.pdf", b"contenu"), nom_fichier="doc.pdf",
        )

        response = self.client.get(
            reverse('cabinet:fichier_download', kwargs={'patient_id': self.patient.id, 'fichier_id': fichier.id})
        )

        self.assertEqual(response.status_code, 404)
