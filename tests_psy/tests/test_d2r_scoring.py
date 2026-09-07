from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, License, User
from cabinet.models import Patient
from tests_psy.models import (
    TestD2R, SymboleReference, NormeExactitude, NormeRythmeTraitement, NormeCapaciteConcentration
)


class D2RTestCaseBase(TestCase):
    """
    Le scoring D2R n'est pas dans une méthode de modèle (contrairement à
    Beck/STAI) mais directement dans les vues d2r_submit/d2r_resultats.
    On teste donc les vraies vues via le client de test, pas une
    réimplémentation du calcul.
    """

    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(
            organization=self.organization, plan='lifetime', status='active', has_d2r=True
        )
        self.user = User.objects.create_user(
            username="psy", password="test-pass-123", role='psychologist', organization=self.organization
        )
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance="1999-01-01"
        )
        self.client.force_login(self.user)


class D2RSubmitScoringTests(D2RTestCaseBase):
    """
    Scénario ligne 2 (positions auto-assignées dans l'ordre de création) :
      pos1: 'd', traits=1+1=2  -> cible
      pos2: 'd', traits=2+0=2  -> cible
      pos3: 'p', traits=1+1=2  -> pas une cible (mauvaise lettre)
      pos4: 'd', traits=0+1=1  -> pas une cible (mauvais nb de traits)
      pos5: 'd', traits=1+1=2  -> cible

    Le patient coche pos1 (cible, correct) et pos3 (pas cible, erreur).
    Dernière position cochée = 3, donc seules pos1/2/3 sont examinées :
    pos2 (cible non cochée) devient une omission ; pos4/5 sont ignorées
    car au-delà de la dernière coche.
    """

    def setUp(self):
        super().setUp()
        self.test_d2r = TestD2R.objects.create(
            organization=self.organization, patient=self.patient, code="D2R-1",
            date="2024-01-01", age=25, sexe='M', correction_vue='NO', lateralite='D',
        )
        self.pos1 = SymboleReference.objects.create(page=1, ligne=2, lettre='d', traits_haut=1, traits_bas=1)
        self.pos2 = SymboleReference.objects.create(page=1, ligne=2, lettre='d', traits_haut=2, traits_bas=0)
        self.pos3 = SymboleReference.objects.create(page=1, ligne=2, lettre='p', traits_haut=1, traits_bas=1)
        self.pos4 = SymboleReference.objects.create(page=1, ligne=2, lettre='d', traits_haut=0, traits_bas=1)
        self.pos5 = SymboleReference.objects.create(page=1, ligne=2, lettre='d', traits_haut=1, traits_bas=1)

    def _submit(self, selected_ids, temps_total=600):
        url = reverse('tests_psy:d2r_submit', kwargs={'test_id': self.test_d2r.id})
        selected_str = ','.join(str(i) for i in selected_ids)
        return self.client.post(url, {'selected_symbols': selected_str, 'temps_total': str(temps_total)})

    def test_comptage_correct_incorrect_omission(self):
        self._submit([self.pos1.id, self.pos3.id])
        self.test_d2r.refresh_from_db()

        self.assertEqual(self.test_d2r.reponses_correctes, 1)
        self.assertEqual(self.test_d2r.reponses_incorrectes, 1)
        self.assertEqual(self.test_d2r.reponses_omises, 1)
        self.assertEqual(self.test_d2r.temps_total, 600)

    def test_note_cct_et_capacite_concentration(self):
        self._submit([self.pos1.id, self.pos3.id])
        self.test_d2r.refresh_from_db()

        self.assertEqual(self.test_d2r.note_cct, 1)
        self.assertEqual(float(self.test_d2r.note_exactitude), 200.0)  # (1 incorrect + 1 omission) / 1 correct * 100
        self.assertEqual(self.test_d2r.capacite_concentration, -1)  # 1 - 1 - 1

    def test_symboles_au_dela_de_la_derniere_coche_sont_ignores(self):
        """pos4 et pos5 (après la dernière coche à pos3) ne doivent pas être comptés du tout."""
        self._submit([self.pos1.id, self.pos3.id])
        self.test_d2r.refresh_from_db()

        total_examine = (
            self.test_d2r.reponses_correctes
            + self.test_d2r.reponses_incorrectes
            + self.test_d2r.reponses_omises
        )
        self.assertEqual(total_examine, 3)  # seulement pos1, pos2, pos3

    def test_ligne_sans_aucune_coche_est_totalement_ignoree(self):
        """Une ligne où le patient n'a rien coché ne doit générer aucune omission,
        même si elle contient des cibles non cochées."""
        SymboleReference.objects.create(page=1, ligne=3, lettre='d', traits_haut=1, traits_bas=1)

        self._submit([self.pos1.id, self.pos3.id])  # rien sélectionné sur la ligne 3
        self.test_d2r.refresh_from_db()

        self.assertEqual(self.test_d2r.reponses_omises, 1)  # inchangé, pas +1 pour la ligne 3

    def test_aucune_reponse_correcte_note_exactitude_est_zero_pas_une_division_par_zero(self):
        """Cas limite : total_correctes=0 doit donner note_exactitude=0, pas une exception."""
        self._submit([self.pos3.id])  # seule une réponse incorrecte est cochée
        self.test_d2r.refresh_from_db()

        self.assertEqual(self.test_d2r.reponses_correctes, 0)
        self.assertEqual(float(self.test_d2r.note_exactitude), 0.0)


class D2RResultatsNormesTests(D2RTestCaseBase):
    """Vérifie que les bonnes normes (note standard / percentile) sont retrouvées par âge et par score."""

    def setUp(self):
        super().setUp()
        self.test_d2r = TestD2R.objects.create(
            organization=self.organization, patient=self.patient, code="D2R-1",
            date="2024-01-01", age=25, sexe='M', correction_vue='NO', lateralite='D',
            reponses_correctes=8, reponses_incorrectes=1, reponses_omises=1,
        )
        # cct=8, ec=1, eo=1, cc=6, e_percentage=(1+1)/8*100=25.0
        NormeExactitude.objects.create(
            note_standard=10, percentile=50, age_min=20, age_max=30, valeur_min=20, valeur_max=30
        )
        NormeRythmeTraitement.objects.create(
            note_standard=12, percentile=60, age_min=20, age_max=30, valeur_min=5, valeur_max=10
        )
        NormeCapaciteConcentration.objects.create(
            note_standard=11, percentile=55, age_min=20, age_max=30, valeur_min=5, valeur_max=10
        )

    def _get_resultats(self):
        url = reverse('tests_psy:d2r_resultats', kwargs={'test_id': self.test_d2r.id})
        return self.client.get(url)

    def test_scores_bruts_dans_le_contexte(self):
        response = self._get_resultats()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['cct'], 8)
        self.assertEqual(response.context['ec'], 1)
        self.assertEqual(response.context['eo'], 1)
        self.assertEqual(response.context['cc'], 6)
        self.assertEqual(response.context['e_percentage'], 25.0)

    def test_normes_correspondantes_sont_retrouvees(self):
        response = self._get_resultats()

        self.assertEqual(response.context['note_standard_e'], 10)
        self.assertEqual(response.context['note_standard_cct'], 12)
        self.assertEqual(response.context['note_standard_cc'], 11)

    def test_aucune_norme_hors_plage_dage_retourne_none(self):
        self.test_d2r.age = 99
        self.test_d2r.save()

        response = self._get_resultats()

        self.assertIsNone(response.context['note_standard_e'])
        self.assertIsNone(response.context['note_standard_cct'])
        self.assertIsNone(response.context['note_standard_cc'])
