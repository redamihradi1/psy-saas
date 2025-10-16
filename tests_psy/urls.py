from django.urls import path
from . import views

app_name = 'tests_psy'

urlpatterns = [
    # Liste globale des tests
    path('d2r/', views.d2r_liste, name='d2r_liste'),
    
    # D2R - Création et passation
    path('d2r/nouveau/', views.d2r_nouveau, name='d2r_nouveau'),
    path('d2r/nouveau/<int:patient_id>/', views.d2r_nouveau, name='d2r_nouveau_patient'),
    path('d2r/<int:test_id>/passation/', views.d2r_passation, name='d2r_passation'),
    path('d2r/<int:test_id>/submit/', views.d2r_submit, name='d2r_submit'),
    
    # D2R - Résultats
    path('d2r/<int:test_id>/resultats/', views.d2r_resultats, name='d2r_resultats'),
    path('d2r/<int:test_id>/pdf/', views.d2r_pdf, name='d2r_pdf'),
]