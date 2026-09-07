from datetime import date

from django.test import TestCase
from django.utils import timezone

from accounts.models import Organization
from cabinet.models import Patient
from tests_psy.models import (
    Domain, SousDomain, QuestionVineland, ReponseVineland, TestVineland, EchelleVMapping,
    NoteDomaineVMapping,
)
from tests_psy.views.vineland import (
    get_age_tranches, get_patient_age, calculate_item_plancher, calculate_all_scores,
    find_echelle_v_mapping, get_domain_mapping,
)


class GetAgeTranchesTests(TestCase):
    """Vérifie les bornes des tranches d'âge utilisées pour les tables de normes."""

    def test_moins_dun_an_retourne_aucune_tranche(self):
        self.assertEqual(get_age_tranches(0), (None, None))

    def test_tranches_domaine_et_intervalle(self):
        cases = {
            1: ('1-2', '1'),
            2: ('1-2', '2'),
            3: ('3-6', '3'),
            6: ('3-6', '6'),
            7: ('7-18', '7-8'),
            8: ('7-18', '7-8'),
            9: ('7-18', '9-11'),
            11: ('7-18', '9-11'),
            12: ('7-18', '12-14'),
            15: ('7-18', '15-18'),
            18: ('7-18', '15-18'),
            19: ('19-49', '19-29'),
            29: ('19-49', '19-29'),
            30: ('19-49', '30-49'),
            49: ('19-49', '30-49'),
            50: ('50-90', '50-90'),
            90: ('50-90', '50-90'),
        }
        for age, attendu in cases.items():
            with self.subTest(age=age):
                self.assertEqual(get_age_tranches(age), attendu)


class GetPatientAgeTests(TestCase):
    """Vérifie le calcul de l'âge précis (années/mois/jours) au moment de la passation."""

    def test_age_calcule_a_partir_de_la_date_de_passation(self):
        organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        patient = Patient.objects.create(
            organization=organization, nom="Dupont", prenom="Jean", date_naissance=date(2015, 3, 10)
        )
        test = TestVineland.objects.create(
            organization=organization, patient=patient,
            date_passation=timezone.make_aware(timezone.datetime(2024, 6, 15)),
        )

        age_info = get_patient_age(test)

        self.assertEqual(age_info['years'], 9)
        self.assertEqual(age_info['months'], 3)
        self.assertEqual(age_info['days'], 5)


class CalculateItemPlancherTests(TestCase):
    """
    Vérifie la détection de l'item plancher (4 réponses consécutives à '2').
    Le retour est le numéro du PREMIER item de cette série de 4.
    """

    class _FakeQuestion:
        def __init__(self, numero_item):
            self.numero_item = numero_item

    class _FakeReponse:
        def __init__(self, numero_item, reponse):
            self.question = CalculateItemPlancherTests._FakeQuestion(numero_item)
            self.reponse = reponse

    def _reponses(self, valeurs):
        return [self._FakeReponse(i + 1, v) for i, v in enumerate(valeurs)]

    def test_aucune_serie_de_4_retourne_zero(self):
        reponses = self._reponses(['2', '2', '1', '2', '2', '2'])
        self.assertEqual(calculate_item_plancher(reponses), 0)

    def test_serie_de_4_au_debut(self):
        reponses = self._reponses(['2', '2', '2', '2', '1', '0'])
        self.assertEqual(calculate_item_plancher(reponses), 1)  # item 4 - 3

    def test_serie_interrompue_puis_reformee(self):
        # items 1-3: '2', item4: '1' (casse la série), items 5-8: '2' (nouvelle série de 4)
        reponses = self._reponses(['2', '2', '2', '1', '2', '2', '2', '2'])
        self.assertEqual(calculate_item_plancher(reponses), 5)  # item 8 - 3

    def test_moins_de_quatre_consecutifs_retourne_zero(self):
        reponses = self._reponses(['2', '2', '2'])
        self.assertEqual(calculate_item_plancher(reponses), 0)


