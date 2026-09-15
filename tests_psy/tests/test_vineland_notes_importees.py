from django.urls import reverse

from tests_psy.models import Domain, SousDomain, TestVineland, NoteBruteImporteeVineland
from tests_psy.views.vineland.scoring import calculate_all_scores, calculate_domain_scores, get_patient_age, get_age_tranches
from .test_vineland_views import VinelandTestCaseBase


class VinelandNotesImporteesTests(VinelandTestCaseBase):

    def setUp(self):
        super().setUp()
        self.domain = Domain.objects.create(name="Communication")
        self.sous_domaine1 = SousDomain.objects.create(domain=self.domain, name="Réceptif")
        self.sous_domaine2 = SousDomain.objects.create(domain=self.domain, name="Expressif")
        self.test_vineland = TestVineland.objects.create(
            organization=self.organization, patient=self.patient, psychologue=self.user, mode='importe',
        )

    def _field_name(self, sous_domaine):
        return f'sous_domaine_{sous_domaine.id}'

    def test_creation_enregistre_une_note_par_sous_domaine(self):
        url = reverse('tests_psy:vineland_notes_importees', kwargs={'test_id': self.test_vineland.id})
        response = self.client.post(url, {
            self._field_name(self.sous_domaine1): 12,
            self._field_name(self.sous_domaine2): 20,
        })

        self.assertRedirects(response, reverse('tests_psy:vineland_scores', kwargs={'test_id': self.test_vineland.id}))
        self.assertEqual(NoteBruteImporteeVineland.objects.filter(test_vineland=self.test_vineland).count(), 2)
        note1 = NoteBruteImporteeVineland.objects.get(test_vineland=self.test_vineland, sous_domaine=self.sous_domaine1)
        self.assertEqual(note1.note_brute, 12)

    def test_resoumission_met_a_jour_sans_dupliquer(self):
        url = reverse('tests_psy:vineland_notes_importees', kwargs={'test_id': self.test_vineland.id})
        self.client.post(url, {
            self._field_name(self.sous_domaine1): 12,
            self._field_name(self.sous_domaine2): 20,
        })
        self.client.post(url, {
            self._field_name(self.sous_domaine1): 15,
            self._field_name(self.sous_domaine2): 20,
        })

        self.assertEqual(NoteBruteImporteeVineland.objects.filter(test_vineland=self.test_vineland).count(), 2)
        note1 = NoteBruteImporteeVineland.objects.get(test_vineland=self.test_vineland, sous_domaine=self.sous_domaine1)
        self.assertEqual(note1.note_brute, 15)

    def test_get_preremplit_les_notes_existantes(self):
        NoteBruteImporteeVineland.objects.create(
            organization=self.organization, test_vineland=self.test_vineland,
            sous_domaine=self.sous_domaine1, note_brute=9,
        )
        url = reverse('tests_psy:vineland_notes_importees', kwargs={'test_id': self.test_vineland.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="9"')

    def test_redirige_si_le_test_n_est_pas_en_mode_importe(self):
        test_cabinet = TestVineland.objects.create(
            organization=self.organization, patient=self.patient, mode='cabinet',
        )
        url = reverse('tests_psy:vineland_notes_importees', kwargs={'test_id': test_cabinet.id})
        response = self.client.get(url)

        self.assertRedirects(response, reverse('tests_psy:vineland_liste'))

    def test_calculate_all_scores_produit_la_meme_forme_que_les_reponses_item_par_item(self):
        NoteBruteImporteeVineland.objects.create(
            organization=self.organization, test_vineland=self.test_vineland,
            sous_domaine=self.sous_domaine1, note_brute=12,
        )
        NoteBruteImporteeVineland.objects.create(
            organization=self.organization, test_vineland=self.test_vineland,
            sous_domaine=self.sous_domaine2, note_brute=20,
        )

        scores = calculate_all_scores(self.test_vineland)
        entry = scores[self.domain.name][self.sous_domaine1.name]

        self.assertEqual(set(entry.keys()), {
            'note_brute', 'item_plancher', 'nsp_count', 'na_count', 'sum_1_2', 'a_refaire', 'items',
        })
        self.assertEqual(entry['note_brute'], 12)
        self.assertEqual(entry['items'], [])
        self.assertIsNone(entry['item_plancher'])

    def test_pages_resultats_rendent_pour_un_test_importe(self):
        NoteBruteImporteeVineland.objects.create(
            organization=self.organization, test_vineland=self.test_vineland,
            sous_domaine=self.sous_domaine1, note_brute=12,
        )
        NoteBruteImporteeVineland.objects.create(
            organization=self.organization, test_vineland=self.test_vineland,
            sous_domaine=self.sous_domaine2, note_brute=20,
        )

        for url_name in ('vineland_scores', 'vineland_resultats', 'vineland_comparaisons'):
            response = self.client.get(reverse(f'tests_psy:{url_name}', kwargs={'test_id': self.test_vineland.id}))
            self.assertEqual(response.status_code, 200, url_name)

    def test_est_complet_une_fois_toutes_les_notes_saisies(self):
        self.assertFalse(self.test_vineland.is_complete)
        NoteBruteImporteeVineland.objects.create(
            organization=self.organization, test_vineland=self.test_vineland,
            sous_domaine=self.sous_domaine1, note_brute=12,
        )
        NoteBruteImporteeVineland.objects.create(
            organization=self.organization, test_vineland=self.test_vineland,
            sous_domaine=self.sous_domaine2, note_brute=20,
        )
        self.assertTrue(self.test_vineland.is_complete)
