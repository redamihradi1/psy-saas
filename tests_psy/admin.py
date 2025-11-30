from django.contrib import admin
from .models import (
    # Commun
    Domain, SousDomain,
    
    # D2R
    TestD2R, SymboleReference, NormeExactitude, 
    NormeRythmeTraitement, NormeCapaciteConcentration,
    
    # Vineland
    TestVineland, ReponseVineland, PlageItemVineland, QuestionVineland,
    EchelleVMapping, NoteDomaineVMapping, IntervaleConfianceSousDomaine,
    IntervaleConfianceDomaine, NiveauAdaptatif, AgeEquivalentSousDomaine,
    ComparaisonDomaineVineland, ComparaisonSousDomaineVineland,
    FrequenceDifferenceDomaineVineland, FrequenceDifferenceSousDomaineVineland,

    # Beck
    TestBeck, ReponseItemBeck, ItemBeck, PhraseBeck
)


# ========== ADMIN COMMUN (DOMAIN & SOUS-DOMAIN) ==========

@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['name', 'ordre', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'description']
    ordering = ['ordre', 'name']


@admin.register(SousDomain)
class SousDomaineAdmin(admin.ModelAdmin):
    list_display = ['name', 'domain', 'ordre', 'created_at']
    list_filter = ['domain', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['domain', 'ordre', 'name']


# ========== ADMIN D2R (TESTS) ==========

@admin.register(TestD2R)
class TestD2RAdmin(admin.ModelAdmin):
    list_display = ['code', 'patient', 'psychologue', 'age', 'date_passation', 'organization']
    list_filter = ['date_passation', 'sexe', 'organization']
    search_fields = ['code', 'patient__nom', 'patient__prenom', 'psychologue__username']
    date_hierarchy = 'date_passation'
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('patient', 'psychologue', 'organization', 'code', 'date_passation')
        }),
        ('Informations participant', {
            'fields': ('age', 'sexe', 'type_ecole', 'etudes', 'profession', 'correction_vue', 'lateralite')
        }),
        ('Résultats', {
            'fields': ('reponses_correctes', 'reponses_incorrectes', 'reponses_omises', 'temps_total')
        }),
        ('Scores calculés', {
            'fields': ('note_cct', 'note_exactitude', 'capacite_concentration')
        })
    )


# ========== ADMIN D2R (CONFIGURATION) ==========

@admin.register(SymboleReference)
class SymboleReferenceAdmin(admin.ModelAdmin):
    list_display = ['page', 'ligne', 'position', 'lettre', 'traits_haut', 'traits_bas', 'background']
    list_filter = ['page', 'ligne', 'lettre', 'background']
    search_fields = ['page', 'ligne', 'position']
    ordering = ['page', 'ligne', 'position']
    
    fieldsets = (
        ('Position', {
            'fields': ('page', 'ligne')
        }),
        ('Caractéristiques', {
            'fields': ('lettre', 'traits_haut', 'traits_bas', 'background')
        })
    )


@admin.register(NormeExactitude)
class NormeExactitudeAdmin(admin.ModelAdmin):
    list_display = ['note_standard', 'percentile', 'age_min', 'age_max', 'valeur_min', 'valeur_max']
    list_filter = ['note_standard', 'age_min', 'age_max']
    search_fields = ['note_standard']
    ordering = ['age_min', 'note_standard']


@admin.register(NormeRythmeTraitement)
class NormeRythmeTraitementAdmin(admin.ModelAdmin):
    list_display = ['note_standard', 'percentile', 'age_min', 'age_max', 'valeur_min', 'valeur_max']
    list_filter = ['note_standard', 'age_min', 'age_max']
    search_fields = ['note_standard']
    ordering = ['age_min', 'note_standard']


@admin.register(NormeCapaciteConcentration)
class NormeCapaciteConcentrationAdmin(admin.ModelAdmin):
    list_display = ['note_standard', 'percentile', 'age_min', 'age_max', 'valeur_min', 'valeur_max']
    list_filter = ['note_standard', 'age_min', 'age_max']
    search_fields = ['note_standard']
    ordering = ['age_min', 'note_standard']


# ========== ADMIN VINELAND (TESTS) ==========

@admin.register(TestVineland)
class TestVinelandAdmin(admin.ModelAdmin):
    list_display = ['patient', 'psychologue', 'date_passation', 'organization', 'is_complete']
    list_filter = ['date_passation', 'organization']
    search_fields = ['patient__nom', 'patient__prenom', 'psychologue__username']
    date_hierarchy = 'date_passation'
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('patient', 'psychologue', 'organization', 'date_passation')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(ReponseVineland)
class ReponseVinelandAdmin(admin.ModelAdmin):
    list_display = ['test_vineland', 'question_short', 'reponse', 'created_at']
    list_filter = ['reponse', 'created_at', 'test_vineland__organization']
    search_fields = ['test_vineland__patient__nom', 'question__texte']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']
    
    def question_short(self, obj):
        return f"{obj.question.sous_domaine.name} - Item {obj.question.numero_item}"
    question_short.short_description = 'Question'


