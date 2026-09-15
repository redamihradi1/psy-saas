from datetime import timedelta

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from tests_psy.models import Domain, SousDomain, QuestionVineland, TestVineland
from .test_vineland_views import VinelandTestCaseBase


class VinelandLienPublicTests(VinelandTestCaseBase):

    def setUp(self):
        super().setUp()
        domain = Domain.objects.create(name="Communication")
        self.sous_domaine = SousDomain.objects.create(domain=domain, name="Réceptif")
        self.q1 = QuestionVineland.objects.create(sous_domaine=self.sous_domaine, texte="Q1", numero_item=1)
        self.q2 = QuestionVineland.objects.create(sous_domaine=self.sous_domaine, texte="Q2", numero_item=2)
        self.test_vineland = TestVineland.objects.create(
            organization=self.organization, patient=self.patient, psychologue=self.user,
        )
        self.test_vineland.generate_lien_public(duree_jours=7)
        self.anon = Client()

    def _public_url(self):
        return reverse('tests_psy:vineland_public_questionnaire', kwargs={'token': self.test_vineland.lien_token})

    def test_creation_genere_un_token_et_une_expiration(self):
        self.assertIsNotNone(self.test_vineland.lien_token)
        self.assertGreater(self.test_vineland.lien_expire_le, timezone.now())
        self.assertEqual(self.test_vineland.lien_duree_jours, 7)

    def test_lien_accessible_sans_connexion(self):
        response = self.anon.get(self._public_url())
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for route in ('vineland_scores', 'vineland_resultats', 'vineland_comparaisons', 'vineland_pdf'):
            self.assertNotIn(route, content)

    def test_soumission_verrouille_le_lien_et_redirige_vers_merci(self):
        url = self._public_url()
        self.anon.post(url, {
            f'question_{self.sous_domaine.id}_1': '2',
            f'question_{self.sous_domaine.id}_2': '1',
            'action': 'submit',
        })

        self.test_vineland.refresh_from_db()
        self.assertIsNotNone(self.test_vineland.lien_soumis_le)

        merci_url = reverse('tests_psy:vineland_public_merci', kwargs={'token': self.test_vineland.lien_token})
        response = self.anon.get(merci_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for mot_interdit in ('note_standard', 'échelle', 'rang_percentile', 'note_brute'):
            self.assertNotIn(mot_interdit, content)

    def test_relecture_apres_soumission_affiche_deja_soumis(self):
        self.test_vineland.lien_soumis_le = timezone.now()
        self.test_vineland.save()

        response = self.anon.get(self._public_url())
        self.assertContains(response, "déjà été transmises")

    def test_lien_expire_affiche_page_expiration(self):
        self.test_vineland.lien_expire_le = timezone.now() - timedelta(days=1)
        self.test_vineland.save()

        response = self.anon.get(self._public_url())
        self.assertContains(response, "expiré")

    def test_token_invalide_page_calme_404(self):
        response = self.anon.get(reverse('tests_psy:vineland_public_questionnaire', kwargs={'token': 'nimportequoi'}))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "n'est pas valide", status_code=404)

    def test_organisation_inactive_bloque_l_acces(self):
        self.organization.is_active = False
        self.organization.save()

        response = self.anon.get(self._public_url())
        self.assertEqual(response.status_code, 404)

    def test_licence_inactive_bloque_l_acces(self):
        self.organization.license.status = 'suspended'
        self.organization.license.save()

        response = self.anon.get(self._public_url())
        self.assertEqual(response.status_code, 404)

    def test_reouvrir_lien_deverrouille(self):
        self.test_vineland.lien_soumis_le = timezone.now()
        self.test_vineland.save()

        url = reverse('tests_psy:vineland_reouvrir_lien', kwargs={'test_id': self.test_vineland.id})
        self.client.post(url)

        self.test_vineland.refresh_from_db()
        self.assertIsNone(self.test_vineland.lien_soumis_le)

        response = self.anon.get(self._public_url())
        self.assertEqual(response.status_code, 200)

    def test_superadmin_peut_reouvrir_pour_nimporte_quel_cabinet(self):
        superadmin = User.objects.create_user(username='super', password='motdepasse123', role='superadmin')
        self.test_vineland.lien_soumis_le = timezone.now()
        self.test_vineland.save()

        superadmin_client = Client()
        superadmin_client.force_login(superadmin)
        url = reverse('tests_psy:vineland_reouvrir_lien', kwargs={'test_id': self.test_vineland.id})
        superadmin_client.post(url)

        self.test_vineland.refresh_from_db()
        self.assertIsNone(self.test_vineland.lien_soumis_le)
