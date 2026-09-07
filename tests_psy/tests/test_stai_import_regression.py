from django.test import TestCase

from tests_psy.models import ItemSTAI


class ImportSTAIDataRegressionTests(TestCase):
    """
    Régression directe sur le bug corrigé dans import_stai_data.py :
    les 40 items s'étaient tous retrouvés avec est_inverse=True, alors que
    seuls 19 items (affirmations positives) doivent être inversés selon le
    barème officiel du STAI de Spielberger.

    Ce test exécute le script d'import réel (pas une réimplémentation) pour
    garantir que toute régression future y sera détectée.
    """

    ITEMS_INVERSES_ATTENDUS_ETAT = {1, 2, 5, 8, 10, 11, 15, 16, 19, 20}
    ITEMS_INVERSES_ATTENDUS_TRAIT = {21, 23, 26, 27, 30, 33, 34, 36, 39}

    def test_import_produit_exactement_19_items_inverses(self):
        from import_stai_data import import_items_stai

        import_items_stai()

        items_inverses = set(ItemSTAI.objects.filter(est_inverse=True).values_list('numero', flat=True))
        attendus = self.ITEMS_INVERSES_ATTENDUS_ETAT | self.ITEMS_INVERSES_ATTENDUS_TRAIT

        self.assertEqual(ItemSTAI.objects.count(), 40)
        self.assertEqual(len(attendus), 19)
        self.assertEqual(items_inverses, attendus)
