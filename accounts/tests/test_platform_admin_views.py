from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, License, User


class PlatformAdminTestCaseBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='super', password='motdepasse123', role='superadmin',
        )
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        self.license = License.objects.create(
            organization=self.org, plan='lifetime', status='active',
            has_vineland=True, has_beck=True, has_stai=True, has_d2r=True,
        )
        self.psychologue = User.objects.create_user(
            username='psy1', password='motdepasse123', role='psychologist', organization=self.org,
        )


class AccessControlTests(PlatformAdminTestCaseBase):
    """Seul le super admin de la plateforme accède à l'administration (clients, assistants)."""

    def test_superadmin_peut_acceder_aux_clients(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse('accounts:clients_list'))
        self.assertEqual(response.status_code, 200)

    def test_superadmin_peut_acceder_aux_assistants(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse('accounts:assistants_list'))
        self.assertEqual(response.status_code, 200)

    def test_psychologue_ne_peut_pas_gerer_les_clients(self):
        """Même le titulaire d'un cabinet ne peut pas créer un autre cabinet - c'est réservé à la plateforme."""
        self.client.force_login(self.psychologue)
        response = self.client.get(reverse('accounts:clients_list'))
        self.assertRedirects(response, reverse('cabinet:dashboard'))

    def test_psychologue_ne_peut_pas_gerer_les_assistants(self):
        """Les assistant(e)s sont créées par le super admin, jamais par le psychologue lui-même."""
        self.client.force_login(self.psychologue)
        response = self.client.get(reverse('accounts:assistants_list'))
        self.assertRedirects(response, reverse('cabinet:dashboard'))

        response = self.client.post(reverse('accounts:assistant_create'), {
            'psychologue': self.psychologue.id, 'username': 'hacker',
            'password1': 'motdepasse123', 'password2': 'motdepasse123',
        })
        self.assertRedirects(response, reverse('cabinet:dashboard'))
        self.assertFalse(User.objects.filter(username='hacker').exists())

    def test_assistant_ne_peut_rien_gerer(self):
        assistant = User.objects.create_user(
            username='assist', password='motdepasse123', role='assistant', organization=self.org,
        )
        self.client.force_login(assistant)
        response = self.client.get(reverse('accounts:clients_list'))
        self.assertRedirects(response, reverse('cabinet:dashboard'))
        response = self.client.get(reverse('accounts:assistants_list'))
        self.assertRedirects(response, reverse('cabinet:dashboard'))

    def test_non_authentifie_redirige_vers_login(self):
        response = self.client.get(reverse('accounts:clients_list'))
        self.assertNotEqual(response.status_code, 200)


