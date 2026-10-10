import json
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import skipUnless

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import License, Organization, User
from cabinet.models import Patient
from tests_psy.models import (
    ItemBRIEF, NormeBRIEF, NoteBruteImporteeBRIEF, PaireIncoherenceBRIEF, ReponseBRIEF, TestBRIEF,
)
from tests_psy.models.brief import ECHELLE_CHOICES
from tests_psy.views.brief.scoring import (
    calculer_resultats, classer_negativite, score_incoherence, score_negativite,
    scores_bruts_echelles, scores_bruts_indices,
)

ECHELLES = [code for code, _ in ECHELLE_CHOICES]
DATA_DIR = Path(__file__).resolve().parents[1] / 'data' / 'brief'
ITEMS_REELS = DATA_DIR / 'brief_parent_items.json'
NORMES_REELLES = DATA_DIR / 'brief_parent_normes.json'


def creer_items_synthetiques():
    """86 items fictifs (le vrai contenu est sous droit d'auteur et hors repo) : les 72
    premiers répartis 9 par échelle, items 1 à 9 de Négativité, une paire d'Incohérence."""
    for numero in range(1, 87):
        ItemBRIEF.objects.create(
            forme='parent', numero=numero, texte=f"Item fictif {numero}",
            echelle=ECHELLES[(numero - 1) % 8] if numero <= 72 else '',
            est_negativite=numero <= 9,
        )
    PaireIncoherenceBRIEF.objects.create(forme='parent', item_a=1, item_b=9)


class BriefScoringTests(TestCase):
    """Règles de cotation du manuel, sur des données construites à la main."""

    ITEMS = {echelle: [i * 10 + n for n in range(1, 4)] for i, echelle in enumerate(ECHELLES)}

    def test_score_brut_est_la_somme_des_items_de_l_echelle(self):
        reponses = {n: 3 for numeros in self.ITEMS.values() for n in numeros}
        resultats, manquants = scores_bruts_echelles(self.ITEMS, reponses)
        self.assertEqual(manquants, 0)
        for echelle in ECHELLES:
            self.assertEqual(resultats[echelle]['note_brute'], 9)

    def test_un_ou_deux_items_manquants_valent_un_point_chacun(self):
        reponses = {n: 3 for numeros in self.ITEMS.values() for n in numeros}
        del reponses[self.ITEMS['inhibition'][0]]
        del reponses[self.ITEMS['flexibilite'][0]]
        del reponses[self.ITEMS['flexibilite'][1]]
        resultats, manquants = scores_bruts_echelles(self.ITEMS, reponses)
        self.assertEqual(manquants, 3)
        self.assertEqual(resultats['inhibition']['note_brute'], 3 + 3 + 1)
        self.assertEqual(resultats['flexibilite']['note_brute'], 3 + 1 + 1)

    def test_plus_de_deux_manquants_pas_de_score_brut_pour_l_echelle(self):
        items = {**self.ITEMS, 'inhibition': [1, 2, 3, 4]}
        reponses = {n: 2 for numeros in items.values() for n in numeros}
        for n in (1, 2, 3):
            del reponses[n]
        resultats, _ = scores_bruts_echelles(items, reponses)
        self.assertIsNone(resultats['inhibition']['note_brute'])
        self.assertEqual(resultats['inhibition']['manquants'], 3)

    def test_indices_et_propagation_d_une_echelle_non_calculable(self):
        notes = dict(zip(ECHELLES, [26, 13, 27, 21, 26, 35, 18, 21]))
        self.assertEqual(scores_bruts_indices(notes), {'irc': 66, 'im': 121, 'ceg': 187})
        notes['controle'] = None
        indices = scores_bruts_indices(notes)
        self.assertEqual(indices['irc'], 66)
        self.assertIsNone(indices['im'])
        self.assertIsNone(indices['ceg'])

    def test_negativite_compte_les_items_cotes_3(self):
        resultat = score_negativite([1, 2, 3, 4, 5], {1: 3, 2: 3, 3: 2, 4: 1})
        self.assertEqual(resultat['score'], 2)
        self.assertEqual(resultat['manquants'], 1)
        self.assertEqual(resultat['classification'], 'Acceptable')

    def test_seuils_de_negativite(self):
        self.assertEqual(classer_negativite(4), 'Acceptable')
        self.assertEqual(classer_negativite(5), 'Élevé')
        self.assertEqual(classer_negativite(6), 'Élevé')
        self.assertEqual(classer_negativite(7), 'Très élevé')

    def test_incoherence_somme_des_differences_absolues(self):
        resultat = score_incoherence([(1, 2), (3, 4), (5, 6)], {1: 3, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2})
        self.assertEqual(resultat['score'], 2 + 1 + 0)
        self.assertEqual(resultat['paires_incompletes'], 0)

    def test_incoherence_paire_incomplete_ignoree_et_signalee(self):
        resultat = score_incoherence([(1, 2), (3, 4)], {1: 3, 2: 1, 3: 1})
        self.assertEqual(resultat['score'], 2)
        self.assertEqual(resultat['paires_incompletes'], 1)
        self.assertIsNone(resultat['classification'])


