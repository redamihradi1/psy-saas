from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, License, User


class ModulePermissionTests(TestCase):
    """Vérifie que can_access_<module> restreint bien l'accès d'un(e) assistant(e).

    Le psychologue (titulaire du cabinet) n'est jamais restreint par ces flags - seul un
    compte assistant(e) (créé par le super admin, voir accounts/tests/test_platform_admin_views.py)
    peut l'être.
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(
            organization=self.org, plan='lifetime', status='active',
            has_vineland=True, has_beck=True, has_stai=True, has_d2r=True,
        )

    def _make_assistant(self, **permissions):
        return User.objects.create_user(
            username='assist', password='motdepasse123', role='assistant',
            organization=self.org, **permissions,
        )

    def test_sans_acces_patients_redirige_vers_dashboard(self):
        user = self._make_assistant(can_access_patients=False)
        self.client.force_login(user)
        response = self.client.get(reverse('cabinet:patients_list'))
        self.assertRedirects(response, reverse('cabinet:dashboard'))

    def test_avec_acces_patients_ok(self):
        user = self._make_assistant(can_access_patients=True)
        self.client.force_login(user)
        response = self.client.get(reverse('cabinet:patients_list'))
        self.assertEqual(response.status_code, 200)

    def test_sans_acces_agenda_redirige(self):
        user = self._make_assistant(can_access_agenda=False)
        self.client.force_login(user)
        response = self.client.get(reverse('cabinet:agenda'))
        self.assertRedirects(response, reverse('cabinet:dashboard'))

    def test_sans_acces_comptabilite_redirige(self):
        user = self._make_assistant(can_access_comptabilite=False)
        self.client.force_login(user)
        response = self.client.get(reverse('cabinet:comptabilite_dashboard'))
        self.assertRedirects(response, reverse('cabinet:dashboard'))

    def test_sans_acces_consultations_redirige(self):
        user = self._make_assistant(can_access_consultations=False)
        self.client.force_login(user)
        response = self.client.get(reverse('cabinet:consultations_list'))
        self.assertRedirects(response, reverse('cabinet:dashboard'))

    def test_sans_acces_tags_redirige(self):
        user = self._make_assistant(can_access_tags=False)
        self.client.force_login(user)
        response = self.client.get(reverse('cabinet:tags_list'))
        self.assertRedirects(response, reverse('cabinet:dashboard'))

    def test_superadmin_bypass_toutes_les_restrictions(self):
        superadmin = User.objects.create_user(
            username='admin_super', password='motdepasse123', role='superadmin',
        )
        self.client.force_login(superadmin)
        response = self.client.get(reverse('cabinet:patients_list'))
        self.assertEqual(response.status_code, 200)

    def test_psychologue_restreint_par_les_memes_flags_que_lassistant(self):
        """Le psychologue titulaire est soumis aux mêmes can_access_* qu'un(e) assistant(e) -
        c'est le super admin qui règle ses accès à la création/édition du cabinet (voir
        accounts/forms.py::ClientCreateForm, par défaut : Patients uniquement)."""
        psychologue = User.objects.create_user(
            username='psy', password='motdepasse123', role='psychologist', organization=self.org,
            can_access_patients=True, can_access_agenda=False, can_access_comptabilite=False,
        )
        self.client.force_login(psychologue)

        response = self.client.get(reverse('cabinet:patients_list'))
        self.assertEqual(response.status_code, 200)

        for url_name in ('cabinet:agenda', 'cabinet:comptabilite_dashboard'):
            response = self.client.get(reverse(url_name))
            self.assertRedirects(response, reverse('cabinet:dashboard'), msg_prefix=f"{url_name} devrait être bloqué")


class TestPermissionTests(TestCase):
    """Vérifie que can_access_<test> bloque l'accès d'un(e) assistant(e) même si la licence
    de l'organisation autorise le test (le psychologue, lui, n'est jamais restreint)."""

    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(
            organization=self.org, plan='lifetime', status='active',
            has_vineland=True,
        )

    def test_licence_ok_mais_assistant_restreint_redirige(self):
        user = User.objects.create_user(
            username='assist', password='motdepasse123', role='assistant',
            organization=self.org, can_access_vineland=False,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('tests_psy:vineland_liste'))
        self.assertRedirects(response, reverse('cabinet:dashboard'))

    def test_licence_ok_et_assistant_autorise(self):
        user = User.objects.create_user(
            username='assist', password='motdepasse123', role='assistant',
            organization=self.org, can_access_vineland=True,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('tests_psy:vineland_liste'))
        self.assertEqual(response.status_code, 200)

    def test_licence_non_activee_redirige_meme_pour_le_psychologue(self):
        """Le flag utilisateur ne remplace jamais la licence de l'organisation, même pour le titulaire."""
        user = User.objects.create_user(
            username='psy', password='motdepasse123', role='psychologist', organization=self.org,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('tests_psy:beck_liste'))
        self.assertRedirects(response, reverse('cabinet:dashboard'))


class GlobalSearchPermissionTests(TestCase):

    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.org, plan='lifetime', status='active')

    def test_recherche_exclut_les_patients_pour_assistant_sans_acces_au_module(self):
        from datetime import date
        from cabinet.models import Patient

        Patient.objects.create(
            organization=self.org, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1),
        )
        user = User.objects.create_user(
            username='assist', password='motdepasse123', role='assistant',
            organization=self.org, can_access_patients=False,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('cabinet:global_search'), {'q': 'dupont'})
        self.assertEqual(response.json()['patients'], [])
