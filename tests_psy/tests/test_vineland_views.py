from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Organization, License, User
from cabinet.models import Patient
from tests_psy.models import (
    Domain, SousDomain, QuestionVineland, ReponseVineland, TestVineland,
    EchelleVMapping, NoteDomaineVMapping, ComparaisonDomaineVineland,
    FrequenceDifferenceDomaineVineland, IntervaleConfianceSousDomaine,
    IntervaleConfianceDomaine, NiveauAdaptatif, AgeEquivalentSousDomaine,
)


class VinelandTestCaseBase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(
            organization=self.organization, plan='lifetime', status='active',
            has_vineland=True, max_tests_vineland=0,
        )
        self.user = User.objects.create_user(
            username="psy", password="test-pass-123", role='psychologist', organization=self.organization
        )
        # Anniversaire pile pour avoir un âge exact et déterministe au moment du test.
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date(2016, 1, 1)
        )
        self.client.force_login(self.user)


class VinelandNouveauTests(VinelandTestCaseBase):

    def test_creation_redirige_vers_le_questionnaire(self):
        url = reverse('tests_psy:vineland_nouveau')
        response = self.client.post(url, {'patient': self.patient.id})

        test = TestVineland.objects.get(patient=self.patient)
        self.assertRedirects(response, reverse('tests_psy:vineland_questionnaire', kwargs={'test_id': test.id}))
        self.assertEqual(test.organization, self.organization)
        self.assertEqual(test.psychologue, self.user)

    def test_quota_atteint_bloque_la_creation(self):
        license = self.organization.license
        license.max_tests_vineland = 1
        license.save()
        TestVineland.objects.create(organization=self.organization, patient=self.patient, psychologue=self.user)

        url = reverse('tests_psy:vineland_nouveau')
        response = self.client.post(url, {'patient': self.patient.id}, follow=True)

        self.assertRedirects(response, reverse('tests_psy:vineland_liste'))
        self.assertEqual(TestVineland.objects.count(), 1)  # pas de 2e test créé

    def test_liste_ne_plante_pas_si_aucun_psychologue_assigne(self):
        """
        Régression : le champ psychologue est nullable (SET_NULL si le compte est
        supprimé). templates/tests_psy/vineland/liste.html utilisait
        `{{ test.psychologue.get_full_name|default:test.psychologue.username }}` -
        l'argument d'un filtre n'est PAS protégé contre l'échec de résolution par
        Django (contrairement à la variable principale), donc `test.psychologue.username`
        avec psychologue=None faisait planter la page (500) plutôt que d'afficher un tiret.
        """
        TestVineland.objects.create(organization=self.organization, patient=self.patient, psychologue=None)

        response = self.client.get(reverse('tests_psy:vineland_liste'))

        self.assertEqual(response.status_code, 200)


class VinelandQuestionnaireTests(VinelandTestCaseBase):

    def setUp(self):
        super().setUp()
        self.test_vineland = TestVineland.objects.create(organization=self.organization, patient=self.patient)
        domain = Domain.objects.create(name="Communication")
        self.sous_domaine = SousDomain.objects.create(domain=domain, name="Réceptif")
        self.q1 = QuestionVineland.objects.create(sous_domaine=self.sous_domaine, texte="Q1", numero_item=1)
        self.q2 = QuestionVineland.objects.create(sous_domaine=self.sous_domaine, texte="Q2", numero_item=2)

    def _url(self):
        return reverse('tests_psy:vineland_questionnaire', kwargs={'test_id': self.test_vineland.id})

    def test_soumission_sauvegarde_les_reponses(self):
        key1 = f'question_{self.sous_domaine.id}_1'
        key2 = f'question_{self.sous_domaine.id}_2'
        self.client.post(self._url(), {key1: '2', key2: '1', 'action': 'submit'})

        reponse1 = ReponseVineland.objects.get(test_vineland=self.test_vineland, question=self.q1)
        reponse2 = ReponseVineland.objects.get(test_vineland=self.test_vineland, question=self.q2)
        self.assertEqual(reponse1.reponse, '2')
        self.assertEqual(reponse2.reponse, '1')

    def test_soumission_submit_redirige_vers_scores(self):
        key1 = f'question_{self.sous_domaine.id}_1'
        key2 = f'question_{self.sous_domaine.id}_2'
        response = self.client.post(self._url(), {key1: '2', key2: '1', 'action': 'submit'})

        self.assertRedirects(response, reverse('tests_psy:vineland_scores', kwargs={'test_id': self.test_vineland.id}))

    def test_reponse_existante_est_mise_a_jour_pas_dupliquee(self):
        key1 = f'question_{self.sous_domaine.id}_1'
        self.client.post(self._url(), {key1: '1', 'action': 'next'})
        self.client.post(self._url(), {key1: '2', 'action': 'next'})

        self.assertEqual(ReponseVineland.objects.filter(test_vineland=self.test_vineland, question=self.q1).count(), 1)
        self.assertEqual(
            ReponseVineland.objects.get(test_vineland=self.test_vineland, question=self.q1).reponse, '2'
        )

    def test_reponses_precedentes_prechargees_dans_le_contexte(self):
        ReponseVineland.objects.create(
            organization=self.organization, test_vineland=self.test_vineland, question=self.q1, reponse='2'
        )
        response = self.client.get(self._url())

        key1 = f'question_{self.sous_domaine.id}_1'
        self.assertEqual(response.context['initial_data'].get(key1), '2')


