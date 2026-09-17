from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),  
    path('settings/', views.settings_view, name='settings'),

    # Administration plateforme (super admin uniquement)
    path('admin/clients/', views.clients_list, name='clients_list'),
    path('admin/clients/create/', views.client_create, name='client_create'),
    path('admin/clients/<int:org_id>/edit/', views.client_edit, name='client_edit'),
    path('admin/clients/<int:org_id>/patients/', views.client_patients, name='client_patients'),
    path('admin/assistants/', views.assistants_list, name='assistants_list'),
    path('admin/assistants/create/', views.assistant_create, name='assistant_create'),
    path('admin/assistants/<int:user_id>/edit/', views.assistant_edit, name='assistant_edit'),
    path('admin/assistants/<int:user_id>/reset-password/', views.assistant_reset_password, name='assistant_reset_password'),
    path('admin/assistants/<int:user_id>/toggle-active/', views.assistant_toggle_active, name='assistant_toggle_active'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/comptabilite/', views.admin_comptabilite, name='admin_comptabilite'),
]