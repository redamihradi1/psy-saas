from django.test import TestCase

from accounts.models import Organization
from cabinet.models import Patient
from tests_psy.models import ItemSTAI, TestSTAI, ReponseItemSTAI


class ReponseItemSTAIScoringTests(TestCase):
    """
    Vérifie l'inversion de score par item (5 - valeur si est_inverse).

    Régression : import_stai_data.py avait tous les items à
    est_inverse=True, ce qui inversait le score d'anxiété pour la moitié
    des items. Ces tests figent le comportement attendu du modèle.
    """

    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        self.patient = Patient.objects.create(
            organization=self.organization,
            nom="Dupont",
            prenom="Jean",
            date_naissance="1990-01-01",
        )
        self.test_stai = TestSTAI.objects.create(organization=self.organization, patient=self.patient)

    def _reponse(self, numero, section, est_inverse, valeur_choisie):
        item = ItemSTAI.objects.create(
            numero=numero, texte=f"Item {numero}", section=section, est_inverse=est_inverse
        )
        return ReponseItemSTAI.objects.create(
            organization=self.organization,
            test=self.test_stai,
            item=item,
            valeur_choisie=valeur_choisie,
        )

    def test_item_normal_score_egale_valeur_choisie(self):
        reponse = self._reponse(numero=3, section='ETAT', est_inverse=False, valeur_choisie=3)
        reponse.calculer_score()
        self.assertEqual(reponse.score_calcule, 3)

    def test_item_inverse_score_est_inverse(self):
        reponse = self._reponse(numero=1, section='ETAT', est_inverse=True, valeur_choisie=3)
        reponse.calculer_score()
        self.assertEqual(reponse.score_calcule, 2)  # 5 - 3

    def test_item_inverse_bornes(self):
        cases = {1: 4, 2: 3, 3: 2, 4: 1}
        for valeur, attendu in cases.items():
            item = ItemSTAI.objects.create(
                numero=100 + valeur, texte="x", section='ETAT', est_inverse=True
            )
            reponse = ReponseItemSTAI.objects.create(
                organization=self.organization, test=self.test_stai, item=item, valeur_choisie=valeur
            )
            reponse.calculer_score()
            self.assertEqual(reponse.score_calcule, attendu)


class TestSTAIScoringTests(TestCase):
    """Vérifie l'agrégation des scores ÉTAT/TRAIT et les seuils de niveau d'anxiété."""

    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        self.patient = Patient.objects.create(
            organization=self.organization,
            nom="Dupont",
            prenom="Jean",
            date_naissance="1990-01-01",
        )
        self.test_stai = TestSTAI.objects.create(organization=self.organization, patient=self.patient)

    def _ajouter_reponse(self, numero, section, est_inverse, valeur_choisie):
        item = ItemSTAI.objects.create(
            numero=numero, texte=f"Item {numero}", section=section, est_inverse=est_inverse
        )
        reponse = ReponseItemSTAI.objects.create(
            organization=self.organization, test=self.test_stai, item=item, valeur_choisie=valeur_choisie
        )
        reponse.calculer_score()
        return reponse

    def test_calcul_scores_separe_etat_et_trait(self):
        # 20 items ÉTAT à 2 points chacun -> score_etat = 40
        for i in range(1, 21):
            self._ajouter_reponse(i, 'ETAT', est_inverse=False, valeur_choisie=2)
        # 20 items TRAIT à 3 points chacun -> score_trait = 60
        for i in range(21, 41):
            self._ajouter_reponse(i, 'TRAIT', est_inverse=False, valeur_choisie=3)

        score_etat, score_trait = self.test_stai.calculer_scores()

        self.assertEqual(score_etat, 40)
        self.assertEqual(score_trait, 60)

    def test_niveaux_anxiete_seuils(self):
        cases = {
            15: 'invalide',
            20: 'minimale',
            35: 'minimale',
            36: 'faible',
            45: 'faible',
            46: 'moderee',
            55: 'moderee',
            56: 'elevee',
            65: 'elevee',
            66: 'tres_elevee',
        }
        for score, niveau_attendu in cases.items():
            self.assertEqual(self.test_stai.get_niveau_anxiete(score), niveau_attendu)