class VinelandFullPipelineTests(VinelandTestCaseBase):
    """
    Construit un jeu de données complet (2 domaines x 2 sous-domaines) pour
    exercer le pipeline de bout en bout : scores bruts -> échelle-V ->
    scores de domaine -> comparaisons -> PDF, via les vraies vues.
    """

    def setUp(self):
        super().setUp()
        # Âge exactement 8 ans -> tranche_age='7-18', tranche_age_intervalle='7-8', tranche_age_simple='7-8'
        self.test_vineland = TestVineland.objects.create(
            organization=self.organization, patient=self.patient,
            date_passation=timezone.make_aware(timezone.datetime(2024, 1, 1)),
        )

        self.domaine_comm = Domain.objects.create(name="Communication")
        self.domaine_socio = Domain.objects.create(name="Socialisation")
        self.sd_receptif = SousDomain.objects.create(domain=self.domaine_comm, name="Réceptif")
        self.sd_expressif = SousDomain.objects.create(domain=self.domaine_comm, name="Expressif")
        self.sd_relations = SousDomain.objects.create(domain=self.domaine_socio, name="Relations")
        self.sd_jeu = SousDomain.objects.create(domain=self.domaine_socio, name="Jeu")

        # Réponses -> note_brute = 7 (aucune série de 4 '2' consécutifs, item_plancher=0)
        self._repondre(self.sd_receptif, ['1', '1', '2', '1', '2'])  # somme = 7
        self._repondre(self.sd_expressif, ['1', '1', '1', '1', '1'])  # somme = 5
        self._repondre(self.sd_relations, ['2', '1', '2', '1', '2'])  # somme = 8
        self._repondre(self.sd_jeu, ['1', '1', '2', '1', '1'])  # somme = 6

        # Mappings échelle-V (couvrent l'âge 7-8 ans et les notes brutes ci-dessus)
        for sd, note_v in [(self.sd_receptif, 10), (self.sd_expressif, 8), (self.sd_relations, 9), (self.sd_jeu, 7)]:
            EchelleVMapping.objects.create(
                sous_domaine=sd, age_debut_annee=7, age_debut_mois=0, age_fin_annee=8, age_fin_mois=11,
                note_brute_min=0, note_brute_max=20, note_echelle_v=note_v,
            )
        # Communication: 10+8=18 ; Socialisation: 9+7=16

        NoteDomaineVMapping.objects.create(
            tranche_age='7-18', communication_min=15, communication_max=20,
            note_standard=100, rang_percentile='50',
        )
        NoteDomaineVMapping.objects.create(
            tranche_age='7-18', socialisation_min=10, socialisation_max=18,
            note_standard=95, rang_percentile='45',
        )

        NiveauAdaptatif.objects.create(
            niveau='adapte', echelle_v_min=1, echelle_v_max=24, note_standard_min=1, note_standard_max=200
        )
        IntervaleConfianceSousDomaine.objects.create(
            age='7-8', niveau_confiance=90, sous_domaine=self.sd_receptif, intervalle=2
        )
        IntervaleConfianceDomaine.objects.create(
            age='7-8', niveau_confiance=90, domain=self.domaine_comm, intervalle=6, note_composite=97
        )
        AgeEquivalentSousDomaine.objects.create(
            sous_domaine=self.sd_receptif, note_brute_min=0, note_brute_max=20, age_annees=8
        )

        ComparaisonDomaineVineland.objects.create(
            age='7-8', niveau_significativite='.05',
            domaine1=self.domaine_comm, domaine2=self.domaine_socio, difference_requise=3,
        )
        FrequenceDifferenceDomaineVineland.objects.create(
            age='7-18', domaine1=self.domaine_comm, domaine2=self.domaine_socio,
            frequence_5='4', frequence_10='3', frequence_16='2',
        )

    def _repondre(self, sous_domaine, valeurs):
        for i, v in enumerate(valeurs, start=1):
            question = QuestionVineland.objects.create(sous_domaine=sous_domaine, texte=f"Q{i}", numero_item=i)
            ReponseVineland.objects.create(
                organization=self.organization, test_vineland=self.test_vineland, question=question, reponse=v
            )

    def test_vineland_scores_contient_les_notes_brutes(self):
        url = reverse('tests_psy:vineland_scores', kwargs={'test_id': self.test_vineland.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        scores = response.context['scores']
        self.assertEqual(scores['Communication']['Réceptif']['note_brute'], 7)
        self.assertEqual(scores['Communication']['Expressif']['note_brute'], 5)
        self.assertEqual(scores['Socialisation']['Relations']['note_brute'], 8)
        self.assertEqual(scores['Socialisation']['Jeu']['note_brute'], 6)

    def test_vineland_echelle_v_mappe_correctement(self):
        url = reverse('tests_psy:vineland_echelle_v', kwargs={'test_id': self.test_vineland.id})
        response = self.client.get(url)

        echelle = response.context['echelle_v_scores']
        self.assertEqual(echelle['Communication']['Réceptif']['note_echelle_v'], 10)
        self.assertEqual(echelle['Socialisation']['Jeu']['note_echelle_v'], 7)

    def test_vineland_echelle_v_signale_absence_de_mapping(self):
        # Sous-domaine sans aucun EchelleVMapping défini -> aucune correspondance possible.
        sd_sans_mapping = SousDomain.objects.create(domain=self.domaine_comm, name="Écrit")
        self._repondre(sd_sans_mapping, ['1'])

        url = reverse('tests_psy:vineland_echelle_v', kwargs={'test_id': self.test_vineland.id})
        response = self.client.get(url)

        resultat = response.context['echelle_v_scores']['Communication']['Écrit']
        self.assertIsNone(resultat['note_echelle_v'])
        self.assertEqual(resultat['error'], 'Aucune correspondance trouvée')

    def test_vineland_resultats_scores_de_domaine(self):
        url = reverse('tests_psy:vineland_resultats', kwargs={'test_id': self.test_vineland.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        complete_scores = {d['name']: d for d in response.context['complete_scores']}

        self.assertEqual(complete_scores['Communication']['domain_score']['note_standard'], 100)
        self.assertEqual(complete_scores['Communication']['domain_score']['rang_percentile'], '50')
        self.assertEqual(complete_scores['Communication']['domain_score']['niveau_adaptatif'], 'Adapté')
        self.assertEqual(complete_scores['Communication']['domain_score']['intervalle'], 6)

        self.assertEqual(complete_scores['Socialisation']['domain_score']['note_standard'], 95)

    def test_vineland_resultats_details_sous_domaine(self):
        url = reverse('tests_psy:vineland_resultats', kwargs={'test_id': self.test_vineland.id})
        response = self.client.get(url)

        complete_scores = {d['name']: d for d in response.context['complete_scores']}
        sous_domaines = {sd['name']: sd for sd in complete_scores['Communication']['sous_domaines']}

        self.assertEqual(sous_domaines['Réceptif']['note_echelle_v'], 10)
        self.assertEqual(sous_domaines['Réceptif']['intervalle'], 2)
        self.assertEqual(sous_domaines['Réceptif']['age_equivalent'], '8')
        self.assertEqual(sous_domaines['Réceptif']['niveau_adaptatif'], 'Adapté')

    def test_vineland_resultats_niveau_confiance_invalide_retombe_a_90(self):
        url = reverse('tests_psy:vineland_resultats', kwargs={'test_id': self.test_vineland.id})
        response = self.client.get(url, {'niveau_confiance': '999'})

        self.assertEqual(response.context['niveau_confiance'], 90)

    def test_vineland_comparaisons_domaine_significatif(self):
        url = reverse('tests_psy:vineland_comparaisons', kwargs={'test_id': self.test_vineland.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        comparisons = response.context['domain_comparisons']
        self.assertEqual(len(comparisons), 1)
        comp = comparisons[0]
        self.assertEqual(comp['difference'], 5)
        self.assertTrue(comp['est_significatif'])
        self.assertEqual(comp['frequence'], '5%')

    def test_vineland_pdf_genere_un_document_pdf_valide(self):
        url = reverse('tests_psy:vineland_pdf', kwargs={'test_id': self.test_vineland.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
