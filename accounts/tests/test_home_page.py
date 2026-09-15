from django.test import TestCase
from django.urls import reverse


class HomePageAnonymousAccessTests(TestCase):
    """La page d'accueil ('/') est publique et rend base.html (donc la sidebar) même pour un
    visiteur non connecté. Régression : les filtres de permission utilisés dans la sidebar
    (has_module/has_test) doivent gérer AnonymousUser sans planter."""

    def test_page_accueil_ne_plante_pas_pour_un_visiteur_anonyme(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
