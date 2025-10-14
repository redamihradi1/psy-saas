from django.contrib import admin
from .models import Patient, Anamnese, Consultation, PackMindOffice, PatientFichier


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['nom', 'prenom', 'age', 'categorie_age', 'telephone', 'organization', 'date_creation']
    list_filter = ['categorie_age', 'organization', 'date_creation']
    search_fields = ['nom', 'prenom', 'telephone', 'email']
    readonly_fields = ['date_creation', 'date_modification']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superadmin():
            return qs  # Voir tout
        return qs.filter(organization=request.user.organization)
    
    def save_model(self, request, obj, form, change):
        if not obj.pk and not request.user.is_superadmin():
            obj.organization = request.user.organization
        super().save_model(request, obj, form, change)


@admin.register(Anamnese)
class AnamneseAdmin(admin.ModelAdmin):
    list_display = ['patient', 'organization', 'niveau_stress', 'date_creation']
    list_filter = ['niveau_stress', 'deja_consulte_psy', 'organization']
    search_fields = ['patient__nom', 'patient__prenom']
    readonly_fields = ['date_creation', 'date_modification']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superadmin():
            return qs
        return qs.filter(organization=request.user.organization)
    
    def save_model(self, request, obj, form, change):
        if not obj.pk and not request.user.is_superadmin():
            obj.organization = request.user.organization
        super().save_model(request, obj, form, change)


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ['patient', 'date_seance', 'lieu_consultation', 'tarif', 'statut_paiement', 'statut_consultation', 'organization']
    list_filter = ['lieu_consultation', 'statut_paiement', 'statut_consultation', 'organization', 'date_seance']
    search_fields = ['patient__nom', 'patient__prenom']
    readonly_fields = ['date_creation', 'date_modification']
    date_hierarchy = 'date_seance'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superadmin():
            return qs
        return qs.filter(organization=request.user.organization)


@admin.register(PackMindOffice)
class PackMindOfficeAdmin(admin.ModelAdmin):
    list_display = ['nom_pack', 'seances_restantes', 'statut', 'prix_pack', 'organization', 'date_achat']
    list_filter = ['statut', 'organization', 'date_achat']
    search_fields = ['nom_pack']
    readonly_fields = ['date_creation', 'date_modification', 'seances_restantes', 'pourcentage_utilise']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superadmin():
            return qs
        return qs.filter(organization=request.user.organization)


@admin.register(PatientFichier)
class PatientFichierAdmin(admin.ModelAdmin):
    list_display = ['nom_fichier', 'patient', 'categorie', 'taille_lisible', 'organization', 'date_upload']
    list_filter = ['categorie', 'organization', 'date_upload']
    search_fields = ['nom_fichier', 'patient__nom', 'patient__prenom']
    readonly_fields = ['date_upload', 'date_modification', 'taille_fichier', 'taille_lisible']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superadmin():
            return qs
        return qs.filter(organization=request.user.organization)