# Réponses de la feuille de cotation d'exemple du manuel (Figure 2 : garçon TDA/H de 8 ans,
# Forme Parent) - 1 = Jamais, 2 = Parfois, 3 = Souvent.
REPONSES_FIGURE_2 = [
    3, 3, 3, 3, 2, 1, 3, 1, 2, 3, 3, 2, 2, 3, 3, 3, 3, 3, 3, 3, 2, 3, 1, 1, 2, 2, 3, 2, 3, 2,
    3, 3, 2, 3, 3, 3, 3, 2, 2, 3, 3, 2, 3, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2, 3, 3, 2, 3,
    2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 1, 3, 3, 3, 3, 2, 3, 2, 2, 3, 3, 2, 1, 3, 3, 1,
]


@skipUnless(ITEMS_REELS.exists(), "Contenu BRIEF réel absent (fichier non versionné)")
class BriefExempleDuManuelTests(TestCase):
    """Reproduit l'exemple complet du manuel (Figures 1 à 4) avec le vrai questionnaire :
    verrouille la répartition item -> échelle, les indices et les échelles de validité."""

    def setUp(self):
        call_command('import_brief', items=str(ITEMS_REELS), normes=str(NORMES_REELLES), verbosity=0)
        self.organization = Organization.objects.create(name="Cabinet Exemple", slug="cabinet-exemple")
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Exemple", prenom="Garçon", date_naissance=date(2017, 6, 1),
        )
        self.test = TestBRIEF.objects.create(
            organization=self.organization, patient=self.patient, sexe='M',
            date_passation=timezone.make_aware(datetime(2026, 1, 15)),
        )
        items = {item.numero: item for item in ItemBRIEF.objects.filter(forme='parent')}
        for numero, valeur in enumerate(REPONSES_FIGURE_2, start=1):
            ReponseBRIEF.objects.create(
                organization=self.organization, test=self.test, item=items[numero], reponse='JPS'[valeur - 1],
            )

    def test_scores_bruts_de_la_figure_2(self):
        r = calculer_resultats(self.test)
        bruts = {ligne['code']: ligne['note_brute'] for ligne in r['lignes']}
        self.assertEqual(bruts, {
            'inhibition': 26, 'flexibilite': 13, 'controle_emotionnel': 27, 'initiation': 21,
            'memoire_travail': 26, 'planification': 35, 'organisation_materiel': 18, 'controle': 21,
            'irc': 66, 'im': 121, 'ceg': 187,
        })
        self.assertEqual(r['manquants_total'], 0)

    def test_validite_des_figures_3_et_4(self):
        r = calculer_resultats(self.test)
        self.assertEqual(r['negativite']['score'], 2)
        self.assertEqual(r['negativite']['classification'], 'Acceptable')
        self.assertEqual(r['incoherence']['score'], 4)

    @skipUnless(NORMES_REELLES.exists(), "Normes BRIEF réelles absentes (fichier non versionné)")
    def test_scores_t_percentiles_et_ic_de_la_figure_1(self):
        r = calculer_resultats(self.test)
        self.assertEqual(r['age'], 8)
        attendus = {
            'inhibition': (82, 99, 75, 89), 'flexibilite': (55, 74, 46, 64),
            'controle_emotionnel': (81, 99, 75, 87), 'initiation': (80, 99, 71, 89),
            'memoire_travail': (78, 99, 72, 84), 'planification': (87, 99, 81, 93),
            'organisation_materiel': (73, 99, 66, 80), 'controle': (71, 99, 64, 78),
            'irc': (79, 99, 74, 84), 'im': (86, 99, 82, 90), 'ceg': (87, 99, 83, 91),
        }
        for code, (t, percentile, ic_bas, ic_haut) in attendus.items():
            ligne = r['par_code'][code]
            self.assertEqual(
                (ligne['score_t'], ligne['percentile'], ligne['ic_bas'], ligne['ic_haut']),
                (t, percentile, ic_bas, ic_haut), code,
            )


