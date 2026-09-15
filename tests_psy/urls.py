from django.urls import path
from tests_psy.views import d2r, vineland , beck , stai
from tests_psy.views.vineland import public as vineland_public

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

    # Nouveau test Vineland - modes "notes importées" et "lien public"
    path('vineland/<int:test_id>/notes-importees/', vineland.vineland_notes_importees, name='vineland_notes_importees'),
    path('vineland/<int:test_id>/lien/genere/', vineland.vineland_lien_genere, name='vineland_lien_genere'),
    path('vineland/<int:test_id>/lien/reouvrir/', vineland.vineland_reouvrir_lien, name='vineland_reouvrir_lien'),
    path('vineland/<int:test_id>/supprimer/', vineland.vineland_delete, name='vineland_delete'),

    # Lien public Vineland - AUCUNE authentification (jeton secret dans l'URL), destiné aux
    # parents pour une passation à distance. Voir tests_psy/views/vineland/public.py.
    path('vineland/public/<str:token>/', vineland_public.vineland_public_questionnaire, name='vineland_public_questionnaire'),
    path('vineland/public/<str:token>/merci/', vineland_public.vineland_public_merci, name='vineland_public_merci'),


    # ========== BECK ==========
    path('beck/', beck.beck_liste, name='beck_liste'),
    path('beck/nouveau/', beck.beck_nouveau, name='beck_nouveau'),
    path('beck/nouveau/<int:patient_id>/', beck.beck_nouveau, name='beck_nouveau_patient'),
    path('beck/<int:test_id>/passation/', beck.beck_passation, name='beck_passation'),
    path('beck/<int:test_id>/resultats/', beck.beck_resultats, name='beck_resultats'),
    path('beck/<int:test_id>/pdf/', beck.beck_pdf, name='beck_pdf'),

    # ========== STAI ==========
    path('stai/', stai.stai_liste, name='stai_liste'),
    path('stai/nouveau/', stai.stai_nouveau, name='stai_nouveau'),
    path('stai/nouveau/<int:patient_id>/', stai.stai_nouveau, name='stai_nouveau_patient'),
    path('stai/<int:test_id>/passation/', stai.stai_passation, name='stai_passation'),
    path('stai/<int:test_id>/resultats/', stai.stai_resultats, name='stai_resultats'),
    path('stai/<int:test_id>/pdf/', stai.stai_pdf, name='stai_pdf'),


]