import json
from datetime import date, datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import License, Organization, User
from cabinet.models import Consultation, Indisponibilite, Patient


def _a(jour, heure, minute=0):
    return timezone.make_aware(datetime.combine(jour, time(heure, minute)))


class CabinetVirtuelTestCase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Sérénité", slug="serenite")
        License.objects.create(organization=self.org, plan='lifetime', status='active')
        self.psy = User.objects.create_user(username='psy', password='pass-12345', role='psychologist',
                                            organization=self.org, first_name='Manal')
        self.yasmine = Patient.objects.create(organization=self.org, nom='Benali', prenom='Yasmine',
                                              date_naissance=date(1990, 5, 2))
        self.yasmine_bis = Patient.objects.create(organization=self.org, nom='Alaoui', prenom='Yasmine',
                                                  date_naissance=date(1992, 1, 1))
        self.client.force_login(self.psy)
        self.demain = timezone.localdate() + timedelta(days=1)

    def seance(self, debut, patient=None, **extra):
        return Consultation.objects.create(organization=self.org, patient=patient or self.yasmine,
                                           date_seance=debut, tarif=300, **extra)

    def post_json(self, nom, data):
        return self.client.post(reverse(nom), data=json.dumps(data), content_type='application/json')


class PageTests(CabinetVirtuelTestCase):

    def test_page_et_pieces(self):
        self.seance(_a(timezone.localdate(), 23, 30))
        response = self.client.get(reverse('cabinet:cabinet_virtuel'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scene"')
        self.assertContains(response, 'Cabinet virtuel')  # lien de la barre latérale
        pieces = response.context['pieces']
        self.assertEqual(pieces['attente']['patients'][0]['graine'], self.yasmine.id)
        self.assertFalse(pieces['attente']['patients'][0]['enfant'])
        self.assertIsNotNone(pieces['accueil'])

    def test_pieces_fermees_sans_permission(self):
        self.psy.can_access_comptabilite = False
        self.psy.can_access_consultations = False
        self.psy.save()
        pieces = self.client.get(reverse('cabinet:cabinet_virtuel')).context['pieces']
        self.assertIsNone(pieces['comptabilite'])
        self.assertIsNone(pieces['accueil'])
        self.assertIsNone(pieces['attente'])
        self.assertEqual(self.client.get(reverse('cabinet:cv_salle_attente')).status_code, 302)
        self.assertEqual(self.post_json('cabinet:cv_creer_consultation', {}).status_code, 302)

    def test_superadmin_redirige(self):
        admin = User.objects.create_user(username='admin', password='pass-12345', role='superadmin')
        self.client.force_login(admin)
        self.assertRedirects(self.client.get(reverse('cabinet:cabinet_virtuel')), reverse('accounts:clients_list'),
                             fetch_redirect_response=False)


class SalleAttenteTests(CabinetVirtuelTestCase):

    def test_consultations_du_jour(self):
        aujourdhui = timezone.localdate()
        self.seance(_a(aujourdhui, 23, 30))
        self.seance(_a(aujourdhui, 23, 45), statut_consultation='annule')
        self.seance(_a(aujourdhui, 23, 50), patient=self.yasmine_bis, statut_consultation='termine')
        self.seance(_a(self.demain, 10))
        data = self.client.get(reverse('cabinet:cv_salle_attente')).json()
        self.assertEqual([c['heure'] for c in data['consultations']], ['23:30', '23:50'])
        self.assertEqual(data['resume']['nb_attente'], 1)
        self.assertEqual(data['resume']['initiales'], ['YB'])


class EncaissementTests(CabinetVirtuelTestCase):

    def test_encaisser_et_isolation(self):
        c = self.seance(_a(timezone.localdate(), 23, 30))
        self.assertEqual(self.client.post(reverse('cabinet:cv_encaisser', args=[c.id])).status_code, 200)
        c.refresh_from_db()
        self.assertEqual((c.statut_paiement, c.date_paiement), ('paye', timezone.localdate()))

        autre_org = Organization.objects.create(name="Autre", slug="autre")
        autre = User.objects.create_user(username='autre', password='pass-12345', role='psychologist',
                                         organization=autre_org)
        License.objects.create(organization=autre_org, plan='lifetime', status='active')
        self.client.force_login(autre)
        self.assertEqual(self.client.post(reverse('cabinet:cv_encaisser', args=[c.id])).status_code, 404)


class AgendaTests(CabinetVirtuelTestCase):

    def test_creneaux_libres_et_indisponibilites(self):
        self.seance(_a(self.demain, 10), duree_minutes=90)
        Indisponibilite.objects.create(organization=self.org, titre='Formation', type_absence='formation',
                                       date_debut=_a(self.demain, 14), date_fin=_a(self.demain, 16))
        jours = self.client.get(reverse('cabinet:cv_agenda'),
                                {'debut': self.demain.isoformat(), 'jours': 1}).json()['jours']
        self.assertEqual(len(jours), 1)
        self.assertEqual(jours[0]['consultations'][0]['fin'], '11:30')
        self.assertEqual(jours[0]['indisponibilites'][0]['titre'], 'Formation')
        self.assertEqual(jours[0]['libres'], ['09:00', '12:00', '13:00', '16:00', '17:00', '18:00'])


class CreationTests(CabinetVirtuelTestCase):

    def donnees(self, **extra):
        return {'patient_id': self.yasmine.id, 'date': self.demain.isoformat(), 'heure': '10:00',
                'duree_minutes': 60, 'type_consultation': 'individuelle', 'lieu_consultation': 'visio',
                'tarif': '350', **extra}

    def test_creation(self):
        response = self.post_json('cabinet:cv_creer_consultation', self.donnees())
        self.assertEqual(response.status_code, 200)
        c = Consultation.objects.get()
        self.assertEqual(timezone.localtime(c.date_seance), _a(self.demain, 10))
        self.assertEqual((c.organization, c.statut_consultation, str(c.tarif)), (self.org, 'planifie', '350.00'))

    def test_conflit_puis_forcer(self):
        self.seance(_a(self.demain, 9, 30))
        response = self.post_json('cabinet:cv_creer_consultation', self.donnees())
        self.assertEqual(response.status_code, 409)
        self.assertIn('09:30', response.json()['erreur'])
        response = self.post_json('cabinet:cv_creer_consultation', self.donnees(forcer=True))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Consultation.objects.count(), 2)

    def test_validation_et_patient_d_un_autre_cabinet(self):
        autre_org = Organization.objects.create(name="Autre", slug="autre")
        etranger = Patient.objects.create(organization=autre_org, nom='X', prenom='Y', date_naissance=date(2000, 1, 1))
        response = self.post_json('cabinet:cv_creer_consultation',
                                  self.donnees(patient_id=etranger.id, heure='25:00', lieu_consultation='lune'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()['erreurs']), {'patient_id', 'date', 'lieu_consultation'})
        self.assertFalse(Consultation.objects.exists())
