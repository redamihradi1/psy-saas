from .dashboard import dashboard_view
from .patients import (
    patients_list,
    patient_create,
    patient_detail,
    patient_edit,
    patient_delete,
)
from .anamnese import anamnese_edit, anamnese_create
from .consultations import (
    consultations_list,
    consultation_create,
    consultation_detail,
    consultation_edit,
    consultation_reporter,
    consultation_annuler,
    consultation_confirmer_paiement,
    consultation_delete,
    consultation_invoice,
    consultation_create_ajax,
    consultation_edit_ajax,
)
from .agenda import agenda, consultations_api
from .fichiers import (
    fichier_upload,
    fichier_delete,
    fichier_download,
    fichier_preview,
)

__all__ = [
    'dashboard_view',
    'patients_list',
    'patient_create',
    'patient_detail',
    'patient_edit',
    'patient_delete',
    'anamnese_edit',
    'anamnese_create',
    'consultations_list',
    'consultation_create',
    'consultation_detail',
    'consultation_edit',
    'consultation_reporter',
    'consultation_annuler',
    'consultation_confirmer_paiement',
    'consultation_delete',
    'consultation_invoice',
    'consultation_create_ajax',
    'consultation_edit_ajax',
    'agenda',
    'consultations_api',
    'fichier_upload',
    'fichier_delete',
    'fichier_download',
    'fichier_preview',
]
