from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Organization, License


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'city', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'slug', 'city']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'role', 'organization', 'is_active']
    list_filter = ['role', 'is_active', 'organization']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Informations supplémentaires', {
            'fields': ('organization', 'role', 'phone', 'license_number', 'avatar')
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Informations supplémentaires', {
            'fields': ('organization', 'role', 'phone', 'license_number')
        }),
    )


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ['organization', 'plan', 'status', 'start_date', 'end_date', 'days_remaining']
    list_filter = ['plan', 'status', 'start_date']
    search_fields = ['organization__name']
    readonly_fields = ['created_at', 'updated_at']
    
    def days_remaining(self, obj):
        return f"{obj.days_remaining()} jours"
    days_remaining.short_description = "Jours restants"