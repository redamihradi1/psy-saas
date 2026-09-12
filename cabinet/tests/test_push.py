import json
from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Organization, License, User
from cabinet.models import Patient, Consultation, PushSubscription, RappelEnvoye
from cabinet.push_utils import envoyer_rappels_consultations_proches
from core.middleware import set_current_tenant


class PushViewsTestCaseBase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.organization, plan='lifetime', status='active')
        self.user = User.objects.create_user(
            username="psy", password="test-pass-123", role='psychologist', organization=self.organization,
        )
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1)
        )
        self.client.force_login(self.user)


class PushSubscribeTests(PushViewsTestCaseBase):

    def test_subscribe_cree_un_abonnement(self):
        payload = {
            'endpoint': 'https://fcm.googleapis.com/fake/endpoint/abc',
            'keys': {'p256dh': 'clefp256dh', 'auth': 'clefauth'},
        }
        response = self.client.post(
            reverse('cabinet:push_subscribe'), data=json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PushSubscription.objects.filter(user=self.user, endpoint=payload['endpoint']).exists())

    def test_subscribe_refuse_payload_invalide(self):
        response = self.client.post(
            reverse('cabinet:push_subscribe'), data=json.dumps({'endpoint': 'x'}), content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_subscribe_necessite_connexion(self):
        self.client.logout()
        response = self.client.post(reverse('cabinet:push_subscribe'), data='{}', content_type='application/json')
        self.assertNotEqual(response.status_code, 200)

    def test_unsubscribe_supprime_labonnement(self):
        sub = PushSubscription.objects.create(
            user=self.user, endpoint='https://fcm.googleapis.com/fake/endpoint/abc',
            p256dh='clefp256dh', auth='clefauth',
        )
        response = self.client.post(
            reverse('cabinet:push_unsubscribe'),
            data=json.dumps({'endpoint': sub.endpoint}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PushSubscription.objects.filter(id=sub.id).exists())

    def test_unsubscribe_ne_supprime_pas_labonnement_dun_autre_utilisateur(self):
        autre_user = User.objects.create_user(
            username="autre", password="test-pass-123", role='psychologist', organization=self.organization,
        )
        sub = PushSubscription.objects.create(
            user=autre_user, endpoint='https://fcm.googleapis.com/fake/endpoint/xyz',
            p256dh='clefp256dh', auth='clefauth',
        )
        self.client.post(
            reverse('cabinet:push_unsubscribe'),
            data=json.dumps({'endpoint': sub.endpoint}),
            content_type='application/json',
        )
        self.assertTrue(PushSubscription.objects.filter(id=sub.id).exists())


@override_settings(CRON_SECRET_TOKEN='secret-de-test')
class PushCronTriggerTests(TestCase):
    def test_refuse_mauvais_jeton(self):
        response = self.client.get(reverse('cabinet:push_cron_trigger', args=['mauvais-jeton']))
        self.assertEqual(response.status_code, 403)

    def test_accepte_bon_jeton(self):
        response = self.client.get(reverse('cabinet:push_cron_trigger', args=['secret-de-test']))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])


@override_settings(VAPID_PRIVATE_KEY='fake-private-key', VAPID_ADMIN_EMAIL='test@example.com')
class EnvoyerRappelsTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.organization, plan='lifetime', status='active')
        self.user = User.objects.create_user(
            username="psy", password="test-pass-123", role='psychologist', organization=self.organization,
        )
        set_current_tenant(self.organization)
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1)
        )
        self.subscription = PushSubscription.objects.create(
            user=self.user, endpoint='https://fcm.googleapis.com/fake/endpoint/abc',
            p256dh='clefp256dh', auth='clefauth',
        )

    def tearDown(self):
        set_current_tenant(None)

    def _creer_consultation(self, minutes_avant_debut, statut='planifie'):
        return Consultation.objects.create(
            organization=self.organization,
            patient=self.patient,
            date_seance=timezone.now() + timezone.timedelta(minutes=minutes_avant_debut),
            tarif=300,
            statut_consultation=statut,
        )

    @patch('cabinet.push_utils.webpush')
    def test_envoie_pour_consultation_dans_environ_1h(self, mock_webpush):
        self._creer_consultation(60)
        nb = envoyer_rappels_consultations_proches()
        self.assertEqual(nb, 1)
        mock_webpush.assert_called_once()

    @patch('cabinet.push_utils.webpush')
    def test_ignore_consultation_trop_loin_dans_le_temps(self, mock_webpush):
        self._creer_consultation(180)
        nb = envoyer_rappels_consultations_proches()
        self.assertEqual(nb, 0)
        mock_webpush.assert_not_called()

    @patch('cabinet.push_utils.webpush')
    def test_ignore_consultation_annulee(self, mock_webpush):
        self._creer_consultation(60, statut='annule')
        nb = envoyer_rappels_consultations_proches()
        self.assertEqual(nb, 0)
        mock_webpush.assert_not_called()

    @patch('cabinet.push_utils.webpush')
    def test_idempotent_ne_renvoie_pas_deux_fois(self, mock_webpush):
        consultation = self._creer_consultation(60)
        envoyer_rappels_consultations_proches()
        envoyer_rappels_consultations_proches()
        self.assertEqual(mock_webpush.call_count, 1)
        self.assertEqual(
            RappelEnvoye.objects.filter(consultation=consultation, type_rappel='1h_avant').count(), 1
        )

    @patch('cabinet.push_utils.webpush')
    def test_sans_abonnement_aucun_envoi(self, mock_webpush):
        self.subscription.delete()
        self._creer_consultation(60)
        nb = envoyer_rappels_consultations_proches()
        self.assertEqual(nb, 0)
        mock_webpush.assert_not_called()

    @override_settings(VAPID_PRIVATE_KEY='')
    @patch('cabinet.push_utils.webpush')
    def test_desactive_sans_cle_vapid(self, mock_webpush):
        self._creer_consultation(60)
        nb = envoyer_rappels_consultations_proches()
        self.assertEqual(nb, 0)
        mock_webpush.assert_not_called()
