from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, License, User
from cabinet.models import PackMindOffice


class PackTestCaseBase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.organization, plan='lifetime', status='active')
        self.user = User.objects.create_user(
            username="psy", password="test-pass-123", role='psychologist', organization=self.organization
        )
        self.client.force_login(self.user)


class PackCreateTests(PackTestCaseBase):

    def test_creation_reussie(self):
        response = self.client.post(reverse('cabinet:pack_create'), {
            'nom_pack': 'Pack 10 séances', 'nombre_seances_total': 10,
            'date_achat': '2024-01-01', 'prix_pack': '1000', 'statut': 'actif',
        })

        pack = PackMindOffice.objects.get(nom_pack='Pack 10 séances')
        self.assertRedirects(response, reverse('cabinet:pack_detail', kwargs={'pack_id': pack.id}))
        self.assertEqual(pack.organization, self.organization)
        self.assertEqual(pack.nombre_seances_utilisees, 0)


class PackListTests(PackTestCaseBase):

    def test_isolation_multi_tenant(self):
        PackMindOffice.objects.create(
            organization=self.organization, nom_pack="Pack A", nombre_seances_total=10,
            date_achat=date.today(), prix_pack=1000,
        )
        autre_org = Organization.objects.create(name="Autre Cabinet", slug="autre-cabinet")
        PackMindOffice.objects.create(
            organization=autre_org, nom_pack="Pack B", nombre_seances_total=10,
            date_achat=date.today(), prix_pack=1000,
        )

        response = self.client.get(reverse('cabinet:packs_list'))

        noms = [p.nom_pack for p in response.context['packs']]
        self.assertEqual(noms, ["Pack A"])

    def test_statistiques_agregees(self):
        PackMindOffice.objects.create(
            organization=self.organization, nom_pack="Pack A", nombre_seances_total=10,
            nombre_seances_utilisees=4, date_achat=date.today(), prix_pack=1000, statut='actif',
        )
        PackMindOffice.objects.create(
            organization=self.organization, nom_pack="Pack B", nombre_seances_total=5,
            nombre_seances_utilisees=5, date_achat=date.today(), prix_pack=500, statut='expire',
        )

        response = self.client.get(reverse('cabinet:packs_list'))

        self.assertEqual(response.context['total_packs'], 2)
        self.assertEqual(response.context['packs_actifs'], 1)
        self.assertEqual(response.context['seances_totales_restantes'], 6)  # (10-4) + (5-5)
        self.assertEqual(response.context['chiffre_affaires_packs'], 1500)


class PackEditDeleteTests(PackTestCaseBase):

    def setUp(self):
        super().setUp()
        self.pack = PackMindOffice.objects.create(
            organization=self.organization, nom_pack="Pack A", nombre_seances_total=10,
            date_achat=date.today(), prix_pack=1000,
        )

    def test_edition(self):
        response = self.client.post(reverse('cabinet:pack_edit', kwargs={'pack_id': self.pack.id}), {
            'nom_pack': 'Pack A modifié', 'nombre_seances_total': 12,
            'date_achat': '2024-01-01', 'prix_pack': '1200', 'statut': 'actif',
        })

        self.pack.refresh_from_db()
        self.assertRedirects(response, reverse('cabinet:pack_detail', kwargs={'pack_id': self.pack.id}))
        self.assertEqual(self.pack.nom_pack, 'Pack A modifié')
        self.assertEqual(self.pack.nombre_seances_total, 12)

    def test_suppression(self):
        response = self.client.post(reverse('cabinet:pack_delete', kwargs={'pack_id': self.pack.id}))

        self.assertRedirects(response, reverse('cabinet:packs_list'))
        self.assertFalse(PackMindOffice.objects.filter(id=self.pack.id).exists())

    def test_get_ne_supprime_pas(self):
        """
        Régression : la vue supprimait le pack sur N'IMPORTE QUELLE méthode
        (le bouton faisait un simple window.location.href, sans CSRF ni
        confirmation serveur). Un GET ne doit plus rien supprimer.
        """
        response = self.client.get(reverse('cabinet:pack_delete', kwargs={'pack_id': self.pack.id}))

        self.assertTrue(PackMindOffice.objects.filter(id=self.pack.id).exists())
