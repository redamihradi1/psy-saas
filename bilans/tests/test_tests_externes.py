"""Tests passés hors plateforme : calculs, saisie, chapitres du document, cohérence, exports,
bibliothèque de textes et en-tête. Données entièrement fictives."""
import io
import json
import shutil
import tempfile
from datetime import date
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import License, Organization, User
from bilans import coherence, donnees, ia
from bilans import tests_externes as te
from bilans.anonymisation import Pseudonymiseur
from bilans.models import Bilan, EnTeteBilan, TexteType
from cabinet.models import Patient

WISC = {'grilles': {
    'indices': {'ICV': {'note': '103', 'percentile': '58', 'ic': '94-114'}, 'IVS': {'note': '94'},
                'IRF': {'note': '67', 'percentile': '1'}, 'IMT': {'note': '97'}, 'IVT': {'note': '66'},
                'QIT': {'note': '82'}},
    'subtests': {'SIM': {'ns': '11'}, 'VOC': {'ns': '10'}, 'CUB': {'ns': '7'}, 'PUZ': {'ns': '11'},
                 'MAT': {'ns': '2'}, 'MCH': {'ns': '12'}, 'MIM': {'ns': '7'}, 'COD': {'ns': '5'}, 'SYM': {'ns': '3'}},
}}


def _png():
    tampon = io.BytesIO()
    Image.new('RGB', (40, 20), 'navy').save(tampon, format='PNG')
    return tampon.getvalue()


class CalculsTests(TestCase):

    def test_wechsler_zones_ecarts_et_points_forts(self):
        res = te.resultats('wisc5', WISC)
        titres = [t[0] for t in res['tableaux']]
        self.assertEqual(titres, ['Indices', 'Comparaisons entre les indices', 'Subtests'])
        indices = {l[0]: l for l in res['tableaux'][0][2]}
        self.assertEqual(indices['Raisonnement fluide (IRF)'][4], 'Très faible')
        self.assertEqual(indices['Compréhension verbale (ICV)'][4], 'Moyenne')
        self.assertTrue(any('QIT est à interpréter avec prudence' in r for r in res['remarques']))
        comparaisons = {l[0]: l for l in res['tableaux'][1][2]}
        self.assertEqual(comparaisons['ICV - IVT'][1:], ['+37', 'ICV > IVT'])
        self.assertEqual(comparaisons['IVS - IMT'][2], 'Écart inférieur à 15 points')
        subtests = {l[1]: l for l in res['tableaux'][2][2]}
        self.assertEqual(subtests['Matrices'][4], 'Point faible relatif')
        self.assertEqual(subtests['Mémoire des chiffres'][4], 'Point fort relatif')
        self.assertEqual(res['figures'], ['wisc5.indices', 'wisc5.subtests'])

    def test_description_saisie_prioritaire(self):
        saisie = {'grilles': {'indices': {'ICV': {'note': '86', 'description': 'Moyenne inférieure'}}}}
        self.assertEqual(te.resultats('wais4', saisie)['tableaux'][0][2][0][4], 'Moyenne inférieure')

    def test_d2r_profil_calcule(self):
        saisie = {'grilles': {'scores': {'CCT': {'ns': '96'}, 'E': {'ns': '102'}, 'CC': {'ns': '97'}}}}
        lignes = te.resultats('d2r_papier', saisie)['tableaux'][0][2]
        self.assertEqual(lignes[-1][:2], ['Profil', 'Réfléchi'])

    def test_tmt_indices_derives(self):
        saisie = {'grilles': {'parties': {'A': {'temps': '34'}, 'B': {'temps': '94', 'erreurs': '0'}}}}
        lignes = {l[0]: l for l in te.resultats('tmt', saisie)['tableaux'][0][2]}
        self.assertEqual(lignes['Indice B - A'][1], '60 s')
        self.assertEqual(lignes['Indice B/A'][1], '2,76')
        self.assertEqual(lignes['TMT-B'][1], '94 s - 0 erreur')

    def test_niveaux_bdi_bai_et_seuils_t(self):
        self.assertEqual(te.zone(12, te.NIVEAUX_BDI), 'Légère')
        self.assertEqual(te.zone(8, te.NIVEAUX_BAI), 'Légère')
        self.assertEqual(te.zone_t_brief('62'), 'Légèrement élevé')
        self.assertEqual(te.zone_t_brief('38'), 'Dans la norme')
        self.assertEqual(te.zone_t_rcads('41'), 'Dans la norme')
        self.assertEqual(te.nombre('4,5'), 4.5)
        self.assertIsNone(te.nombre('<0.1'))

    def test_lecture_du_formulaire(self):
        post = {'tmt__g__parties__A__temps': ' 56 ', 'tmt__g__parties__A__erreurs': '1', 'tmt__c__normes': 'GREFEX',
                'tmt__g__parties__B__temps': ''}
        saisie = te.lire_formulaire('tmt', post)
        self.assertEqual(saisie['grilles'], {'parties': {'A': {'temps': '56', 'erreurs': '1'}}})
        self.assertEqual(saisie['champs'], {'normes': 'GREFEX'})
        libre = te.lire_formulaire('autre_1', {'autre_1__c__nom': 'Figure de Rey', 'autre_1__l__mesures__0__0': 'Copie',
                                               'autre_1__l__mesures__0__1': '18/36'})
        self.assertEqual(libre['libres']['mesures'], [['Copie', '18/36', '']])
        self.assertEqual(te.nom_court('autre_1', libre), 'Figure de Rey')