class BriefTestCaseBase(TestCase):
    def setUp(self):
        creer_items_synthetiques()
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        self.license = License.objects.create(
            organization=self.organization, plan='lifetime', status='active', has_brief=True,
        )
        self.user = User.objects.create_user(
            username="psy", password="test-pass-123", role='psychologist', organization=self.organization,
        )
        # 2016-01-01 : 10 ans à la date du jour (tranche 7-10 ans), anniversaire déjà passé.
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date(2016, 1, 1),
        )
        self.client.force_login(self.user)

    def creer_test(self, **kwargs):
        return TestBRIEF.objects.create(
            organization=self.organization, patient=self.patient, psychologue=self.user, sexe='M', **kwargs,
        )

    def repondre_a_tout(self, test, valeur='P'):
        for item in ItemBRIEF.objects.all():
            ReponseBRIEF.objects.create(organization=self.organization, test=test, item=item, reponse=valeur)


class BriefAccesTests(BriefTestCaseBase):

    def test_liste_accessible_avec_licence_et_permission(self):
        response = self.client.get(reverse('tests_psy:brief_liste'))
        self.assertEqual(response.status_code, 200)

    def test_licence_sans_brief_bloque_l_acces(self):
        self.license.has_brief = False
        self.license.save()
        response = self.client.get(reverse('tests_psy:brief_liste'))
        self.assertNotEqual(response.status_code, 200)

    def test_permission_utilisateur_retiree_bloque_l_acces(self):
        self.user.can_access_brief = False
        self.user.save()
        response = self.client.get(reverse('tests_psy:brief_liste'))
        self.assertNotEqual(response.status_code, 200)

    def test_test_d_une_autre_organisation_introuvable(self):
        autre_org = Organization.objects.create(name="Autre", slug="autre")
        autre_patient = Patient.objects.create(
            organization=autre_org, nom="X", prenom="Y", date_naissance=date(2015, 1, 1),
        )
        test = TestBRIEF.objects.create(organization=autre_org, patient=autre_patient, sexe='F')
        response = self.client.get(reverse('tests_psy:brief_resultats', kwargs={'test_id': test.id}))
        self.assertEqual(response.status_code, 404)

    def test_superadmin_voit_les_resultats_d_un_cabinet(self):
        test = self.creer_test(termine_le=timezone.now())
        self.repondre_a_tout(test)
        admin = User.objects.create_user(username="admin-plateforme", password="x", role='superadmin')
        self.client.force_login(admin)
        response = self.client.get(reverse('tests_psy:brief_resultats', kwargs={'test_id': test.id}))
        self.assertEqual(response.status_code, 200)

    def test_quota_de_la_licence_bloque_la_creation(self):
        self.license.max_tests_brief = 1
        self.license.save()
        self.creer_test()
        response = self.client.post(reverse('tests_psy:brief_nouveau'), {
            'patient': self.patient.id, 'sexe': 'M', 'mode': 'cabinet',
        })
        self.assertRedirects(response, reverse('tests_psy:brief_liste'))
        self.assertEqual(TestBRIEF.objects.count(), 1)


