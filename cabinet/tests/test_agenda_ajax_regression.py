from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Organization, License, User
from cabinet.models import Patient, Consultation


class AgendaAjaxRoutingRegressionTests(TestCase):
    """
    Régression : consultations/create/ et consultations/<id>/edit/ étaient
    enregistrées DEUX FOIS dans cabinet/urls.py -- une fois pour la vue HTML
    classique (consultation_create/consultation_edit) et une fois pour la
    version AJAX (consultation_create_ajax/consultation_edit_ajax) qui
    renvoie du JSON. Django résout toujours la PREMIÈRE entrée déclarée pour
    un chemin donné, donc la version AJAX n'était jamais atteinte : le modal
    du calendrier Agenda (qui poste sur ces chemins et attend du JSON)
    recevait une page HTML et `response.json()` échouait côté client.

    Fix : les endpoints AJAX ont désormais leurs propres chemins
    (create-ajax/, edit-ajax/). Ces tests vérifient que reverse() les résout
    bien vers des chemins distincts et que les vues renvoient du vrai JSON.
    """

    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.organization, plan='lifetime', status='active')
        self.user = User.objects.create_user(
            username="psy", password="test-pass-123", role='psychologist', organization=self.organization
        )
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1)
        )
        self.client.force_login(self.user)

    def test_les_urls_create_html_et_ajax_sont_distinctes(self):
        url_html = reverse('cabinet:consultation_create')
        url_ajax = reverse('cabinet:consultation_create_ajax')
        self.assertNotEqual(url_html, url_ajax)

    def test_les_urls_edit_html_et_ajax_sont_distinctes(self):
        consultation = Consultation.objects.create(
            organization=self.organization, patient=self.patient, date_seance=timezone.now(), tarif=400,
        )
        url_html = reverse('cabinet:consultation_edit', kwargs={'consultation_id': consultation.id})
        url_ajax = reverse('cabinet:consultation_edit_ajax', kwargs={'pk': consultation.id})
        self.assertNotEqual(url_html, url_ajax)

    def test_create_ajax_repond_en_json_et_cree_la_consultation(self):
        url = reverse('cabinet:consultation_create_ajax')
        response = self.client.post(url, {
            'patient': self.patient.id,
            'date': '2024-06-15',
            'heure': '10:00',
            'duree': '60',
            'type_consultation': 'individuelle',
            'statut': 'planifie',
            'notes': 'RAS',
        })

        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(Consultation.objects.filter(id=data['id']).exists())

    def test_edit_ajax_repond_en_json_et_modifie_la_consultation(self):
        consultation = Consultation.objects.create(
            organization=self.organization, patient=self.patient, date_seance=timezone.now(), tarif=400,
        )
        url = reverse('cabinet:consultation_edit_ajax', kwargs={'pk': consultation.id})

        response = self.client.post(url, {
            'date': '2024-07-01', 'heure': '15:30', 'duree': '45',
            'type_consultation': 'suivi', 'statut': 'planifie', 'notes': 'Modifié',
        })

        data = response.json()
        self.assertTrue(data['success'])
        consultation.refresh_from_db()
        self.assertEqual(consultation.notes_cliniques, 'Modifié')
        self.assertEqual(consultation.duree_minutes, 45)

    def test_ancien_chemin_partage_route_toujours_vers_la_vue_html(self):
        """
        Sécurité : un POST direct sur l'ancien chemin partagé continue de
        router vers la vue HTML classique, pas vers l'AJAX -- comportement
        inchangé pour tout code qui dépendait de cette route.
        """
        response = self.client.post('/cabinet/consultations/create/', {})
        self.assertEqual(response['Content-Type'].split(';')[0], 'text/html')