class CalculateAllScoresTests(TestCase):
    """
    Vérifie le calcul de la note brute par sous-domaine :
    note_brute = (item_plancher x 2) + somme(items 1/2 après le plancher) + nb NSP
    """

    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance="2015-01-01"
        )
        self.test_vineland = TestVineland.objects.create(organization=self.organization, patient=self.patient)
        self.domain = Domain.objects.create(name="Communication")
        self.sous_domaine = SousDomain.objects.create(domain=self.domain, name="Réceptif")
        self.questions = {
            i: QuestionVineland.objects.create(sous_domaine=self.sous_domaine, texte=f"Q{i}", numero_item=i)
            for i in range(1, 9)
        }

    def _repondre(self, numero_item, valeur):
        ReponseVineland.objects.create(
            organization=self.organization,
            test_vineland=self.test_vineland,
            question=self.questions[numero_item],
            reponse=valeur,
        )

    def test_note_brute_avec_item_plancher_et_nsp(self):
        # items 1-4: '2' (série de 4 -> item_plancher = 1)
        for i in range(1, 5):
            self._repondre(i, '2')
        self._repondre(5, '1')
        self._repondre(6, '2')
        self._repondre(7, 'NSP')
        self._repondre(8, 'NA')

        scores = calculate_all_scores(self.test_vineland)
        resultat = scores["Communication"]["Réceptif"]

        self.assertEqual(resultat['item_plancher'], 1)
        self.assertEqual(resultat['nsp_count'], 1)
        self.assertEqual(resultat['na_count'], 1)
        # sum_1_2 = items 2,3,4 ('2' chacun, numero > item_plancher) + item5('1') + item6('2') = 2+2+2+1+2 = 9
        self.assertEqual(resultat['sum_1_2'], 9)
        # note_brute = item_plancher*2 + sum_1_2 + nsp_count = 2 + 9 + 1 = 12
        self.assertEqual(resultat['note_brute'], 12)
        self.assertFalse(resultat['a_refaire'])

    def test_a_refaire_si_plus_de_deux_nsp(self):
        self._repondre(1, 'NSP')
        self._repondre(2, 'NSP')
        self._repondre(3, 'NSP')

        scores = calculate_all_scores(self.test_vineland)
        resultat = scores["Communication"]["Réceptif"]

        self.assertEqual(resultat['nsp_count'], 3)
        self.assertTrue(resultat['a_refaire'])

    def test_sous_domaine_sans_reponse_note_brute_zero(self):
        scores = calculate_all_scores(self.test_vineland)
        resultat = scores["Communication"]["Réceptif"]

        self.assertEqual(resultat['note_brute'], 0)
        self.assertEqual(resultat['item_plancher'], 0)


class FindEchelleVMappingTests(TestCase):
    """Vérifie la recherche du mapping échelle-V par âge (avec ou sans précision en jours)."""

    def setUp(self):
        domain = Domain.objects.create(name="Communication")
        self.sous_domaine = SousDomain.objects.create(domain=domain, name="Réceptif")

    def test_mapping_sans_precision_jours(self):
        EchelleVMapping.objects.create(
            sous_domaine=self.sous_domaine,
            age_debut_annee=2, age_debut_mois=0, age_fin_annee=3, age_fin_mois=11,
            note_brute_min=0, note_brute_max=5, note_echelle_v=10,
        )
        age_info = {'years': 2, 'months': 6, 'days': 10}

        mapping = find_echelle_v_mapping(self.sous_domaine, note_brute=3, age_info=age_info)

        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.note_echelle_v, 10)

    def test_mapping_avec_precision_jours_respecte_le_jour_de_debut(self):
        EchelleVMapping.objects.create(
            sous_domaine=self.sous_domaine,
            age_debut_annee=4, age_debut_mois=0, age_debut_jour=15,
            age_fin_annee=4, age_fin_mois=11, age_fin_jour=30,
            note_brute_min=0, note_brute_max=5, note_echelle_v=12,
        )

        # avant le jour de début -> pas de correspondance
        avant = find_echelle_v_mapping(self.sous_domaine, note_brute=3, age_info={'years': 4, 'months': 0, 'days': 10})
        self.assertIsNone(avant)

        # à partir du jour de début -> correspondance
        apres = find_echelle_v_mapping(self.sous_domaine, note_brute=3, age_info={'years': 4, 'months': 0, 'days': 20})
        self.assertIsNotNone(apres)
        self.assertEqual(apres.note_echelle_v, 12)

    def test_note_brute_hors_plage_ne_correspond_pas(self):
        EchelleVMapping.objects.create(
            sous_domaine=self.sous_domaine,
            age_debut_annee=2, age_debut_mois=0, age_fin_annee=3, age_fin_mois=11,
            note_brute_min=0, note_brute_max=5, note_echelle_v=10,
        )
        age_info = {'years': 2, 'months': 6, 'days': 10}

        mapping = find_echelle_v_mapping(self.sous_domaine, note_brute=99, age_info=age_info)

        self.assertIsNone(mapping)


class GetDomainMappingTests(TestCase):
    """Vérifie la recherche du mapping de note de domaine (dispatch par nom de domaine)."""

    def test_mapping_communication_trouve_par_sa_plage(self):
        NoteDomaineVMapping.objects.create(
            tranche_age='7-18', communication_min=10, communication_max=20,
            note_standard=100, rang_percentile='50',
        )

        mapping = get_domain_mapping('Communication', domain_note_v_sum=15, tranche_age='7-18')

        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.note_standard, 100)

    def test_mapping_vie_quotidienne_utilise_sa_propre_plage(self):
        NoteDomaineVMapping.objects.create(
            tranche_age='7-18', vie_quotidienne_min=30, vie_quotidienne_max=40,
            note_standard=110, rang_percentile='60',
        )

        # Hors plage Communication (non renseignée) -> aucune correspondance
        self.assertIsNone(get_domain_mapping('Communication', domain_note_v_sum=35, tranche_age='7-18'))
        # Dans la plage Vie quotidienne -> correspondance
        mapping = get_domain_mapping('Vie quotidienne', domain_note_v_sum=35, tranche_age='7-18')
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.note_standard, 110)

    def test_somme_hors_plage_ne_correspond_pas(self):
        NoteDomaineVMapping.objects.create(
            tranche_age='7-18', communication_min=10, communication_max=20,
            note_standard=100, rang_percentile='50',
        )

        mapping = get_domain_mapping('Communication', domain_note_v_sum=999, tranche_age='7-18')

        self.assertIsNone(mapping)