class BriefCreationEtPassationTests(BriefTestCaseBase):

    def test_creation_mode_cabinet(self):
        response = self.client.post(reverse('tests_psy:brief_nouveau'), {
            'patient': self.patient.id, 'sexe': 'F', 'repondant': 'Mère', 'mode': 'cabinet',
        })
        test = TestBRIEF.objects.get()
        self.assertRedirects(response, reverse('tests_psy:brief_questionnaire', kwargs={'test_id': test.id}))
        self.assertEqual((test.sexe, test.repondant, test.organization), ('F', 'Mère', self.organization))

    def test_creation_mode_importe(self):
        response = self.client.post(reverse('tests_psy:brief_nouveau'), {
            'patient': self.patient.id, 'sexe': 'M', 'mode': 'importe',
        })
        test = TestBRIEF.objects.get()
        self.assertRedirects(response, reverse('tests_psy:brief_notes_importees', kwargs={'test_id': test.id}))

    def test_creation_mode_lien_public(self):
        response = self.client.post(reverse('tests_psy:brief_nouveau'), {
            'patient': self.patient.id, 'sexe': 'M', 'mode': 'lien_public', 'duree_jours': 7,
        })
        test = TestBRIEF.objects.get()
        self.assertRedirects(response, reverse('tests_psy:brief_lien_genere', kwargs={'test_id': test.id}))
        self.assertIsNotNone(test.lien_token)

    def test_sexe_obligatoire(self):
        self.client.post(reverse('tests_psy:brief_nouveau'), {'patient': self.patient.id, 'mode': 'cabinet'})
        self.assertFalse(TestBRIEF.objects.exists())

    def test_enregistrement_brouillon_puis_terminer(self):
        test = self.creer_test()
        url = reverse('tests_psy:brief_questionnaire', kwargs={'test_id': test.id})

        self.client.post(url, {'item_1': 'S', 'item_2': 'J', 'action': 'save'})
        test.refresh_from_db()
        self.assertIsNone(test.termine_le)
        self.assertEqual(
            dict(test.reponses.values_list('item__numero', 'valeur')), {1: 3, 2: 1},
        )

        response = self.client.post(url, {'item_2': 'P', 'action': 'submit'})
        test.refresh_from_db()
        self.assertIsNotNone(test.termine_le)
        self.assertRedirects(response, reverse('tests_psy:brief_resultats', kwargs={'test_id': test.id}))
        reponse = test.reponses.get(item__numero=2)
        self.assertEqual((reponse.reponse, reponse.valeur), ('P', 2))

    def test_valeur_invalide_ignoree(self):
        test = self.creer_test()
        self.client.post(reverse('tests_psy:brief_questionnaire', kwargs={'test_id': test.id}), {
            'item_1': 'X', 'item_999': 'S', 'action': 'save',
        })
        self.assertFalse(test.reponses.exists())

    def test_notes_importees_puis_resultats(self):
        test = self.creer_test(mode='importe')
        donnees = {f'echelle_{code}': 15 for code in ECHELLES}
        donnees.update({'negativite': 5, 'incoherence': 3})
        response = self.client.post(reverse('tests_psy:brief_notes_importees', kwargs={'test_id': test.id}), donnees)
        self.assertRedirects(response, reverse('tests_psy:brief_resultats', kwargs={'test_id': test.id}))
        self.assertEqual(NoteBruteImporteeBRIEF.objects.filter(test=test).count(), 8)

        test.refresh_from_db()
        r = calculer_resultats(test)
        self.assertEqual(r['par_code']['irc']['note_brute'], 45)
        self.assertEqual(r['par_code']['ceg']['note_brute'], 120)
        self.assertEqual(r['negativite']['classification'], 'Élevé')
        self.assertTrue(test.is_complete)