# ========== ADMIN VINELAND (CONFIGURATION) ==========

@admin.register(PlageItemVineland)
class PlageItemVinelandAdmin(admin.ModelAdmin):
    list_display = ['sous_domaine', 'item_debut', 'item_fin', 'age_debut', 'age_fin']
    list_filter = ['sous_domaine', 'age_debut']
    search_fields = ['sous_domaine__name']
    ordering = ['sous_domaine', 'age_debut']


@admin.register(QuestionVineland)
class QuestionVinelandAdmin(admin.ModelAdmin):
    list_display = ['numero_item', 'sous_domaine', 'texte_court', 'permet_na']
    list_filter = ['sous_domaine', 'permet_na']
    search_fields = ['texte', 'numero_item']
    ordering = ['sous_domaine', 'numero_item']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Identification', {
            'fields': ('sous_domaine', 'numero_item')
        }),
        ('Contenu', {
            'fields': ('texte', 'note', 'permet_na')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def texte_court(self, obj):
        return obj.texte[:50] + '...' if len(obj.texte) > 50 else obj.texte
    texte_court.short_description = 'Question'


@admin.register(EchelleVMapping)
class EchelleVMappingAdmin(admin.ModelAdmin):
    list_display = ['sous_domaine', 'age_range', 'note_brute_range', 'note_echelle_v']
    list_filter = ['sous_domaine', 'age_debut_annee', 'note_echelle_v']
    search_fields = ['sous_domaine__name']
    ordering = ['sous_domaine', 'age_debut_annee', 'age_debut_mois', 'note_brute_min']
    
    fieldsets = (
        ('Sous-domaine', {
            'fields': ('sous_domaine',)
        }),
        ('Âge début', {
            'fields': ('age_debut_annee', 'age_debut_mois', 'age_debut_jour')
        }),
        ('Âge fin', {
            'fields': ('age_fin_annee', 'age_fin_mois', 'age_fin_jour')
        }),
        ('Notes', {
            'fields': ('note_brute_min', 'note_brute_max', 'note_echelle_v')
        })
    )
    
    def age_range(self, obj):
        jour_d = f";{obj.age_debut_jour}" if obj.age_debut_jour else ""
        jour_f = f";{obj.age_fin_jour}" if obj.age_fin_jour else ""
        return f"{obj.age_debut_annee}a{obj.age_debut_mois}m{jour_d} - {obj.age_fin_annee}a{obj.age_fin_mois}m{jour_f}"
    age_range.short_description = 'Tranche d\'âge'
    
    def note_brute_range(self, obj):
        return f"{obj.note_brute_min}-{obj.note_brute_max}"
    note_brute_range.short_description = 'Note brute'


@admin.register(NoteDomaineVMapping)
class NoteDomaineVMappingAdmin(admin.ModelAdmin):
    list_display = ['tranche_age', 'note_standard', 'rang_percentile']
    list_filter = ['tranche_age', 'note_standard']
    ordering = ['tranche_age', '-note_standard']
    
    fieldsets = (
        ('Tranche d\'âge', {
            'fields': ('tranche_age',)
        }),
        ('Communication', {
            'fields': ('communication_min', 'communication_max')
        }),
        ('Vie quotidienne', {
            'fields': ('vie_quotidienne_min', 'vie_quotidienne_max')
        }),
        ('Socialisation', {
            'fields': ('socialisation_min', 'socialisation_max')
        }),
        ('Motricité', {
            'fields': ('motricite_min', 'motricite_max')
        }),
        ('Résultats', {
            'fields': ('note_standard', 'note_composite_min', 'note_composite_max', 'rang_percentile')
        })
    )


@admin.register(IntervaleConfianceSousDomaine)
class IntervaleConfianceSousDomaineAdmin(admin.ModelAdmin):
    list_display = ['sous_domaine', 'age', 'niveau_confiance', 'intervalle']
    list_filter = ['age', 'niveau_confiance', 'sous_domaine']
    ordering = ['age', '-niveau_confiance', 'sous_domaine']


@admin.register(IntervaleConfianceDomaine)
class IntervaleConfianceDomaineAdmin(admin.ModelAdmin):
    list_display = ['domain', 'age', 'niveau_confiance', 'intervalle', 'note_composite']
    list_filter = ['age', 'niveau_confiance', 'domain']
    ordering = ['age', '-niveau_confiance', 'domain']


@admin.register(NiveauAdaptatif)
class NiveauAdaptatifAdmin(admin.ModelAdmin):
    list_display = ['niveau', 'echelle_v_range', 'note_standard_range']
    list_filter = ['niveau']
    ordering = ['echelle_v_min']
    
    def echelle_v_range(self, obj):
        return f"{obj.echelle_v_min}-{obj.echelle_v_max}"
    echelle_v_range.short_description = 'Échelle-V'
    
    def note_standard_range(self, obj):
        return f"{obj.note_standard_min}-{obj.note_standard_max}"
    note_standard_range.short_description = 'Note standard'


@admin.register(AgeEquivalentSousDomaine)
class AgeEquivalentSousDomaineAdmin(admin.ModelAdmin):
    list_display = ['sous_domaine', 'note_brute_range', 'age_display']
    list_filter = ['sous_domaine', 'age_special']
    search_fields = ['sous_domaine__name']
    ordering = ['sous_domaine', '-age_annees', '-age_mois']
    
    fieldsets = (
        ('Sous-domaine', {
            'fields': ('sous_domaine',)
        }),
        ('Note brute', {
            'fields': ('note_brute_min', 'note_brute_max')
        }),
        ('Âge équivalent', {
            'fields': ('age_special', 'age_annees', 'age_mois')
        })
    )
    
    def note_brute_range(self, obj):
        if obj.note_brute_max:
            return f"{obj.note_brute_min}-{obj.note_brute_max}"
        return str(obj.note_brute_min)
    note_brute_range.short_description = 'Note brute'
    
    def age_display(self, obj):
        return obj.get_age_equivalent_display()
    age_display.short_description = 'Âge équivalent'


@admin.register(ComparaisonDomaineVineland)
class ComparaisonDomaineVinelandAdmin(admin.ModelAdmin):
    list_display = ['domaine1', 'domaine2', 'age', 'niveau_significativite', 'difference_requise']
    list_filter = ['age', 'niveau_significativite']
    search_fields = ['domaine1__name', 'domaine2__name']
    ordering = ['age', 'domaine1']


@admin.register(ComparaisonSousDomaineVineland)
class ComparaisonSousDomaineVinelandAdmin(admin.ModelAdmin):
    list_display = ['sous_domaine1', 'sous_domaine2', 'age', 'niveau_significativite', 'difference_requise']
    list_filter = ['age', 'niveau_significativite']
    search_fields = ['sous_domaine1__name', 'sous_domaine2__name']
    ordering = ['age', 'sous_domaine1']


@admin.register(FrequenceDifferenceDomaineVineland)
class FrequenceDifferenceDomaineVinelandAdmin(admin.ModelAdmin):
    list_display = ['domaine1', 'domaine2', 'age', 'frequence_5', 'frequence_10', 'frequence_16']
    list_filter = ['age']
    search_fields = ['domaine1__name', 'domaine2__name']
    ordering = ['age', 'domaine1']


@admin.register(FrequenceDifferenceSousDomaineVineland)
class FrequenceDifferenceSousDomaineVinelandAdmin(admin.ModelAdmin):
    list_display = ['sous_domaine1', 'sous_domaine2', 'age', 'frequence_5', 'frequence_10', 'frequence_16']
    list_filter = ['age']
    search_fields = ['sous_domaine1__name', 'sous_domaine2__name']
    ordering = ['age', 'sous_domaine1']

# ========== ADMIN BECK (TESTS) ==========

@admin.register(TestBeck)
class TestBeckAdmin(admin.ModelAdmin):
    list_display = ['patient', 'psychologue', 'date_passation', 'score_total', 'niveau_depression', 'alerte_suicide', 'organization']
    list_filter = ['date_passation', 'niveau_depression', 'alerte_suicide', 'organization']
    search_fields = ['patient__nom', 'patient__prenom', 'psychologue__username']
    date_hierarchy = 'date_passation'
    readonly_fields = ['date_passation', 'score_total', 'niveau_depression', 'alerte_suicide']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('patient', 'psychologue', 'organization', 'date_passation')
        }),
        ('Résultats', {
            'fields': ('score_total', 'niveau_depression', 'alerte_suicide')
        }),
        ('Notes', {
            'fields': ('notes',)
        })
    )


