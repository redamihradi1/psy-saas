from django.urls import path
from . import views

app_name = 'cabinet'

urlpatterns = [
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
    
    # Packs
    path('packs/', views.packs_list, name='packs_list'),
    path('packs/create/', views.pack_create, name='pack_create'),
    path('packs/<int:pack_id>/', views.pack_detail, name='pack_detail'),
]