class BriefResultatsTests(BriefTestCaseBase):

    def test_resultats_sans_normes_affiche_scores_bruts_et_attente(self):
        test = self.creer_test(termine_le=timezone.now())
        self.repondre_a_tout(test, 'S')
        response = self.client.get(reverse('tests_psy:brief_resultats', kwargs={'test_id': test.id}))
        self.assertContains(response, "Scores T et percentiles en attente")
        r = response.context['r']
        self.assertEqual(r['par_code']['inhibition']['note_brute'], 27)  # 9 items x 3
        self.assertIsNone(r['par_code']['inhibition']['score_t'])

    def test_resultats_avec_normes(self):
        test = self.creer_test(termine_le=timezone.now())
        self.repondre_a_tout(test, 'S')
        NormeBRIEF.objects.create(
            sexe='M', age_min=7, age_max=10, echelle='inhibition', score_brut=27, score_t=85, percentile=99, ic90=7,
        )
        r = calculer_resultats(test)
        ligne = r['par_code']['inhibition']
        self.assertEqual((ligne['score_t'], ligne['percentile'], ligne['ic_bas'], ligne['ic_haut']), (85, 99, 78, 92))
        self.assertTrue(ligne['significatif'])
        self.assertTrue(r['normes_disponibles'])

    def test_normes_d_une_autre_tranche_ou_de_l_autre_sexe_non_utilisees(self):
        test = self.creer_test(termine_le=timezone.now())
        self.repondre_a_tout(test, 'S')
        NormeBRIEF.objects.create(sexe='F', age_min=7, age_max=10, echelle='inhibition', score_brut=27, score_t=80)
        NormeBRIEF.objects.create(sexe='M', age_min=11, age_max=14, echelle='inhibition', score_brut=27, score_t=75)
        self.assertIsNone(calculer_resultats(test)['par_code']['inhibition']['score_t'])

    def test_plus_de_14_manquants_protocole_non_cotable(self):
        test = self.creer_test(termine_le=timezone.now())
        for item in ItemBRIEF.objects.filter(numero__gt=15):
            ReponseBRIEF.objects.create(organization=self.organization, test=test, item=item, reponse='P')
        NormeBRIEF.objects.create(sexe='M', age_min=7, age_max=10, echelle='inhibition', score_brut=18, score_t=60)
        r = calculer_resultats(test)
        self.assertEqual(r['manquants_total'], 15)
        self.assertFalse(r['protocole_cotable'])
        self.assertFalse(r['normes_disponibles'])

    def test_alerte_ecart_irc_im(self):
        test = self.creer_test(mode='importe')
        for code in ECHELLES:
            NoteBruteImporteeBRIEF.objects.create(organization=self.organization, test=test, echelle=code, note_brute=10)
        NormeBRIEF.objects.create(sexe='M', age_min=7, age_max=10, echelle='irc', score_brut=30, score_t=70)
        NormeBRIEF.objects.create(sexe='M', age_min=7, age_max=10, echelle='im', score_brut=50, score_t=55)
        r = calculer_resultats(test)
        self.assertEqual(r['ecart_irc_im'], 15)
        self.assertTrue(r['alerte_ecart_irc_im'])

    def test_pdf(self):
        test = self.creer_test(termine_le=timezone.now())
        self.repondre_a_tout(test)
        NormeBRIEF.objects.create(sexe='M', age_min=7, age_max=10, echelle='inhibition', score_brut=18, score_t=60, ic90=7)
        response = self.client.get(reverse('tests_psy:brief_pdf', kwargs={'test_id': test.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_suppression(self):
        test = self.creer_test()
        response = self.client.post(reverse('tests_psy:brief_delete', kwargs={'test_id': test.id}))
        self.assertRedirects(response, reverse('tests_psy:brief_liste'))
        self.assertFalse(TestBRIEF.objects.exists())

    def test_onglet_tests_de_la_fiche_patient(self):
        from cabinet.views.patients import _patient_tests_par_categorie
        self.creer_test()
        categories = _patient_tests_par_categorie(self.user, self.patient)
        self.assertIn('BRIEF', [c['label'] for c in categories])


class BriefLienPublicTests(BriefTestCaseBase):

    def setUp(self):
        super().setUp()
        self.test = self.creer_test()
        self.test.generate_lien_public(duree_jours=7)
        self.anon = Client()
        self.url = reverse('tests_psy:brief_public_questionnaire', kwargs={'token': self.test.lien_token})

    def test_accessible_sans_connexion_sans_aucun_score(self):
        response = self.anon.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for interdit in ('brief_resultats', 'brief_pdf', 'Score T', 'Négativité'):
            self.assertNotIn(interdit, content)

    def test_enregistrer_puis_envoyer_verrouille_le_lien(self):
        self.anon.post(self.url, {'item_1': 'S', 'action': 'save'})
        self.test.refresh_from_db()
        self.assertIsNone(self.test.lien_soumis_le)

        response = self.anon.post(self.url, {'item_2': 'J', 'action': 'submit'})
        self.assertRedirects(response, reverse('tests_psy:brief_public_merci', kwargs={'token': self.test.lien_token}))
        self.test.refresh_from_db()
        self.assertIsNotNone(self.test.lien_soumis_le)
        self.assertEqual(self.test.reponses.count(), 2)
        self.assertContains(self.anon.get(self.url), "déjà été transmises")

    def test_lien_expire(self):
        self.test.lien_expire_le = timezone.now() - timedelta(days=1)
        self.test.save()
        self.assertContains(self.anon.get(self.url), "expiré")

    def test_jeton_invalide(self):
        response = self.anon.get(reverse('tests_psy:brief_public_questionnaire', kwargs={'token': 'nimportequoi'}))
        self.assertEqual(response.status_code, 404)

    def test_reouverture_par_le_psy(self):
        self.test.lien_soumis_le = timezone.now()
        self.test.save()
        self.client.post(reverse('tests_psy:brief_reouvrir_lien', kwargs={'test_id': self.test.id}))
        self.test.refresh_from_db()
        self.assertIsNone(self.test.lien_soumis_le)
        self.assertEqual(self.anon.get(self.url).status_code, 200)


class ImportBriefCommandTests(TestCase):

    def _fichier(self, contenu):
        f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(contenu, f)
        f.close()
        self.addCleanup(Path(f.name).unlink)
        return f.name

    def test_import_des_fichiers_d_exemple(self):
        call_command(
            'import_brief', verbosity=0,
            items=str(DATA_DIR / 'brief_parent_items.example.json'),
            normes=str(DATA_DIR / 'brief_parent_normes.example.json'),
        )
        self.assertEqual(ItemBRIEF.objects.count(), 3)
        self.assertEqual(PaireIncoherenceBRIEF.objects.count(), 1)
        self.assertEqual(NormeBRIEF.objects.get(echelle='inhibition', score_brut=11).score_t, 34)

    def test_reimport_remplace_la_table(self):
        normes = str(DATA_DIR / 'brief_parent_normes.example.json')
        call_command('import_brief', items='absent.json', normes=normes, verbosity=0)
        call_command('import_brief', items='absent.json', normes=normes, verbosity=0)
        self.assertEqual(NormeBRIEF.objects.count(), 3)

    def test_score_t_decroissant_refuse(self):
        chemin = self._fichier({'forme': 'parent', 'tables': [{
            'sexe': 'M', 'age_min': 5, 'age_max': 6, 'echelle': 'inhibition', 'ic90': 7,
            'scores': {'10': [31, 4], '11': [30, 9]},
        }]})
        with self.assertRaises(CommandError):
            call_command('import_brief', items='absent.json', normes=chemin, verbosity=0)
        self.assertFalse(NormeBRIEF.objects.exists())

    def test_aucun_fichier(self):
        with self.assertRaises(CommandError):
            call_command('import_brief', items='absent.json', normes='absent.json', verbosity=0)
