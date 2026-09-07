from django.test import TestCase

from tests_psy.models import (
    Domain, SousDomain, ComparaisonDomaineVineland, ComparaisonSousDomaineVineland,
    FrequenceDifferenceDomaineVineland, FrequenceDifferenceSousDomaineVineland,
)
from tests_psy.views.vineland import (
    extract_number, get_frequency_percentage, find_domain_comparison, find_domain_frequency,
    find_sous_domaine_comparison, find_sous_domaine_frequency, generate_domain_comparisons,
    generate_sous_domaine_comparisons, generate_interdomaine_comparisons,
)


class _FakeFrequence:
    """Stub léger : get_frequency_percentage ne fait que lire ces 3 attributs."""
    def __init__(self, frequence_5=None, frequence_10=None, frequence_16=None):
        self.frequence_5 = frequence_5
        self.frequence_10 = frequence_10
        self.frequence_16 = frequence_16


class ExtractNumberTests(TestCase):

    def test_valeur_vide_retourne_9999(self):
        self.assertEqual(extract_number(None), 9999)
        self.assertEqual(extract_number(''), 9999)

    def test_valeur_avec_plus(self):
        self.assertEqual(extract_number('16+'), 16)

    def test_valeur_avec_tiret_prend_la_borne_basse(self):
        self.assertEqual(extract_number('5-10'), 5)

    def test_valeur_numerique_simple(self):
        self.assertEqual(extract_number('7'), 7)

    def test_valeur_non_numerique_retourne_9999(self):
        self.assertEqual(extract_number('abc'), 9999)


class GetFrequencyPercentageTests(TestCase):

    def test_aucune_frequence_retourne_none(self):
        self.assertIsNone(get_frequency_percentage(10, None))

    def test_priorite_au_seuil_5_pourcent(self):
        freq = _FakeFrequence(frequence_5='8', frequence_10='5', frequence_16='2')
        self.assertEqual(get_frequency_percentage(10, freq), '5%')

    def test_seuil_10_pourcent_si_5_non_atteint(self):
        freq = _FakeFrequence(frequence_5='20', frequence_10='5', frequence_16='2')
        self.assertEqual(get_frequency_percentage(10, freq), '10%')

    def test_seuil_16_pourcent_si_5_et_10_non_atteints(self):
        freq = _FakeFrequence(frequence_5='20', frequence_10='15', frequence_16='2')
        self.assertEqual(get_frequency_percentage(10, freq), '16%')

    def test_difference_sous_tous_les_seuils_retourne_none(self):
        freq = _FakeFrequence(frequence_5='20', frequence_10='15', frequence_16='12')
        self.assertIsNone(get_frequency_percentage(10, freq))


class FindDomainComparisonAndFrequencyTests(TestCase):
    """Vérifie que la recherche fonctionne dans les deux sens (domaine1<->domaine2)."""

    def setUp(self):
        self.domaine_a = Domain.objects.create(name="Communication")
        self.domaine_b = Domain.objects.create(name="Socialisation")
        self.comparaison = ComparaisonDomaineVineland.objects.create(
            age='7-18', niveau_significativite='.05',
            domaine1=self.domaine_a, domaine2=self.domaine_b, difference_requise=15,
        )
        self.frequence = FrequenceDifferenceDomaineVineland.objects.create(
            age='7-18', domaine1=self.domaine_a, domaine2=self.domaine_b,
            frequence_16='5', frequence_10='10', frequence_5='15',
        )

    def test_trouve_dans_lordre_enregistre(self):
        result = find_domain_comparison(self.domaine_a, self.domaine_b, '7-18', '.05')
        self.assertEqual(result, self.comparaison)

    def test_trouve_dans_lordre_inverse(self):
        result = find_domain_comparison(self.domaine_b, self.domaine_a, '7-18', '.05')
        self.assertEqual(result, self.comparaison)

    def test_aucune_comparaison_retourne_none(self):
        autre_domaine = Domain.objects.create(name="Motricité")
        result = find_domain_comparison(self.domaine_a, autre_domaine, '7-18', '.05')
        self.assertIsNone(result)

    def test_frequence_trouvee_dans_les_deux_sens(self):
        self.assertEqual(find_domain_frequency(self.domaine_a, self.domaine_b, '7-18'), self.frequence)
        self.assertEqual(find_domain_frequency(self.domaine_b, self.domaine_a, '7-18'), self.frequence)


class FindSousDomaineComparisonAndFrequencyTests(TestCase):

    def setUp(self):
        domaine = Domain.objects.create(name="Communication")
        self.sd_a = SousDomain.objects.create(domain=domaine, name="Réceptif")
        self.sd_b = SousDomain.objects.create(domain=domaine, name="Expressif")
        self.comparaison = ComparaisonSousDomaineVineland.objects.create(
            age='7-18', niveau_significativite='.05',
            sous_domaine1=self.sd_a, sous_domaine2=self.sd_b, difference_requise=4,
        )
        self.frequence = FrequenceDifferenceSousDomaineVineland.objects.create(
            age='7-18', sous_domaine1=self.sd_a, sous_domaine2=self.sd_b,
            frequence_16='2', frequence_10='4', frequence_5='6',
        )

    def test_trouve_dans_les_deux_sens(self):
        self.assertEqual(find_sous_domaine_comparison(self.sd_a, self.sd_b, '7-18', '.05'), self.comparaison)
        self.assertEqual(find_sous_domaine_comparison(self.sd_b, self.sd_a, '7-18', '.05'), self.comparaison)

    def test_frequence_trouvee_dans_les_deux_sens(self):
        self.assertEqual(find_sous_domaine_frequency(self.sd_a, self.sd_b, '7-18'), self.frequence)
        self.assertEqual(find_sous_domaine_frequency(self.sd_b, self.sd_a, '7-18'), self.frequence)

    def test_aucune_comparaison_retourne_none(self):
        autre_sd = SousDomain.objects.create(domain=self.sd_a.domain, name="Écrit")
        self.assertIsNone(find_sous_domaine_comparison(self.sd_a, autre_sd, '7-18', '.05'))


