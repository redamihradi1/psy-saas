from django.urls import path
from . import views

app_name = 'cabinet'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Recherche globale
    path('search/', views.global_search, name='global_search'),

    # Sauvegarde
    path('sauvegarde/', views.backup_page, name='backup_page'),
    path('sauvegarde/export/', views.backup_export, name='backup_export'),

    # Comptabilité
    path('comptabilite/', views.comptabilite_dashboard, name='comptabilite_dashboard'),
    path('comptabilite/depenses/create/', views.depense_create, name='depense_create'),
    path('comptabilite/depenses/<int:depense_id>/edit/', views.depense_edit, name='depense_edit'),
    path('comptabilite/depenses/<int:depense_id>/delete/', views.depense_delete, name='depense_delete'),
    path('comptabilite/export/', views.comptabilite_export_csv, name='comptabilite_export_csv'),

    # Modèles de messages (rappels WhatsApp)
    path('modeles-messages/', views.message_templates_list, name='message_templates_list'),
    path('modeles-messages/json/', views.message_templates_json, name='message_templates_json'),
    path('modeles-messages/create/', views.message_template_create, name='message_template_create'),
    path('modeles-messages/<int:template_id>/edit/', views.message_template_edit, name='message_template_edit'),
    path('modeles-messages/<int:template_id>/delete/', views.message_template_delete, name='message_template_delete'),
    
    # Patients
    path('patients/', views.patients_list, name='patients_list'),
    path('patients/create/', views.patient_create, name='patient_create'),
    path('patients/<int:patient_id>/', views.patient_detail, name='patient_detail'),
    path('patients/<int:patient_id>/edit/', views.patient_edit, name='patient_edit'),
    path('patients/<int:patient_id>/delete/', views.patient_delete, name='patient_delete'),

    # Consultations
    path('consultations/', views.consultations_list, name='consultations_list'),
    path('consultations/create/', views.consultation_create, name='consultation_create'),
    path('consultations/<int:consultation_id>/', views.consultation_detail, name='consultation_detail'),
    path('consultations/<int:consultation_id>/edit/', views.consultation_edit, name='consultation_edit'),
    path('consultations/<int:consultation_id>/delete/', views.consultation_delete, name='consultation_delete'),
    path('consultations/<int:consultation_id>/reporter/', views.consultation_reporter, name='consultation_reporter'),
    path('consultations/<int:consultation_id>/annuler/', views.consultation_annuler, name='consultation_annuler'),
    path('consultations/<int:consultation_id>/confirmer-paiement/', views.consultation_confirmer_paiement, name='consultation_confirmer_paiement'),
    path('consultations/<int:consultation_id>/facture/', views.consultation_invoice, name='consultation_invoice'),
    path('consultations/<int:consultation_id>/statut-rapide/', views.consultation_quick_statut, name='consultation_quick_statut'),

    # Gestion des fichiers patients
    path('patients/<int:patient_id>/fichiers/upload/', views.fichier_upload, name='fichier_upload'),
    path('patients/<int:patient_id>/fichiers/<int:fichier_id>/delete/', views.fichier_delete, name='fichier_delete'),
    path('patients/<int:patient_id>/fichiers/<int:fichier_id>/download/', views.fichier_download, name='fichier_download'),
    path('patients/<int:patient_id>/fichiers/<int:fichier_id>/preview/', views.fichier_preview, name='fichier_preview'),

    # Anamnese
    path('patients/<int:patient_id>/anamnese/create/', views.anamnese_create, name='anamnese_create'),
    path('patients/<int:patient_id>/anamnese/edit/', views.anamnese_edit, name='anamnese_edit'),

    # Agenda
    path('agenda/', views.agenda, name='agenda'),
    path('consultations/api/', views.consultations_api, name='consultations_api'),
    path('consultations/create-ajax/', views.consultation_create_ajax, name='consultation_create_ajax'),
    path('consultations/<int:pk>/edit-ajax/', views.consultation_edit_ajax, name='consultation_edit_ajax'),
    

]