@admin.register(ReponseItemBeck)
class ReponseItemBeckAdmin(admin.ModelAdmin):
    list_display = ['test', 'item', 'score_item', 'organization']
    list_filter = ['item__numero', 'score_item', 'organization']
    search_fields = ['test__patient__nom', 'test__patient__prenom']
    readonly_fields = ['score_item']
    
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        # Filtrer les phrases disponibles selon l'item sélectionné
        if db_field.name == "phrases_cochees":
            # On laisse Django gérer, mais on pourrait filtrer ici si besoin
            pass
        return super().formfield_for_manytomany(db_field, request, **kwargs)


# ========== ADMIN BECK (CONFIGURATION) ==========

@admin.register(ItemBeck)
class ItemBeckAdmin(admin.ModelAdmin):
    list_display = ['numero', 'categorie']
    list_filter = ['numero']
    search_fields = ['categorie']
    ordering = ['numero']


@admin.register(PhraseBeck)
class PhraseBeckAdmin(admin.ModelAdmin):
    list_display = ['item', 'score_valeur', 'texte_court', 'ordre']
    list_filter = ['item__numero', 'score_valeur']
    search_fields = ['texte', 'item__categorie']
    ordering = ['item__numero', 'ordre']
    
    fieldsets = (
        ('Item', {
            'fields': ('item', 'ordre')
        }),
        ('Contenu', {
            'fields': ('score_valeur', 'texte')
        })
    )
    
    def texte_court(self, obj):
        return obj.texte[:60] + '...' if len(obj.texte) > 60 else obj.texte
    texte_court.short_description = 'Phrase'