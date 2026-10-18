import json
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import License, Organization, User
from bilans import ia
from bilans.models import AppelIA, Bilan, MessageBilan, VersionBilan
from bilans.modeles import PLACEHOLDER_IA
from cabinet.models import Anamnese, Consultation, Patient
from tests_psy.models import TestBeck, TestSTAI


class BilanTestCaseBase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Sérénité", slug="serenite", city="Rabat")
        License.objects.create(organization=self.org, plan='lifetime', status='active',
                               has_bilans=True, has_beck=True, has_stai=True)
        self.psy = User.objects.create_user(username='psy', password='pass-12345', role='psychologist',
                                            organization=self.org, first_name='Manal', last_name='Moussaid')
        self.patient = Patient.objects.create(organization=self.org, nom='Benali', prenom='Yasmine',
                                              date_naissance=date(1990, 5, 2), telephone='0612345678',
                                              email='yasmine@mail.ma')
        # Autre patient du cabinet (sœur) : son prénom ne doit jamais partir vers l'IA
        Patient.objects.create(organization=self.org, nom='Benali', prenom='Salma', date_naissance=date(1995, 1, 1))
        Anamnese.objects.create(organization=self.org, patient=self.patient,
                                motif_consultation="Yasmine consulte pour des angoisses ; sa sœur Salma l'accompagne.")
        Consultation.objects.create(organization=self.org, patient=self.patient, tarif=300,
                                    date_seance=timezone.now() - timedelta(days=7), statut_consultation='termine',
                                    note_subjectif="Se sent mieux depuis deux semaines.")
        self.beck = TestBeck.objects.create(organization=self.org, patient=self.patient, psychologue=self.psy,
                                            score_total=22, niveau_depression='moderee', alerte_suicide=True)
        self.stai = TestSTAI.objects.create(organization=self.org, patient=self.patient, psychologue=self.psy,
                                            score_etat=48, score_trait=57,
                                            niveau_anxiete_etat='moderee', niveau_anxiete_trait='elevee')
        self.client.force_login(self.psy)

    def creer_bilan(self, modele='psy_adulte', **extra):
        data = {'patient': self.patient.id, 'modele': modele, 'anamnese': '1', 'consultations': '1',
                'tests': [f'beck:{self.beck.id}', f'stai:{self.stai.id}'], **extra}
        response = self.client.post(reverse('bilans:nouveau'), data)
        self.assertEqual(response.status_code, 302)
        return Bilan.objects.latest('id')

    def post_json(self, nom, bilan, data, **kwargs):
        return self.client.post(reverse(nom, args=[bilan.id], **kwargs), data=json.dumps(data),
                                content_type='application/json')


class AccesTests(BilanTestCaseBase):

    def test_licence_sans_bilans_redirige(self):
        License.objects.filter(organization=self.org).update(has_bilans=False)
        self.assertRedirects(self.client.get(reverse('bilans:liste')), reverse('cabinet:dashboard'),
                             fetch_redirect_response=False)

    def test_permission_utilisateur_requise(self):
        self.psy.can_access_bilans = False
        self.psy.save()
        self.assertEqual(self.client.get(reverse('bilans:liste')).status_code, 302)

    def test_bilan_d_un_autre_cabinet_introuvable(self):
        bilan = self.creer_bilan()
        autre_org = Organization.objects.create(name="Autre", slug="autre")
        License.objects.create(organization=autre_org, plan='lifetime', status='active', has_bilans=True)
        autre = User.objects.create_user(username='autre', password='pass-12345', role='psychologist',
                                         organization=autre_org)
        self.client.force_login(autre)
        self.assertEqual(self.client.get(reverse('bilans:editeur', args=[bilan.id])).status_code, 404)
        self.assertEqual(self.post_json('bilans:sauvegarder', bilan, {'contenu': '<p>pirate</p>'}).status_code, 404)
        self.assertEqual(self.client.get(reverse('bilans:export', args=[bilan.id, 'pdf'])).status_code, 404)

    def test_superadmin_voit_le_bilan(self):
        bilan = self.creer_bilan()
        admin = User.objects.create_user(username='admin', password='pass-12345', role='superadmin')
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse('bilans:editeur', args=[bilan.id])).status_code, 200)

    def test_sans_acces_consultations_pas_d_anamnese(self):
        self.psy.can_access_consultations = False
        self.psy.save()
        bilan = self.creer_bilan()
        self.assertFalse(bilan.sources['anamnese'])
        self.assertFalse(bilan.sources['consultations'])


