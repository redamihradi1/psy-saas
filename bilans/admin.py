from django.contrib import admin

from .models import AppelIA, Bilan, VersionBilan


@admin.register(Bilan)
class BilanAdmin(admin.ModelAdmin):
    list_display = ('titre', 'patient', 'organization', 'statut', 'date_modification')
    list_filter = ('statut', 'modele', 'organization')


@admin.register(VersionBilan)
class VersionBilanAdmin(admin.ModelAdmin):
    list_display = ('bilan', 'motif', 'date')


@admin.register(AppelIA)
class AppelIAAdmin(admin.ModelAdmin):
    list_display = ('date', 'organization', 'type_appel', 'succes', 'tokens', 'erreur')
    list_filter = ('succes', 'type_appel', 'organization')
