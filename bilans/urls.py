from django.urls import path

from . import views

app_name = 'bilans'

urlpatterns = [
    path('', views.bilans_liste, name='liste'),
    path('nouveau/', views.bilan_nouveau, name='nouveau'),
    path('<int:bilan_id>/', views.bilan_editeur, name='editeur'),
    path('<int:bilan_id>/sauvegarder/', views.bilan_sauvegarder, name='sauvegarder'),
    path('<int:bilan_id>/statut/', views.bilan_statut, name='statut'),
    path('<int:bilan_id>/versions/', views.bilan_versions, name='versions'),
    path('<int:bilan_id>/versions/<int:version_id>/restaurer/', views.bilan_restaurer_version, name='restaurer_version'),
    path('<int:bilan_id>/supprimer/', views.bilan_supprimer, name='supprimer'),
    path('<int:bilan_id>/export/<str:format_export>/', views.bilan_export, name='export'),
    path('<int:bilan_id>/ia/apercu/', views.bilan_ia_apercu, name='ia_apercu'),
    path('<int:bilan_id>/ia/premier-jet/', views.bilan_ia_premier_jet, name='ia_premier_jet'),
    path('<int:bilan_id>/ia/chat/', views.bilan_ia_chat, name='ia_chat'),
]