class CreationEtEditionTests(BilanTestCaseBase):

    def test_creation_remplit_identite_et_resultats(self):
        bilan = self.creer_bilan()
        self.assertEqual(bilan.organization, self.org)
        self.assertEqual(bilan.titre, "Bilan psychologique")
        self.assertIn('BENALI Yasmine', bilan.contenu)
        self.assertIn('22 / 63', bilan.contenu)
        self.assertIn('ALERTE : item 9', bilan.contenu)
        self.assertIn('48 / 80', bilan.contenu)
        # Un chapitre par test (tableau + interprétation), puis les sections rédigées
        self.assertIn(f'data-section="test_beck_{self.beck.id}" data-type="test"', bilan.contenu)
        self.assertIn('<h3>Interprétation</h3>', bilan.contenu)
        self.assertIn('data-section="synthese" data-type="ia"', bilan.contenu)
        self.assertIn(PLACEHOLDER_IA, bilan.contenu)
        self.assertEqual(bilan.versions.count(), 1)

    def test_tests_d_un_autre_patient_refuses(self):
        autre = Patient.objects.create(organization=self.org, nom='X', prenom='Y', date_naissance=date(2000, 1, 1))
        beck_autre = TestBeck.objects.create(organization=self.org, patient=autre, score_total=50)
        bilan = self.creer_bilan(tests=[f'beck:{beck_autre.id}'])
        self.assertEqual(bilan.sources['tests'], [])

    def test_les_trois_modeles_se_creent(self):
        for modele in ('neuropsy_enfant', 'psy_adulte', 'compte_rendu_suivi'):
            bilan = self.creer_bilan(modele=modele)
            response = self.client.get(reverse('bilans:editeur', args=[bilan.id]))
            self.assertEqual(response.status_code, 200)
        self.assertIn('1 séance(s) réalisée(s)', Bilan.objects.get(modele='compte_rendu_suivi').contenu)

    def test_sauvegarde_nettoie_le_html(self):
        bilan = self.creer_bilan()
        response = self.post_json('bilans:sauvegarder', bilan,
                                  {'contenu': '<p>Texte<script>alert(1)</script></p><img src=x onerror=alert(1)>',
                                   'titre': 'Nouveau titre'})
        self.assertEqual(response.status_code, 200)
        bilan.refresh_from_db()
        self.assertEqual(bilan.contenu, '<p>Texte</p>')
        self.assertEqual(bilan.titre, 'Nouveau titre')

    def test_version_avant_et_restauration(self):
        bilan = self.creer_bilan()
        contenu_initial = bilan.contenu
        self.post_json('bilans:sauvegarder', bilan, {'contenu': '<p>v2</p>', 'version_avant': True})
        version = bilan.versions.first()
        self.assertEqual(version.contenu, contenu_initial)
        response = self.client.post(reverse('bilans:restaurer_version', args=[bilan.id, version.id]))
        self.assertEqual(response.json()['contenu'], contenu_initial)
        self.assertEqual(bilan.versions.first().contenu, '<p>v2</p>')  # rien n'est perdu

    def test_bilan_finalise_non_modifiable(self):
        bilan = self.creer_bilan()
        self.client.post(reverse('bilans:statut', args=[bilan.id]), {'action': 'finaliser'})
        self.assertEqual(self.post_json('bilans:sauvegarder', bilan, {'contenu': '<p>x</p>'}).status_code, 409)
        self.client.post(reverse('bilans:statut', args=[bilan.id]), {'action': 'rouvrir'})
        self.assertEqual(self.post_json('bilans:sauvegarder', bilan, {'contenu': '<p>x</p>'}).status_code, 200)

    def test_exports_word_et_pdf(self):
        bilan = self.creer_bilan()
        self.post_json('bilans:sauvegarder', bilan, {'contenu': bilan.contenu + '<p>Conclusion ≥ test « ok »</p>'})
        docx = self.client.get(reverse('bilans:export', args=[bilan.id, 'docx']))
        self.assertEqual(docx.status_code, 200)
        self.assertTrue(docx.content.startswith(b'PK'))
        pdf = self.client.get(reverse('bilans:export', args=[bilan.id, 'pdf']))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        self.assertEqual(self.client.get(reverse('bilans:export', args=[bilan.id, 'exe'])).status_code, 404)

    def test_suppression(self):
        bilan = self.creer_bilan()
        self.client.post(reverse('bilans:supprimer', args=[bilan.id]))
        self.assertFalse(Bilan.objects.filter(id=bilan.id).exists())

    def test_onglet_bilans_sur_la_fiche_patient(self):
        self.creer_bilan()
        response = self.client.get(reverse('cabinet:patient_detail', args=[self.patient.id]))
        self.assertContains(response, 'id="tab-bilans"')
        self.assertContains(response, 'Bilan psychologique')


