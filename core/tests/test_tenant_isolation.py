from django.test import TestCase

from accounts.models import Organization
from cabinet.models import Patient
from core.middleware import get_current_tenant, set_current_tenant


class TenantManagerIsolationTests(TestCase):
    """
    Vérifie que le TenantManager (utilisé par tous les modèles métier :
    Patient, Consultation, tests psychométriques...) isole correctement les
    données par organisation. C'est la garantie de base du multi-cabinet :
    un cabinet ne doit jamais voir les patients d'un autre.
    """

    def setUp(self):
        self.org_a = Organization.objects.create(name="Cabinet A", slug="cabinet-a")
        self.org_b = Organization.objects.create(name="Cabinet B", slug="cabinet-b")

        self.patient_a = Patient.objects.create(
            organization=self.org_a, nom="Alpha", prenom="Anna", date_naissance="1990-01-01"
        )
        self.patient_b = Patient.objects.create(
            organization=self.org_b, nom="Beta", prenom="Bruno", date_naissance="1991-02-02"
        )

    def tearDown(self):
        # Le middleware nettoie le tenant après chaque requête ; on fait
        # pareil ici pour ne pas fuiter d'état entre tests.
        set_current_tenant(None)

    def test_sans_tenant_actif_aucun_filtrage(self):
        """Hors contexte de requête (ex: scripts, admin superadmin), pas de filtrage."""
        set_current_tenant(None)
        self.assertEqual(Patient.objects.count(), 2)

    def test_tenant_actif_ne_voit_que_ses_propres_patients(self):
        set_current_tenant(self.org_a)
        patients = list(Patient.objects.all())

        self.assertEqual(patients, [self.patient_a])

    def test_organisation_b_ne_voit_pas_les_patients_de_a(self):
        set_current_tenant(self.org_b)
        patients = list(Patient.objects.all())

        self.assertEqual(patients, [self.patient_b])
        self.assertNotIn(self.patient_a, patients)

    def test_all_objects_ignore_le_filtrage_tenant(self):
        """Le manager all_objects (superadmin) doit voir tous les patients."""
        set_current_tenant(self.org_a)
        self.assertEqual(Patient.all_objects.count(), 2)

    def test_get_object_dune_autre_organisation_leve_does_not_exist(self):
        set_current_tenant(self.org_a)
        with self.assertRaises(Patient.DoesNotExist):
            Patient.objects.get(pk=self.patient_b.pk)


class TenantModelAutoAssignTests(TestCase):
    """
    Vérifie que TenantModel.save() assigne automatiquement l'organisation
    courante quand elle n'est pas fournie explicitement (utilisé par les
    vues qui créent des objets sans passer organization= à la main).
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Cabinet C", slug="cabinet-c")

    def tearDown(self):
        set_current_tenant(None)

    def test_organisation_auto_assignee_depuis_le_tenant_courant(self):
        set_current_tenant(self.org)
        patient = Patient(nom="Curie", prenom="Marie", date_naissance="1990-01-01")
        patient.save()

        self.assertEqual(patient.organization, self.org)

    def test_organisation_explicite_prioritaire_sur_le_tenant_courant(self):
        autre_org = Organization.objects.create(name="Cabinet D", slug="cabinet-d")
        set_current_tenant(self.org)

        patient = Patient(
            organization=autre_org, nom="Curie", prenom="Marie", date_naissance="1990-01-01"
        )
        patient.save()

        self.assertEqual(patient.organization, autre_org)

    def test_aucune_organisation_sans_tenant_courant_leve_une_erreur(self):
        set_current_tenant(None)
        patient = Patient(nom="Curie", prenom="Marie", date_naissance="1990-01-01")

        with self.assertRaises(Exception):
            patient.save()