class GenerateDomainComparisonsTests(TestCase):

    def setUp(self):
        self.domaine_a = Domain.objects.create(name="Communication")
        self.domaine_b = Domain.objects.create(name="Socialisation")
        ComparaisonDomaineVineland.objects.create(
            age='7-18', niveau_significativite='.05',
            domaine1=self.domaine_a, domaine2=self.domaine_b, difference_requise=10,
        )
        self.domaine_scores = {
            'Communication': {'note_standard': 100, 'domaine_obj': self.domaine_a},
            'Socialisation': {'note_standard': 85, 'domaine_obj': self.domaine_b},
        }

    def test_comparaison_significative_si_difference_atteint_le_seuil(self):
        comparisons = generate_domain_comparisons(self.domaine_scores, '7-18', '7-18', '.05')

        self.assertEqual(len(comparisons), 1)
        comp = comparisons[0]
        self.assertEqual(comp['difference'], 15)
        self.assertEqual(comp['signe'], '>')
        self.assertTrue(comp['est_significatif'])
        self.assertEqual(comp['difference_requise'], 10)

    def test_pas_significative_si_sous_le_seuil(self):
        self.domaine_scores['Socialisation']['note_standard'] = 95  # différence = 5 < 10

        comparisons = generate_domain_comparisons(self.domaine_scores, '7-18', '7-18', '.05')

        self.assertFalse(comparisons[0]['est_significatif'])

    def test_sans_comparaison_en_base_difference_requise_est_none(self):
        domaine_c = Domain.objects.create(name="Motricité")
        scores = {
            'Communication': {'note_standard': 100, 'domaine_obj': self.domaine_a},
            'Motricité': {'note_standard': 80, 'domaine_obj': domaine_c},
        }

        comparisons = generate_domain_comparisons(scores, '7-18', '7-18', '.05')

        self.assertIsNone(comparisons[0]['difference_requise'])
        self.assertFalse(comparisons[0]['est_significatif'])


class GenerateSousDomaineComparisonsTests(TestCase):
    """Vérifie que les sous-domaines sont comparés PAR PAIRES au sein du MÊME domaine uniquement."""

    def setUp(self):
        self.domaine_comm = Domain.objects.create(name="Communication")
        self.domaine_socio = Domain.objects.create(name="Socialisation")
        self.sd_receptif = SousDomain.objects.create(domain=self.domaine_comm, name="Réceptif")
        self.sd_expressif = SousDomain.objects.create(domain=self.domaine_comm, name="Expressif")
        self.sd_relations = SousDomain.objects.create(domain=self.domaine_socio, name="Relations")

        self.sous_domaine_scores = {
            'Réceptif': {'note_echelle_v': 15, 'domaine': 'Communication', 'sous_domaine_obj': self.sd_receptif},
            'Expressif': {'note_echelle_v': 10, 'domaine': 'Communication', 'sous_domaine_obj': self.sd_expressif},
            'Relations': {'note_echelle_v': 12, 'domaine': 'Socialisation', 'sous_domaine_obj': self.sd_relations},
        }

    def test_regroupe_par_domaine_et_ne_compare_que_dans_le_meme_domaine(self):
        result = generate_sous_domaine_comparisons(self.sous_domaine_scores, '7-18', '.05')

        self.assertEqual(set(result.keys()), {'Communication', 'Socialisation'})
        self.assertEqual(len(result['Communication']), 1)  # Réceptif vs Expressif
        self.assertEqual(len(result['Socialisation']), 0)  # un seul sous-domaine, aucune paire

        comp = result['Communication'][0]
        self.assertEqual({comp['sous_domaine1'], comp['sous_domaine2']}, {'Réceptif', 'Expressif'})
        self.assertEqual(comp['difference'], 5)


class GenerateInterdomaineComparisonsTests(TestCase):
    """Vérifie que SEULES les paires de sous-domaines de domaines DIFFÉRENTS sont comparées."""

    def setUp(self):
        domaine_comm = Domain.objects.create(name="Communication")
        domaine_socio = Domain.objects.create(name="Socialisation")
        self.sd_receptif = SousDomain.objects.create(domain=domaine_comm, name="Réceptif")
        self.sd_expressif = SousDomain.objects.create(domain=domaine_comm, name="Expressif")
        self.sd_relations = SousDomain.objects.create(domain=domaine_socio, name="Relations")

        self.sous_domaine_scores = {
            'Réceptif': {'note_echelle_v': 15, 'domaine': 'Communication', 'sous_domaine_obj': self.sd_receptif},
            'Expressif': {'note_echelle_v': 10, 'domaine': 'Communication', 'sous_domaine_obj': self.sd_expressif},
            'Relations': {'note_echelle_v': 12, 'domaine': 'Socialisation', 'sous_domaine_obj': self.sd_relations},
        }

    def test_exclut_les_paires_du_meme_domaine(self):
        comparisons = generate_interdomaine_comparisons(self.sous_domaine_scores, '7-18', '.05')

        # 3 sous-domaines -> 3 paires possibles, mais 1 seule est inter-domaine
        # (Réceptif vs Expressif sont dans le même domaine et doivent être exclus)
        paires = {frozenset([c['sous_domaine1'], c['sous_domaine2']]) for c in comparisons}
        self.assertNotIn(frozenset(['Réceptif', 'Expressif']), paires)
        self.assertEqual(len(comparisons), 2)  # Réceptif-Relations et Expressif-Relations
