from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, User


class HomePageAnonymousAccessTests(TestCase):
    """La page d'accueil ('/') est publique (template marketing dédié, sans sidebar
    applicative) et doit rester accessible à un visiteur non connecté."""

    def test_page_accueil_ne_plante_pas_pour_un_visiteur_anonyme(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)


class HomePageAuthenticatedRedirectTests(TestCase):
    """Un utilisateur déjà connecté qui visite '/' n'a rien à faire sur la page marketing -
    il doit être renvoyé directement vers son espace (régression : avant ce fix, il voyait la
    page marketing enveloppée dans la sidebar applicative complète)."""

    def test_psychologue_connecte_est_redirige_vers_le_dashboard_cabinet(self):
        organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        user = User.objects.create_user(
            username="psy", password="test-pass-123", role='psychologist', organization=organization
        )
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, reverse('cabinet:dashboard'))

    def test_superadmin_connecte_est_redirige_vers_clients_list(self):
        superadmin = User.objects.create_user(
            username="reda", password="test-pass-123", role='superadmin',
            is_staff=True, is_superuser=True,
        )
        self.client.force_login(superadmin)
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, reverse('accounts:clients_list'))