class ClientCreateTests(PlatformAdminTestCaseBase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.superadmin)

    def _post_data(self, **overrides):
        data = {
            'org_name': 'Nouveau Cabinet', 'org_phone': '', 'org_city': '', 'org_address': '',
            'plan': 'trial', 'max_patients': 10,
            'has_vineland': 'on',
            # Case "Patients" pré-cochée par défaut dans le formulaire (voir ClientCreateForm) -
            # un vrai navigateur l'envoie donc dans le POST si le super admin ne la décoche pas.
            'can_access_patients': 'on',
            'username': 'psy_nouveau', 'first_name': 'Jane', 'last_name': 'Doe', 'email': '',
            'phone': '', 'license_number': '',
            'password1': 'motdepasse123', 'password2': 'motdepasse123',
        }
        data.update(overrides)
        return data

    def test_creation_cree_org_licence_et_psychologue(self):
        response = self.client.post(reverse('accounts:client_create'), self._post_data())
        self.assertRedirects(response, reverse('accounts:clients_list'))

        org = Organization.objects.get(name='Nouveau Cabinet')
        self.assertTrue(org.slug)
        self.assertTrue(org.license.is_active())
        self.assertTrue(org.license.has_vineland)
        self.assertFalse(org.license.has_beck)

        psy = User.objects.get(username='psy_nouveau')
        self.assertEqual(psy.role, 'psychologist')
        self.assertEqual(psy.organization, org)
        self.assertTrue(self.client.login(username='psy_nouveau', password='motdepasse123'))

    def test_psychologue_nobtient_que_patients_et_vineland_par_defaut(self):
        """Par défaut à la création : seul Patients est coché parmi les modules, le reste
        (Consultations/Agenda/Comptabilité/Tags/Sauvegarde) doit être coché explicitement.
        Cocher un test sur la licence (Vineland) donne directement accès au psychologue -
        une seule case par test, pas de double confirmation (voir LICENSE_TO_USER_TEST_FIELD)."""
        self.client.post(reverse('accounts:client_create'), self._post_data())
        psy = User.objects.get(username='psy_nouveau')

        self.assertTrue(psy.can_access_patients)
        self.assertFalse(psy.can_access_consultations)
        self.assertFalse(psy.can_access_agenda)
        self.assertFalse(psy.can_access_comptabilite)
        self.assertFalse(psy.can_access_tags)
        self.assertFalse(psy.can_export_backup)
        # has_vineland='on' dans _post_data() règle aussi l'accès utilisateur du psychologue :
        self.assertTrue(psy.can_access_vineland)

        self.client.force_login(psy)
        response = self.client.get(reverse('cabinet:patients_list'))
        self.assertEqual(response.status_code, 200)
        for url_name in ('cabinet:consultations_list', 'cabinet:agenda', 'cabinet:comptabilite_dashboard'):
            response = self.client.get(reverse(url_name))
            self.assertRedirects(response, reverse('cabinet:dashboard'))
        response = self.client.get(reverse('tests_psy:vineland_liste'))
        self.assertEqual(response.status_code, 200)

    def test_nom_de_cabinet_deja_pris_rejete(self):
        response = self.client.post(reverse('accounts:client_create'), self._post_data(org_name='Cabinet Test'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Organization.objects.filter(name='Cabinet Test').count(), 1)

    def test_nom_utilisateur_deja_pris_rejete(self):
        response = self.client.post(reverse('accounts:client_create'), self._post_data(username='psy1'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Organization.objects.filter(name='Nouveau Cabinet').exists())

    def test_mots_de_passe_non_correspondants_rejetes(self):
        response = self.client.post(reverse('accounts:client_create'), self._post_data(password2='autrechose456'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='psy_nouveau').exists())


class ClientEditTests(PlatformAdminTestCaseBase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.superadmin)

    def _post_data(self, **overrides):
        data = {
            'org_name': 'Cabinet Test', 'org_phone': '0600000000', 'org_city': 'Casablanca', 'org_address': '',
            'plan': 'lifetime', 'status': 'active', 'max_patients': 25,
            # Une seule case par test : coché = licence ET accès utilisateur du psychologue.
            'has_vineland': 'on', 'has_beck': 'on',
            'can_access_patients': 'on', 'can_access_consultations': 'on',
        }
        data.update(overrides)
        return data

    def test_get_prefiltre_avec_les_valeurs_actuelles(self):
        response = self.client.get(reverse('accounts:client_edit', args=[self.org.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial['org_name'], 'Cabinet Test')

    def test_modifie_org_licence_et_acces_du_psychologue(self):
        response = self.client.post(reverse('accounts:client_edit', args=[self.org.id]), self._post_data())
        self.assertRedirects(response, reverse('accounts:clients_list'))

        self.org.refresh_from_db()
        self.assertEqual(self.org.phone, '0600000000')
        self.assertEqual(self.org.city, 'Casablanca')

        self.license.refresh_from_db()
        self.assertEqual(self.license.max_patients, 25)
        self.assertTrue(self.license.has_vineland)
        self.assertTrue(self.license.has_beck)
        self.assertFalse(self.license.has_stai)

        self.psychologue.refresh_from_db()
        self.assertTrue(self.psychologue.can_access_patients)
        self.assertTrue(self.psychologue.can_access_consultations)
        self.assertFalse(self.psychologue.can_access_agenda)
        # Dérivés directement de has_vineland/has_beck (une seule case par test) :
        self.assertTrue(self.psychologue.can_access_vineland)
        self.assertTrue(self.psychologue.can_access_beck)
        self.assertFalse(self.psychologue.can_access_stai)

    def test_suspendre_la_licence_bloque_le_psychologue(self):
        self.client.post(reverse('accounts:client_edit', args=[self.org.id]), self._post_data(status='suspended'))
        self.license.refresh_from_db()
        self.assertFalse(self.license.is_active())

        self.client.force_login(self.psychologue)
        response = self.client.get(reverse('cabinet:dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_psychologue_ne_peut_pas_editer_un_cabinet(self):
        self.client.force_login(self.psychologue)
        response = self.client.get(reverse('accounts:client_edit', args=[self.org.id]))
        self.assertRedirects(response, reverse('cabinet:dashboard'))


class AssistantCreateTests(PlatformAdminTestCaseBase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.superadmin)

    def test_creation_attachee_au_bon_cabinet_avec_acces_restreint(self):
        response = self.client.post(reverse('accounts:assistant_create'), {
            'psychologue': self.psychologue.id,
            'username': 'assist1', 'first_name': 'Aya', 'last_name': '', 'email': '',
            'password1': 'motdepasse123', 'password2': 'motdepasse123',
            'can_access_patients': 'on',
            'can_access_vineland': 'on',
        })
        self.assertRedirects(response, reverse('accounts:assistants_list'))

        assistant = User.objects.get(username='assist1')
        self.assertEqual(assistant.role, 'assistant')
        self.assertEqual(assistant.organization, self.org)
        self.assertTrue(assistant.can_access_patients)
        self.assertTrue(assistant.can_access_vineland)
        self.assertFalse(assistant.can_access_consultations)
        self.assertFalse(assistant.can_access_agenda)
        self.assertFalse(assistant.can_access_comptabilite)
        self.assertFalse(assistant.can_access_tags)
        self.assertFalse(assistant.can_access_beck)
        self.assertFalse(assistant.can_export_backup)

        self.assertTrue(self.client.login(username='assist1', password='motdepasse123'))

    def test_deuxieme_cabinet_isolation_du_choix_psychologue(self):
        autre_org = Organization.objects.create(name="Autre Cabinet", slug="autre-cabinet")
        License.objects.create(organization=autre_org, plan='lifetime', status='active')
        autre_psy = User.objects.create_user(
            username='psy2', password='motdepasse123', role='psychologist', organization=autre_org,
        )

        response = self.client.post(reverse('accounts:assistant_create'), {
            'psychologue': autre_psy.id,
            'username': 'assist2',
            'password1': 'motdepasse123', 'password2': 'motdepasse123',
            'can_access_patients': 'on',
        })
        self.assertRedirects(response, reverse('accounts:assistants_list'))
        assistant = User.objects.get(username='assist2')
        self.assertEqual(assistant.organization, autre_org)


class AssistantEditAndActionsTests(PlatformAdminTestCaseBase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.superadmin)
        self.assistant = User.objects.create_user(
            username='assist1', password='motdepasse123', role='assistant', organization=self.org,
            can_access_patients=True,
        )

    def test_modification_des_acces(self):
        response = self.client.post(reverse('accounts:assistant_edit', args=[self.assistant.id]), {
            'first_name': '', 'last_name': '', 'email': '', 'is_active': 'on',
            'can_access_consultations': 'on',
        })
        self.assertRedirects(response, reverse('accounts:assistants_list'))
        self.assistant.refresh_from_db()
        self.assertTrue(self.assistant.can_access_consultations)
        self.assertFalse(self.assistant.can_access_patients)

    def test_toggle_active(self):
        response = self.client.post(reverse('accounts:assistant_toggle_active', args=[self.assistant.id]))
        self.assertRedirects(response, reverse('accounts:assistants_list'))
        self.assistant.refresh_from_db()
        self.assertFalse(self.assistant.is_active)

    def test_reinitialisation_mot_de_passe(self):
        response = self.client.post(reverse('accounts:assistant_reset_password', args=[self.assistant.id]), {
            'password1': 'nouveaumdp789', 'password2': 'nouveaumdp789',
        })
        self.assertRedirects(response, reverse('accounts:assistants_list'))
        self.client.logout()
        self.assertTrue(self.client.login(username='assist1', password='nouveaumdp789'))
