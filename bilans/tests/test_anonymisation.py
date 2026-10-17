from types import SimpleNamespace

from django.test import SimpleTestCase

from bilans.anonymisation import Pseudonymiseur


def _patient(prenom='Yasmine', nom='El Idrissi'):
    return SimpleNamespace(prenom=prenom, nom=nom)


def _psy():
    return SimpleNamespace(first_name='Manal', last_name='Moussaid', username='manal',
                           get_full_name=lambda: 'Manal Moussaid')


class PseudonymiseurTests(SimpleTestCase):

    def setUp(self):
        self.pseudo = Pseudonymiseur(_patient(), _psy(), SimpleNamespace(name='Cabinet Sérénité'),
                                     autres_noms={'Grace', 'Omar', 'Al'})

    def test_masque_patient_psy_cabinet_et_coordonnees(self):
        texte = ("Yasmine El Idrissi (yasmine) est suivie par Manal Moussaid au Cabinet Sérénité. "
                 "Mme Moussaid joignable au 06 12 34 56 78 ou yas@mail.ma. YASMINE dit que sa mère...")
        masque = self.pseudo.masquer(texte)
        for interdit in ('Yasmine', 'yasmine', 'YASMINE', 'El Idrissi', 'Manal', 'Moussaid', 'Sérénité',
                         '06 12 34 56 78', 'yas@mail.ma'):
            self.assertNotIn(interdit, masque)
        self.assertIn('[PRÉNOM] [NOM]', masque)
        self.assertIn('[PSYCHOLOGUE]', masque)
        self.assertIn('[CABINET]', masque)
        self.assertIn('[TÉLÉPHONE]', masque)
        self.assertIn('[EMAIL]', masque)

    def test_insensible_aux_accents_et_mots_entiers(self):
        pseudo = Pseudonymiseur(_patient('Hélène', 'Benani'))
        masque = pseudo.masquer("Helene et HÉLÈNE ; Benaniya n'est pas concerné.")
        self.assertEqual(masque, "[PRÉNOM] et [PRÉNOM] ; Benaniya n'est pas concerné.")

    def test_autres_patients_masques_puis_restaures_a_l_identique(self):
        masque = self.pseudo.masquer("Son frère Omar l'aide ; grâce à lui, ça va. Al reste.")
        self.assertNotIn('Omar', masque)
        self.assertNotIn('grâce', masque)
        self.assertIn('Al reste', masque)  # 2 lettres : trop court pour un autre patient
        self.assertEqual(self.pseudo.restaurer(masque), "Son frère Omar l'aide ; grâce à lui, ça va. Al reste.")

    def test_restaure_les_etiquettes_de_l_ia(self):
        self.pseudo.masquer("rien")
        texte = self.pseudo.restaurer("[PRÉNOM] [NOM] a été vue par [PSYCHOLOGUE] ([CABINET]). [prenom] progresse.")
        self.assertEqual(texte, "Yasmine El Idrissi a été vue par Manal Moussaid (Cabinet Sérénité). Yasmine progresse.")

    def test_les_scores_ne_sont_pas_pris_pour_des_telephones(self):
        texte = "| Inhibition | 12 | 65 | 93 | 58-72 | ; scores 12 13 14 15"
        self.assertEqual(self.pseudo.masquer(texte), texte)

