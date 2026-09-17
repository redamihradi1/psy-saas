from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import Organization, License
from cabinet.models import Patient
from tests_psy.models import TestBeck, TestSTAI


class LicenseActivationTests(TestCase):
    """Vérifie is_active() pour les différentes combinaisons plan/statut/date."""

    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")

    def test_licence_lifetime_toujours_active(self):
        license = License.objects.create(organization=self.org, plan='lifetime', status='active')
        self.assertTrue(license.is_active())

    def test_licence_trial_active_si_date_non_depassee(self):
        license = License.objects.create(
            organization=self.org, plan='trial', status='active',
            end_date=timezone.now() + timedelta(days=5),
        )
        self.assertTrue(license.is_active())

    def test_licence_trial_inactive_si_date_depassee(self):
        license = License.objects.create(
            organization=self.org, plan='trial', status='active',
            end_date=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(license.is_active())

    def test_licence_suspendue_inactive_meme_si_lifetime(self):
        license = License.objects.create(organization=self.org, plan='lifetime', status='suspended')
        self.assertFalse(license.is_active())

    def test_licence_trial_sans_date_fin_recoit_30_jours_a_la_creation(self):
        license = License.objects.create(organization=self.org, plan='trial', status='active')
        self.assertIsNotNone(license.end_date)
        self.assertTrue(license.is_active())

    def test_licence_lifetime_efface_la_date_de_fin(self):
        license = License.objects.create(
            organization=self.org, plan='trial', status='active',
            end_date=timezone.now() + timedelta(days=5),
        )
        license.plan = 'lifetime'
        license.save()
        self.assertIsNone(license.end_date)


class LicenseAbonnementTests(TestCase):
    """Formules d'abonnement récurrent (2026-09-17) : cycle initial à la création,
    renouvellement manuel, alerte d'expiration proche."""

    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Abonnement", slug="cabinet-abonnement")

    def test_abonnement_mensuel_recoit_30_jours_a_la_creation(self):
        license = License.objects.create(organization=self.org, plan='abonnement_mensuel', status='active')
        self.assertIsNotNone(license.end_date)
        self.assertAlmostEqual(
            (license.end_date - timezone.now()).days, 30, delta=1
        )

    def test_abonnement_annuel_recoit_365_jours_a_la_creation(self):
        license = License.objects.create(organization=self.org, plan='abonnement_annuel', status='active')
        self.assertAlmostEqual(
            (license.end_date - timezone.now()).days, 365, delta=1
        )

    def test_renouveler_prolonge_a_partir_de_la_date_de_fin_si_pas_encore_expiree(self):
        end_date_initiale = timezone.now() + timedelta(days=5)
        license = License.objects.create(
            organization=self.org, plan='abonnement_mensuel', status='active', end_date=end_date_initiale,
        )
        license.renouveler()
        # Prolongé depuis l'échéance existante (pas depuis aujourd'hui) : pas de jours perdus.
        self.assertAlmostEqual((license.end_date - end_date_initiale).days, 30, delta=1)
        self.assertEqual(license.dernier_paiement_le, timezone.now().date())

    def test_renouveler_repart_d_aujourdhui_si_licence_deja_expiree(self):
        license = License.objects.create(
            organization=self.org, plan='abonnement_mensuel', status='expired',
            end_date=timezone.now() - timedelta(days=10),
        )
        license.renouveler()
        self.assertAlmostEqual((license.end_date - timezone.now()).days, 30, delta=1)
        self.assertEqual(license.status, 'active')

    def test_renouveler_sans_effet_sur_trial_et_lifetime(self):
        license = License.objects.create(organization=self.org, plan='lifetime', status='active')
        license.renouveler()
        self.assertIsNone(license.end_date)

    def test_expire_bientot_detecte_une_echeance_proche(self):
        license = License.objects.create(
            organization=self.org, plan='abonnement_mensuel', status='active',
            end_date=timezone.now() + timedelta(days=3),
        )
        self.assertTrue(license.expire_bientot(jours=7))
        self.assertFalse(license.expire_bientot(jours=1))

    def test_expire_bientot_faux_pour_lifetime(self):
        license = License.objects.create(organization=self.org, plan='lifetime', status='active')
        self.assertFalse(license.expire_bientot())

    def test_expire_bientot_faux_si_licence_deja_inactive(self):
        license = License.objects.create(
            organization=self.org, plan='abonnement_mensuel', status='suspended',
            end_date=timezone.now() + timedelta(days=1),
        )
        self.assertFalse(license.expire_bientot())

    def test_renouveler_journalise_un_paiement(self):
        from accounts.models import PaiementLicence

        license = License.objects.create(
            organization=self.org, plan='abonnement_mensuel', status='active', prix_dhs=299,
        )
        license.renouveler()
        self.assertEqual(PaiementLicence.objects.filter(license=license).count(), 1)
        paiement = PaiementLicence.objects.get(license=license)
        self.assertEqual(paiement.montant, 299)
        self.assertEqual(paiement.plan, 'abonnement_mensuel')
        self.assertEqual(paiement.date_paiement, timezone.now().date())

    def test_renouveler_plusieurs_fois_accumule_l_historique(self):
        from accounts.models import PaiementLicence

        license = License.objects.create(organization=self.org, plan='abonnement_mensuel', status='active')
        license.renouveler()
        license.renouveler()
        self.assertEqual(PaiementLicence.objects.filter(license=license).count(), 2)

    def test_renouveler_sans_effet_ne_journalise_rien_pour_lifetime(self):
        from accounts.models import PaiementLicence

        license = License.objects.create(organization=self.org, plan='lifetime', status='active')
        license.renouveler()
        self.assertEqual(PaiementLicence.objects.filter(license=license).count(), 0)


class LicensePatientQuotaTests(TestCase):
    """Vérifie le quota de patients par organisation."""

    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        self.license = License.objects.create(
            organization=self.org, plan='lifetime', status='active', max_patients=2
        )

    def test_peut_ajouter_patient_sous_le_quota(self):
        self.assertTrue(self.license.can_add_patient())
        self.assertEqual(self.license.get_patients_remaining(), 2)

    def test_ne_peut_plus_ajouter_patient_au_dela_du_quota(self):
        Patient.objects.create(organization=self.org, nom="A", prenom="A", date_naissance="1990-01-01")
        Patient.objects.create(organization=self.org, nom="B", prenom="B", date_naissance="1990-01-01")

        self.assertFalse(self.license.can_add_patient())
        self.assertEqual(self.license.get_patients_remaining(), 0)

    def test_quota_patients_isole_par_organisation(self):
        """Les patients d'une autre organisation ne doivent pas compter dans le quota."""
        autre_org = Organization.objects.create(name="Autre Cabinet", slug="autre-cabinet")
        Patient.objects.create(organization=autre_org, nom="X", prenom="X", date_naissance="1990-01-01")

        self.assertTrue(self.license.can_add_patient())
        self.assertEqual(self.license.get_patients_remaining(), 2)


class LicenseTestAccessTests(TestCase):
    """Vérifie has_test_access() : dépend à la fois du flag has_<test> et de is_active()."""

    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")

    def test_acces_autorise_si_flag_actif_et_licence_active(self):
        license = License.objects.create(
            organization=self.org, plan='lifetime', status='active', has_beck=True
        )
        self.assertTrue(license.has_test_access('beck'))
        self.assertTrue(license.has_test_access('BECK'))  # insensible à la casse

    def test_acces_refuse_si_flag_inactif(self):
        license = License.objects.create(organization=self.org, plan='lifetime', status='active', has_beck=False)
        self.assertFalse(license.has_test_access('beck'))

    def test_acces_refuse_si_licence_inactive_meme_avec_le_flag(self):
        license = License.objects.create(
            organization=self.org, plan='lifetime', status='suspended', has_beck=True
        )
        self.assertFalse(license.has_test_access('beck'))

    def test_test_inconnu_retourne_false(self):
        license = License.objects.create(organization=self.org, plan='lifetime', status='active')
        self.assertFalse(license.has_test_access('test_qui_nexiste_pas'))


class LicenseTestQuotaTests(TestCase):
    """Vérifie can_add_test() / get_tests_remaining() : quota par test, 0 = illimité."""

    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")

    def _passer_test_beck(self, patient):
        return TestBeck.objects.create(organization=self.org, patient=patient)

    def test_max_zero_est_illimite(self):
        license = License.objects.create(
            organization=self.org, plan='lifetime', status='active', has_beck=True, max_tests_beck=0
        )
        self.assertTrue(license.can_add_test('beck'))
        self.assertEqual(license.get_tests_remaining('beck'), 'Illimité')

    def test_quota_atteint_bloque_nouveau_test(self):
        license = License.objects.create(
            organization=self.org, plan='lifetime', status='active', has_beck=True, max_tests_beck=1
        )
        patient = Patient.objects.create(
            organization=self.org, nom="A", prenom="A", date_naissance="1990-01-01"
        )
        self.assertTrue(license.can_add_test('beck'))

        self._passer_test_beck(patient)

        self.assertFalse(license.can_add_test('beck'))
        self.assertEqual(license.get_tests_remaining('beck'), 0)

    def test_sans_acces_au_test_can_add_test_est_false(self):
        license = License.objects.create(
            organization=self.org, plan='lifetime', status='active', has_beck=False, max_tests_beck=5
        )
        self.assertFalse(license.can_add_test('beck'))

    def test_quota_dun_test_nest_pas_affecte_par_un_autre_test(self):
        license = License.objects.create(
            organization=self.org, plan='lifetime', status='active',
            has_beck=True, max_tests_beck=1,
            has_stai=True, max_tests_stai=1,
        )
        patient = Patient.objects.create(
            organization=self.org, nom="A", prenom="A", date_naissance="1990-01-01"
        )
        TestSTAI.objects.create(organization=self.org, patient=patient)

        # Le quota STAI est atteint mais celui de Beck doit rester intact.
        self.assertFalse(license.can_add_test('stai'))
        self.assertTrue(license.can_add_test('beck'))


class LicenseAvailableTestsTests(TestCase):
    """Vérifie get_available_tests() / get_missing_tests()."""

    def test_listes_disponibles_et_manquantes_sont_completes_et_disjointes(self):
        org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        license = License.objects.create(
            organization=org, plan='lifetime', status='active', has_beck=True, has_stai=True
        )

        disponibles = set(license.get_available_tests())
        manquants = set(license.get_missing_tests())

        self.assertEqual(disponibles, {'Beck', 'STAI'})
        self.assertEqual(manquants, {'D2R', 'Vineland', 'PEP3'})
        self.assertEqual(disponibles & manquants, set())
