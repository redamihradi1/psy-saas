from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, License, User
from cabinet.models import Patient, Anamnese


class AnamneseTestCaseBase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Cabinet Test", slug="cabinet-test")
        License.objects.create(organization=self.organization, plan='lifetime', status='active')
        self.user = User.objects.create_user(
            username="psy", password="test-pass-123", role='psychologist', organization=self.organization
        )
        self.patient = Patient.objects.create(
            organization=self.organization, nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1)
        )
        self.client.force_login(self.user)


class AnamneseCreateTests(AnamneseTestCaseBase):
    """
    Régression : anamnese_create était définie deux fois dans cabinet/views.py.
    La première version (jamais exécutée) ne vérifiait pas l'existence
    préalable et ne sauvegardait qu'une poignée de champs. Ces tests
    verrouillent le comportement de la version réellement active.
    """

    def test_creation_sauvegarde_tous_les_champs_textuels(self):
        response = self.client.post(
            reverse('cabinet:anamnese_create', kwargs={'patient_id': self.patient.id}),
            {
                'motif_consultation': 'Anxiété généralisée',
                'antecedents_medicaux': 'RAS',
                'antecedents_familiaux': 'Dépression maternelle',
                'medicaments_actuels': 'Aucun',
                'situation_professionnelle': 'Cadre',
                'situation_familiale': 'Marié, 2 enfants',
                'troubles_sommeil': 'Insomnies',
                'troubles_alimentaires': '',
                'activite_physique': 'Course à pied',
                'hobbies_bien_etre': 'Lecture',
                'changements_souhaites': 'Moins de stress',
                'consommation_substances': 'Aucune',
                'niveau_stress': '8',
                'objectifs_therapie': 'Gérer le stress',
                'attentes_patient': 'Outils concrets',
                'contraintes_horaires': 'Soirées uniquement',
                'deja_consulte_psy': 'true',
            },
        )

        anamnese = Anamnese.objects.get(patient=self.patient)
        self.assertRedirects(response, reverse('cabinet:patient_detail', kwargs={'patient_id': self.patient.id}))
        self.assertEqual(anamnese.antecedents_familiaux, 'Dépression maternelle')
        self.assertEqual(anamnese.troubles_sommeil, 'Insomnies')
        self.assertEqual(anamnese.niveau_stress, 8)
        self.assertTrue(anamnese.deja_consulte_psy)
        self.assertEqual(anamnese.organization, self.organization)

    def test_deja_consulte_psy_false_si_case_non_cochee(self):
        self.client.post(
            reverse('cabinet:anamnese_create', kwargs={'patient_id': self.patient.id}),
            {'motif_consultation': 'x', 'niveau_stress': '5'},
        )

        anamnese = Anamnese.objects.get(patient=self.patient)
        self.assertFalse(anamnese.deja_consulte_psy)

    def test_ne_cree_pas_de_doublon_si_anamnese_existe_deja(self):
        Anamnese.objects.create(
            organization=self.organization, patient=self.patient, motif_consultation="Première anamnèse"
        )

        response = self.client.get(reverse('cabinet:anamnese_create', kwargs={'patient_id': self.patient.id}))

        self.assertRedirects(response, reverse('cabinet:patient_detail', kwargs={'patient_id': self.patient.id}))
        self.assertEqual(Anamnese.objects.filter(patient=self.patient).count(), 1)


class AnamneseEditTests(AnamneseTestCaseBase):

    def setUp(self):
        super().setUp()
        self.anamnese = Anamnese.objects.create(
            organization=self.organization, patient=self.patient, motif_consultation="Motif initial"
        )

    def test_edition_met_a_jour_les_champs(self):
        response = self.client.post(
            reverse('cabinet:anamnese_edit', kwargs={'patient_id': self.patient.id}),
            {'motif_consultation': 'Motif mis à jour', 'niveau_stress': '3'},
        )

        self.anamnese.refresh_from_db()
        self.assertRedirects(response, reverse('cabinet:patient_detail', kwargs={'patient_id': self.patient.id}))
        self.assertEqual(self.anamnese.motif_consultation, 'Motif mis à jour')
        self.assertEqual(self.anamnese.niveau_stress, 3)
