from django.test import TestCase
from django.urls import reverse

from accounts.models import User, Organization, License


class AuthViewsTestCaseBase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.org, plan='lifetime', status='active')
        self.user = User.objects.create_user(
            username='psy1', password='motdepasse123', organization=self.org,
        )


class LoginViewTests(AuthViewsTestCaseBase):

    def test_get_affiche_le_formulaire(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)

    def test_deja_authentifie_redirige_vers_dashboard(self):
        self.client.login(username='psy1', password='motdepasse123')
        response = self.client.get(reverse('accounts:login'))
        self.assertRedirects(response, reverse('cabinet:dashboard'))

    def test_identifiants_valides_connecte_et_redirige(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'psy1', 'password': 'motdepasse123',
        })
        self.assertRedirects(response, reverse('cabinet:dashboard'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_identifiants_invalides_naffiche_aucune_redirection(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'psy1', 'password': 'mauvais',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class LogoutViewTests(AuthViewsTestCaseBase):

    def test_logout_deconnecte_et_redirige_vers_login(self):
        self.client.login(username='psy1', password='motdepasse123')
        response = self.client.get(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('accounts:login'))


class ProfileViewTests(AuthViewsTestCaseBase):

    def test_necessite_authentification(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_utilisateur_authentifie_accede_a_la_page(self):
        self.client.login(username='psy1', password='motdepasse123')
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)


class SettingsViewTests(AuthViewsTestCaseBase):

    def test_necessite_authentification(self):
        response = self.client.get(reverse('accounts:settings'))
        self.assertEqual(response.status_code, 302)

    def test_mise_a_jour_du_profil(self):
        self.client.login(username='psy1', password='motdepasse123')
        response = self.client.post(reverse('accounts:settings'), {
            'update_profile': '1',
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'email': 'jean.dupont@example.com',
            'phone': '0600000000',
            'license_number': 'PSY-123',
        })
        self.assertRedirects(response, reverse('accounts:settings'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Jean')
        self.assertEqual(self.user.email, 'jean.dupont@example.com')

    def test_changement_mot_de_passe_valide(self):
        self.client.login(username='psy1', password='motdepasse123')
        response = self.client.post(reverse('accounts:settings'), {
            'change_password': '1',
            'old_password': 'motdepasse123',
            'new_password1': 'nouveaumotdepasse456',
            'new_password2': 'nouveaumotdepasse456',
        })
        self.assertRedirects(response, reverse('accounts:settings'))
        self.assertTrue(self.client.login(username='psy1', password='nouveaumotdepasse456'))

    def test_changement_mot_de_passe_invalide_naffiche_pas_derreur_500(self):
        self.client.login(username='psy1', password='motdepasse123')
        response = self.client.post(reverse('accounts:settings'), {
            'change_password': '1',
            'old_password': 'mauvais_ancien',
            'new_password1': 'nouveaumotdepasse456',
            'new_password2': 'nouveaumotdepasse456',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.login(username='psy1', password='motdepasse123'))