class BaseBilanExterne(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet Test", slug="cabinet-test", city="Rabat")
        License.objects.create(organization=self.org, plan='lifetime', status='active', has_bilans=True)
        self.psy = User.objects.create_user(username='psy', password='pass-12345', role='psychologist',
                                            organization=self.org, first_name='Nadia', last_name='Alaoui')
        self.patient = Patient.objects.create(organization=self.org, nom='Fictif', prenom='Rayan',
                                              date_naissance=date(2014, 3, 1))
        self.client.force_login(self.psy)

    def creer(self, externes=('wisc5', 'tmt'), **infos):
        data = {'patient': self.patient.id, 'modele': 'neuropsy_enfant', 'externes': list(externes),
                **{f'info_{k}': v for k, v in infos.items()}}
        response = self.client.post(reverse('bilans:nouveau'), data)
        bilan = Bilan.objects.latest('id')
        return bilan, response

    def saisir(self, bilan, post):
        return self.client.post(reverse('bilans:donnees', args=[bilan.id]), post)


class FluxSaisieTests(BaseBilanExterne):

    def test_creation_avec_tests_externes_mene_a_la_saisie(self):
        bilan, response = self.creer(lateralite='Gaucher', etablissement='École Les Oliviers')
        self.assertRedirects(response, reverse('bilans:donnees', args=[bilan.id]))
        self.assertEqual(set(bilan.scores), {'wisc5', 'tmt'})
        self.assertIn('data-section="ext_wisc5" data-type="test"', bilan.contenu)
        self.assertIn('Gaucher', bilan.contenu)
        self.assertIn('Évaluation des capacités attentionnelles et exécutives', bilan.contenu)
        self.assertIn('Scores non encore saisis', bilan.contenu)
        self.assertEqual(self.client.get(reverse('bilans:donnees', args=[bilan.id])).status_code, 200)

    def test_saisie_met_a_jour_tableaux_et_garde_les_textes(self):
        bilan, _ = self.creer()
        # Le psy a déjà rédigé l'interprétation du WISC-V
        bilan.contenu = bilan.contenu.replace(
            '<h3>Interprétation</h3>\n<p><em>', '<h3>Interprétation</h3>\n<p>Mon analyse du profil.</p>\n<p><em>', 1)
        bilan.save()
        post = {'externes': ['wisc5', 'stroop'], 'info_lateralite': 'Droitier',
                'wisc5__g__indices__ICV__note': '103', 'wisc5__g__indices__IVT__note': '66',
                'stroop__g__conditions__interference__score': '52', 'stroop__g__conditions__interference__classe': 'Classe 1'}
        response = self.saisir(bilan, post)
        self.assertRedirects(response, reverse('bilans:editeur', args=[bilan.id]))
        bilan.refresh_from_db()
        self.assertIn('Mon analyse du profil.', bilan.contenu)
        self.assertIn('<td>103</td>', bilan.contenu)
        self.assertIn('data-figure="wisc5.indices"', bilan.contenu)
        self.assertIn('data-section="ext_stroop"', bilan.contenu)
        self.assertNotIn('data-section="ext_tmt"', bilan.contenu)  # test retiré
        self.assertIn('Droitier', bilan.contenu)
        self.assertEqual(bilan.versions.first().motif, "Avant mise à jour des données")
        # Ordre des chapitres : intellectuel avant exécutif
        self.assertLess(bilan.contenu.index('ext_wisc5'), bilan.contenu.index('ext_stroop'))
        # Le tableau de synthèse reprend les scores
        self.assertIn('WISC-V - ICV', bilan.contenu)

    def test_graphique_png(self):
        bilan, _ = self.creer(externes=['wisc5'])
        self.saisir(bilan, {'externes': ['wisc5'], 'wisc5__g__indices__ICV__note': '103',
                            'wisc5__g__indices__IVT__note': '66', 'wisc5__g__indices__IMT__note': '97'})
        response = self.client.get(reverse('bilans:figure', args=[bilan.id, 'wisc5.indices']))
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertTrue(response.content.startswith(b'\x89PNG'))
        self.assertEqual(self.client.get(reverse('bilans:figure', args=[bilan.id, 'tmt.indices'])).status_code, 404)

    def test_contexte_ia_contient_les_scores_saisis(self):
        bilan, _ = self.creer(externes=['tmt'], adresse_par='Dr Bennani, pédopsychiatre')
        self.saisir(bilan, {'externes': ['tmt'], 'tmt__g__parties__A__temps': '56', 'tmt__g__parties__B__temps': '88',
                            'info_adresse_par': 'Dr Bennani, pédopsychiatre'})
        bilan.refresh_from_db()
        contexte = donnees.contexte_patient(bilan, self.psy)
        self.assertIn('| Indice B - A | 32 s |', contexte)
        masque = Pseudonymiseur.pour_bilan(bilan).masquer(contexte + " Le Dr Bennani suit Rayan.")
        self.assertNotIn('Bennani', masque)
        self.assertNotIn('Rayan', masque)


class CoherenceTests(BaseBilanExterne):

    def test_detecte_score_niveau_edition_et_texte_d_attente(self):
        bilan, _ = self.creer(externes=['wais4', 'bdi', 'rcads'])
        bilan.scores = {
            'wais4': {'grilles': {'indices': {'ICV': {'note': '100', 'percentile': '50'}}, 'subtests': {'ARI': {'ns': '6'}}}},
            'bdi': {'champs': {'score': '12'}},
            'rcads': {'grilles': {'echelles': {'total_anxiete': {'t': '41'}}}},
        }
        bilan.contenu = (
            '<h1>Bilan</h1><h2 data-section="conclusion" data-type="ia">Conclusion</h2>'
            '<p>La WAIS-V montre une compréhension verbale moyenne (ICV = 102 ; P55). Arithmétique (NS = 6) est faible.</p>'
            '<p>Le BDI met en évidence des symptômes dépressifs modérés.</p>'
            '<h2 data-section="ext_rcads" data-type="test">RCADS</h2><p><em>Lecture des scores T : 70 et plus = seuil clinique.</em></p><h3>Interprétation</h3><p>Un score d\'anxiété élevé, dépassant le seuil clinique.</p>'
            '<p>[à compléter : observations]</p>'
        )
        alertes = coherence.verifier(bilan.contenu, donnees.valeurs_de_reference(bilan, self.psy))
        messages = ' | '.join(a['message'] for a in alertes)
        self.assertIn('ICV (WAIS-IV) vaut 100 dans les scores, mais 102 dans le texte', messages)
        self.assertIn('Percentile de ICV : 50', messages)
        self.assertNotIn('Arithmétique', messages)  # score juste : pas d'alerte
        self.assertIn('BDI-II : le score correspond à un niveau « légère »', messages)
        self.assertIn('RCADS : aucun score T', messages)
        self.assertIn('WAIS-V', messages)
        self.assertIn("Texte d'attente", messages)

    def test_vue_coherence(self):
        bilan, _ = self.creer(externes=['tmt'])
        response = self.client.get(reverse('bilans:coherence', args=[bilan.id]))
        self.assertTrue(response.json()['ok'])
        self.assertTrue(any("Texte d'attente" in a['message'] for a in response.json()['alertes']))


class IALotsTests(BaseBilanExterne):

    @override_settings(IA_API_KEY='cle-test')
    @patch('bilans.ia._appeler', side_effect=ia.IAErreur("Limite par minute", attendre=12))
    def test_limite_par_minute_renvoie_le_delai(self, _):
        bilan, _ = self.creer(externes=['tmt'])
        response = self.client.post(reverse('bilans:ia_premier_jet', args=[bilan.id]), data='{}',
                                    content_type='application/json')
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['attendre'], 12)

    @override_settings(IA_API_KEY='cle-test')
    @patch('bilans.ia._appeler')
    def test_conclusion_redigee_en_dernier_avec_le_bilan_deja_ecrit(self, appeler):
        bilan, _ = self.creer(externes=['tmt'])
        _, sections = donnees.hb.decouper_sections(donnees.hb.lire(bilan.contenu))
        from bilans.views import _prochain_lot, _sections_a_rediger
        a_rediger = _sections_a_rediger(bilan, self.psy)
        cles = [s['cle'] for s in a_rediger]
        self.assertIn('ext_tmt', cles)
        self.assertEqual(cles[-2:], ['conclusion', 'recommandations'])
        lot, finale = _prochain_lot(a_rediger)
        self.assertFalse(finale)
        self.assertNotIn('conclusion', [s['cle'] for s in lot])
        # Sans anamnèse ni notes de séance, l'IA ne rédige pas l'histoire du patient (elle l'inventerait)
        self.assertNotIn('anamnese', cles)
        self.assertNotIn('scolarite', cles)
        self.assertIn('motif_reference', cles)
        lot, finale = _prochain_lot([s for s in a_rediger if s['cle'] in ('conclusion', 'recommandations')])
        self.assertTrue(finale)
        self.assertEqual([s['cle'] for s in lot], ['conclusion'])


