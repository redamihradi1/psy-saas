from django.test import TestCase

from accounts.models import Organization
from cabinet.models import Patient
from tests_psy.models import ItemBeck, PhraseBeck, TestBeck, ReponseItemBeck


class ReponseItemBeckScoringTests(TestCase):
    """Vérifie que le score d'un item Beck = MAX des phrases cochées."""

    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        self.patient = Patient.objects.create(
            organization=self.organization,
            nom="Martin",
            prenom="Alice",
            date_naissance="1985-06-15",
        )
        self.test_beck = TestBeck.objects.create(organization=self.organization, patient=self.patient)
        self.item = ItemBeck.objects.create(numero=1, categorie="Tristesse")
        self.phrase_0 = PhraseBeck.objects.create(item=self.item, score_valeur=0, texte="...", ordre=0)
        self.phrase_2 = PhraseBeck.objects.create(item=self.item, score_valeur=2, texte="...", ordre=1)
        self.phrase_3 = PhraseBeck.objects.create(item=self.item, score_valeur=3, texte="...", ordre=2)

    def test_aucune_phrase_cochee_score_zero(self):
        reponse = ReponseItemBeck.objects.create(
            organization=self.organization, test=self.test_beck, item=self.item
        )
        reponse.calculer_score()
        self.assertEqual(reponse.score_item, 0)

    def test_score_est_le_maximum_des_phrases_cochees(self):
        reponse = ReponseItemBeck.objects.create(
            organization=self.organization, test=self.test_beck, item=self.item
        )
        reponse.phrases_cochees.set([self.phrase_0, self.phrase_2])
        reponse.calculer_score()
        self.assertEqual(reponse.score_item, 2)

        reponse.phrases_cochees.add(self.phrase_3)
        reponse.calculer_score()
        self.assertEqual(reponse.score_item, 3)


class TestBeckScoringTests(TestCase):
    """Vérifie le score total, les seuils de niveau de dépression et l'alerte suicide."""

    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        self.patient = Patient.objects.create(
            organization=self.organization,
            nom="Martin",
            prenom="Alice",
            date_naissance="1985-06-15",
        )
        self.test_beck = TestBeck.objects.create(organization=self.organization, patient=self.patient)

    def _ajouter_reponse(self, numero, score_valeur):
        item = ItemBeck.objects.create(numero=numero, categorie=f"Categorie {numero}")
        phrase = PhraseBeck.objects.create(item=item, score_valeur=score_valeur, texte="...", ordre=0)
        reponse = ReponseItemBeck.objects.create(
            organization=self.organization, test=self.test_beck, item=item
        )
        reponse.phrases_cochees.add(phrase)
        reponse.calculer_score()
        return reponse

    def test_score_total_est_la_somme_des_items(self):
        self._ajouter_reponse(1, 2)
        self._ajouter_reponse(2, 3)
        self._ajouter_reponse(3, 1)

        total = self.test_beck.calculer_score_total()

        self.assertEqual(total, 6)

    def test_niveaux_depression_seuils(self):
        cases = {0: 'minimale', 9: 'minimale', 10: 'legere', 18: 'legere', 19: 'moderee', 29: 'moderee', 30: 'severe', 63: 'severe'}
        for score, niveau_attendu in cases.items():
            self.test_beck.score_total = score
            self.assertEqual(self.test_beck.get_niveau_depression(), niveau_attendu)

    def test_alerte_suicide_declenchee_si_item_9_superieur_ou_egal_a_2(self):
        self._ajouter_reponse(9, 2)
        self.test_beck.calculer_score_total()
        self.assertTrue(self.test_beck.alerte_suicide)

    def test_pas_alerte_suicide_si_item_9_faible(self):
        self._ajouter_reponse(9, 1)
        self.test_beck.calculer_score_total()
        self.assertFalse(self.test_beck.alerte_suicide)

    def test_pas_alerte_suicide_si_item_9_absent(self):
        self._ajouter_reponse(1, 3)
        self.test_beck.calculer_score_total()
        self.assertFalse(self.test_beck.alerte_suicide)

    def test_score_pourcentage(self):
        self.test_beck.score_total = 31  # ~49.2% de 63
        self.assertAlmostEqual(self.test_beck.score_pourcentage, 49.2, places=1)