def _reponse_ia(contenu):
    return json.dumps(contenu, ensure_ascii=False), 123


@override_settings(IA_API_KEY='cle-test', IA_QUOTA_JOUR_PAR_CABINET=5)
class IATests(BilanTestCaseBase):

    def test_apercu_anonymise(self):
        bilan = self.creer_bilan()
        texte = self.client.get(reverse('bilans:ia_apercu', args=[bilan.id])).json()['texte']
        for interdit in ('Yasmine', 'Benali', 'Salma', 'Manal', 'Moussaid', 'Sérénité', '0612345678',
                         'yasmine@mail.ma'):
            self.assertNotIn(interdit, texte)
        self.assertIn('né(e) le 02/05/1990', texte)  # date de naissance transmise volontairement
        self.assertIn('[PRÉNOM]', texte)
        self.assertIn('22 / 63', texte)
        self.assertIn('Se sent mieux', texte)

    @patch('bilans.ia._appeler')
    def test_premier_jet_remplit_les_sections_ia_et_restaure_les_noms(self, appeler):
        appeler.return_value = _reponse_ia({'sections': {
            'motif': "[PRÉNOM] consulte pour des angoisses.",
            f'test_beck_{self.beck.id}': "Score de Beck modéré.",
            'identite': "L'IA ne doit pas toucher aux données",
        }})
        bilan = self.creer_bilan()
        response = self.post_json('bilans:ia_premier_jet', bilan, {'contenu': bilan.contenu})
        self.assertEqual(response.status_code, 200, response.content)
        # Premier lot : motif, contexte, interprétation du Beck ; il reste STAI, synthèse, recommandations
        self.assertEqual(response.json()['restantes'], 4)
        bilan.refresh_from_db()
        self.assertIn('Yasmine consulte pour des angoisses.', bilan.contenu)
        self.assertIn('<h3>Interprétation</h3>\n<p>Score de Beck modéré.</p>', bilan.contenu)
        self.assertIn('22 / 63', bilan.contenu)  # le tableau calculé reste en place
        self.assertNotIn("L'IA ne doit pas toucher", bilan.contenu)
        self.assertEqual(bilan.versions.first().motif, "Avant rédaction IA")
        envoye = json.dumps(appeler.call_args[0][0], ensure_ascii=False)
        self.assertNotIn('Yasmine', envoye)
        self.assertNotIn('Salma', envoye)
        self.assertTrue(AppelIA.objects.get().succes)

    @patch('bilans.ia._appeler')
    def test_premier_jet_ne_reecrit_pas_une_section_deja_ecrite(self, appeler):
        bilan = self.creer_bilan()
        contenu = bilan.contenu.replace(PLACEHOLDER_IA, "Mon texte à moi", 1)
        appeler.return_value = _reponse_ia({'sections': {'motif': "écrasé", 'contexte': "Contexte IA"}})
        self.post_json('bilans:ia_premier_jet', bilan, {'contenu': contenu})
        bilan.refresh_from_db()
        self.assertIn('Mon texte à moi', bilan.contenu)
        self.assertNotIn('écrasé', bilan.contenu)
        self.assertIn('Contexte IA', bilan.contenu)

    @patch('bilans.ia._appeler')
    def test_reecriture_d_une_section_deja_remplie(self, appeler):
        bilan = self.creer_bilan()
        contenu = bilan.contenu.replace(PLACEHOLDER_IA, "Ancien motif", 1)
        sans_ia = self.post_json('bilans:ia_premier_jet', bilan, {'contenu': contenu.replace(PLACEHOLDER_IA, "rempli")})
        self.assertEqual(sans_ia.status_code, 400)  # tout est rempli : rien à faire sans choix explicite
        self.assertEqual(appeler.call_count, 0)

        appeler.return_value = _reponse_ia({'sections': {'motif': "Nouveau motif", 'contexte': "ignoré"}})
        response = self.post_json('bilans:ia_premier_jet', bilan, {'sections': ['motif', 'inconnue']})
        self.assertEqual(response.json()['remplies'], ["Motif de consultation"])
        bilan.refresh_from_db()
        self.assertIn('Nouveau motif', bilan.contenu)
        self.assertNotIn('Ancien motif', bilan.contenu)
        self.assertNotIn('ignoré', bilan.contenu)
        self.assertEqual(bilan.versions.first().motif, "Avant réécriture IA")
        self.assertIn('"motif"', appeler.call_args[0][0][-1]['content'])
        self.assertNotIn('"contexte"', appeler.call_args[0][0][-1]['content'])

    @patch('bilans.ia._appeler')
    def test_chat_avec_selection(self, appeler):
        appeler.return_value = _reponse_ia({'reponse': "Voici une version plus concise pour [PRÉNOM].",
                                            'proposition': "[PRÉNOM] va mieux."})
        bilan = self.creer_bilan()
        response = self.post_json('bilans:ia_chat', bilan, {'message': "Plus concis pour Yasmine",
                                                            'selection': "Yasmine Benali se sent beaucoup mieux"})
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['proposition'], "Yasmine va mieux.")
        self.assertEqual(data['proposition_html'], "<p>Yasmine va mieux.</p>")
        self.assertIn('Yasmine', data['reponse'])
        envoye = json.dumps(appeler.call_args[0][0], ensure_ascii=False)
        self.assertNotIn('Yasmine', envoye)
        self.assertNotIn('Benali', envoye)
        self.assertEqual(list(MessageBilan.objects.values_list('role', flat=True)), ['psy', 'ia'])
        self.assertEqual(MessageBilan.objects.first().contenu, "Plus concis pour Yasmine")

    @patch('bilans.ia._appeler')
    def test_quota_quotidien(self, appeler):
        appeler.return_value = _reponse_ia({'reponse': 'ok', 'proposition': None})
        bilan = self.creer_bilan()
        for _ in range(5):
            self.assertEqual(self.post_json('bilans:ia_chat', bilan, {'message': 'question'}).status_code, 200)
        response = self.post_json('bilans:ia_chat', bilan, {'message': 'question'})
        self.assertEqual(response.status_code, 502)
        self.assertIn('Quota quotidien', response.json()['erreur'])
        self.assertEqual(appeler.call_count, 5)

    @patch('bilans.ia._appeler', side_effect=ia.IAErreur("Limite de l'offre gratuite de l'IA atteinte"))
    def test_erreur_fournisseur_journalisee(self, _):
        bilan = self.creer_bilan()
        response = self.post_json('bilans:ia_premier_jet', bilan, {})
        self.assertEqual(response.status_code, 502)
        appel = AppelIA.objects.get()
        self.assertFalse(appel.succes)
        self.assertIn('Limite', appel.erreur)

    @override_settings(IA_API_KEY='')
    def test_sans_cle_l_editeur_fonctionne(self):
        bilan = self.creer_bilan()
        response = self.client.get(reverse('bilans:editeur', args=[bilan.id]))
        self.assertContains(response, "pas encore configuré")
        response = self.post_json('bilans:ia_chat', bilan, {'message': 'question'})
        self.assertEqual(response.status_code, 502)

    def test_json_entoure_de_markdown_accepte(self):
        self.assertEqual(ia._json('```json\n{"reponse": "ok"}\n```'), {'reponse': 'ok'})
        with self.assertRaises(ia.IAErreur):
            ia._json('pas du json')
