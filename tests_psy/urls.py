from django.urls import path
from tests_psy.views import d2r

app_name = 'tests_psy'

urlpatterns = [
    # Liste globale des tests
    path('d2r/', d2r.d2r_liste, name='d2r_liste'),
    
    # D2R - Création et passation
    path('d2r/nouveau/', d2r.d2r_nouveau, name='d2r_nouveau'),
    path('d2r/nouveau/<int:patient_id>/', d2r.d2r_nouveau, name='d2r_nouveau_patient'),
    path('d2r/<int:test_id>/instructions/', d2r.d2r_instructions, name='d2r_instructions'),
    path('d2r/<int:test_id>/passation/', d2r.d2r_passation, name='d2r_passation'),
    path('d2r/<int:test_id>/submit/', d2r.d2r_submit, name='d2r_submit'),
    
    # D2R - Résultats
    path('d2r/<int:test_id>/resultats/', d2r.d2r_resultats, name='d2r_resultats'),
    path('d2r/<int:test_id>/pdf/', d2r.d2r_pdf, name='d2r_pdf'),
]