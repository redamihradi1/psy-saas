"""
Test BRIEF (fonctions exécutives, Forme Parent), découpé en modules comme Vineland :
- scoring: cotation (scores bruts, indices, validité, normes)
- views: vues authentifiées (liste, création 3 modes, passation, résultats...)
- public: lien public envoyé au parent (aucune authentification)
- pdf: rapport PDF
"""
from .views import (
    brief_liste, brief_nouveau, brief_questionnaire, brief_notes_importees, brief_resultats,
    brief_lien_genere, brief_reouvrir_lien, brief_delete,
)
from .pdf import brief_pdf

__all__ = [
    'brief_liste', 'brief_nouveau', 'brief_questionnaire', 'brief_notes_importees', 'brief_resultats',
    'brief_lien_genere', 'brief_reouvrir_lien', 'brief_delete', 'brief_pdf',
]