MEDIA_TEST = tempfile.mkdtemp(prefix='bilans-media-')


@override_settings(MEDIA_ROOT=MEDIA_TEST)
class ExportsEtReglagesTests(BaseBilanExterne):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEST, ignore_errors=True)

    def test_exports_avec_en_tete_graphique_et_signature(self):
        EnTeteBilan.objects.create(
            utilisateur=self.psy, nom_affiche="ALAOUI Nadia", titre_pro="Psychologue clinicienne",
            texte_droite="نادية العلوي", pied_de_page="Rabat - 06 00 00 00 00",
            signature=SimpleUploadedFile('s.png', _png(), content_type='image/png'),
            logo=SimpleUploadedFile('l.png', _png(), content_type='image/png'),
        )
        bilan, _ = self.creer(externes=['wisc5'])
        self.saisir(bilan, {'externes': ['wisc5'], 'wisc5__g__indices__ICV__note': '103',
                            'wisc5__g__indices__IVT__note': '66', 'wisc5__g__indices__IRF__note': '67'})
        bilan.refresh_from_db()
        self.assertIn('data-figure="signature"', bilan.contenu)
        self.assertIn('ALAOUI Nadia', bilan.contenu)
        for fmt, signature in (('docx', b'PK'), ('pdf', b'%PDF')):
            response = self.client.get(reverse('bilans:export', args=[bilan.id, fmt]))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.content.startswith(signature))

    def test_en_tete_enregistre_et_refuse_un_faux_fichier(self):
        response = self.client.post(reverse('bilans:en_tete'), {
            'nom_affiche': 'ALAOUI Nadia', 'titre_pro': 'Psychologue', 'formule_signature': 'Pour faire valoir ce que de droit.',
            'signature': SimpleUploadedFile('s.png', b'pas une image', content_type='image/png'),
        })
        self.assertRedirects(response, reverse('bilans:en_tete'))
        en_tete = EnTeteBilan.objects.get(utilisateur=self.psy)
        self.assertEqual(en_tete.nom_affiche, 'ALAOUI Nadia')
        self.assertFalse(en_tete.signature)

    def test_bibliotheque_personnaliser_masquer_retablir(self):
        url = reverse('bilans:textes_types')
        self.client.post(url, {'action': 'enregistrer', 'cle': 'rec_tiers_temps', 'categorie': 'recommandation',
                               'titre': 'Tiers-temps', 'contenu': 'Ma version du tiers-temps.'})
        textes = {t['cle']: t for t in self.client.get(reverse('bilans:textes_types_json')).json()['textes']}
        self.assertEqual(textes['rec_tiers_temps']['contenu'], 'Ma version du tiers-temps.')
        self.client.post(url, {'action': 'masquer', 'cle': 'rec_consignes', 'titre': 'Consignes'})
        textes = {t['cle'] for t in self.client.get(reverse('bilans:textes_types_json')).json()['textes']}
        self.assertNotIn('rec_consignes', textes)
        self.client.post(url, {'action': 'retablir', 'cle': 'rec_consignes'})
        self.client.post(url, {'action': 'enregistrer', 'titre': 'Mon texte', 'contenu': '- un\n- deux'})
        json_textes = self.client.get(reverse('bilans:textes_types_json')).json()['textes']
        self.assertIn('rec_consignes', {t['cle'] for t in json_textes})
        perso = next(t for t in json_textes if t['titre'] == 'Mon texte')
        self.assertIn('<ul>', perso['html'])
        self.assertEqual(TexteType.objects.filter(organization=self.org).count(), 2)
        self.assertEqual(self.client.get(url).status_code, 200)
