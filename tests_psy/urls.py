from django.urls import path
from tests_psy.views import d2r, vineland , beck

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


    # ========== VINELAND ==========
    path('vineland/', vineland.vineland_liste, name='vineland_liste'),
    path('vineland/nouveau/', vineland.vineland_nouveau, name='vineland_nouveau'),
    path('vineland/nouveau/<int:patient_id>/', vineland.vineland_nouveau, name='vineland_nouveau_patient'),
    path('vineland/<int:test_id>/questionnaire/', vineland.vineland_questionnaire, name='vineland_questionnaire'),
    path('vineland/<int:test_id>/scores/', vineland.vineland_scores, name='vineland_scores'),
    path('vineland/<int:test_id>/echelle-v/', vineland.vineland_echelle_v, name='vineland_echelle_v'),
    path('vineland/<int:test_id>/resultats/', vineland.vineland_resultats, name='vineland_resultats'),
    path('vineland/<int:test_id>/pdf/', vineland.vineland_pdf, name='vineland_pdf'),
    path('vineland/<int:test_id>/comparaisons/', vineland.vineland_comparaisons, name='vineland_comparaisons'),

        
    # ========== BECK ==========
    path('beck/', beck.beck_liste, name='beck_liste'),
    path('beck/nouveau/', beck.beck_nouveau, name='beck_nouveau'),
    path('beck/nouveau/<int:patient_id>/', beck.beck_nouveau, name='beck_nouveau_patient'),
    path('beck/<int:test_id>/passation/', beck.beck_passation, name='beck_passation'),
    path('beck/<int:test_id>/resultats/', beck.beck_resultats, name='beck_resultats'),
    path('beck/<int:test_id>/pdf/', beck.beck_pdf, name='beck_pdf'),


]