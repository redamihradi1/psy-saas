from django.urls import path

from . import views

app_name = 'bilans'

urlpatterns = [
    path('', views.bilans_liste, name='liste'),
    path('nouveau/', views.bilan_nouveau, name='nouveau'),
    path('textes/', views.textes_types, name='textes_types'),
    path('textes/json/', views.textes_types_json, name='textes_types_json'),
    path('en-tete/', views.en_tete, name='en_tete'),
    path('en-tete/<str:champ>.png', views.en_tete_image, name='en_tete_image'),
    path('<int:bilan_id>/', views.bilan_editeur, name='editeur'),
    path('<int:bilan_id>/donnees/', views.bilan_donnees, name='donnees'),
    path('<int:bilan_id>/figure/<str:ref>.png', views.bilan_figure, name='figure'),
    path('<int:bilan_id>/sauvegarder/', views.bilan_sauvegarder, name='sauvegarder'),
    path('<int:bilan_id>/statut/', views.bilan_statut, name='statut'),
    path('<int:bilan_id>/versions/', views.bilan_versions, name='versions'),
    path('<int:bilan_id>/versions/<int:version_id>/restaurer/', views.bilan_restaurer_version, name='restaurer_version'),
    path('<int:bilan_id>/supprimer/', views.bilan_supprimer, name='supprimer'),
    path('<int:bilan_id>/export/<str:format_export>/', views.bilan_export, name='export'),
    path('<int:bilan_id>/coherence/', views.bilan_coherence, name='coherence'),
    path('<int:bilan_id>/ia/apercu/', views.bilan_ia_apercu, name='ia_apercu'),
    path('<int:bilan_id>/ia/premier-jet/', views.bilan_ia_premier_jet, name='ia_premier_jet'),
    path('<int:bilan_id>/ia/chat/', views.bilan_ia_chat, name='ia_chat'),
]
