from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse, HttpResponseForbidden
from django.test import RequestFactory, TestCase
from django.utils import timezone
from datetime import timedelta

from accounts.models import Organization, User, License
from core.middleware import TenantMiddleware, get_current_tenant


def _get_response_ok(request):
    """get_response factice qui capture le tenant actif pendant le traitement."""
    _get_response_ok.tenant_pendant_requete = get_current_tenant()
    return HttpResponse("ok")


class TenantMiddlewareTests(TestCase):
    """
    Vérifie le comportement de sécurité de TenantMiddleware : c'est la
    barrière qui empêche un utilisateur sans organisation ou avec une
    licence expirée d'accéder à l'application.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(_get_response_ok)
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")

    def _request(self, path='/cabinet/dashboard/', user=None):
        request = self.factory.get(path)
        request.user = user or AnonymousUser()
        return request

    def test_utilisateur_anonyme_aucun_tenant(self):
        request = self._request(user=AnonymousUser())
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(request.tenant)
        self.assertIsNone(get_current_tenant())  # nettoyé après la requête

    def test_superadmin_voit_tout_pas_de_filtrage(self):
        superadmin = User.objects.create(username="super", role='superadmin')
        request = self._request(user=superadmin)
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(request.tenant)
        self.assertIsNone(_get_response_ok.tenant_pendant_requete)

    def test_psychologue_sans_organisation_est_bloque(self):
        user = User.objects.create(username="orphelin", role='psychologist', organization=None)
        request = self._request(path='/cabinet/dashboard/', user=user)
        response = self.middleware(request)

        self.assertIsInstance(response, HttpResponseForbidden)

    def test_psychologue_sans_organisation_peut_acceder_a_accounts(self):
        user = User.objects.create(username="orphelin2", role='psychologist', organization=None)
        request = self._request(path='/accounts/login/', user=user)
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_licence_expiree_bloque_lacces(self):
        License.objects.create(
            organization=self.org,
            plan='trial',
            status='active',
            end_date=timezone.now() - timedelta(days=1),
        )
        user = User.objects.create(username="expire", role='psychologist', organization=self.org)
        request = self._request(path='/cabinet/dashboard/', user=user)
        response = self.middleware(request)

        self.assertIsInstance(response, HttpResponseForbidden)

    def test_licence_active_laisse_passer_et_fixe_le_tenant(self):
        License.objects.create(organization=self.org, plan='lifetime', status='active')
        user = User.objects.create(username="actif", role='psychologist', organization=self.org)
        request = self._request(path='/cabinet/dashboard/', user=user)
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.tenant, self.org)
        self.assertEqual(_get_response_ok.tenant_pendant_requete, self.org)
        # Le tenant est nettoyé après la réponse pour ne pas fuiter vers la requête suivante.
        self.assertIsNone(get_current_tenant())

    def test_organisation_sans_licence_ne_bloque_pas(self):
        """Une organisation sans licence associée (edge case) ne doit pas planter le middleware."""
        user = User.objects.create(username="sans_licence", role='psychologist', organization=self.org)
        request = self._request(path='/cabinet/dashboard/', user=user)
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
