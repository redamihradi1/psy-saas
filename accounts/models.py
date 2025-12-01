from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta
from tests_psy.models import TestBeck , TestSTAI

from core import tests

class Organization(models.Model):
    """Cabinet/Organisation du psychologue"""
    name = models.CharField(max_length=200, verbose_name="Nom du cabinet")
    slug = models.SlugField(unique=True, verbose_name="Identifiant unique")
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organisation"
        verbose_name_plural = "Organisations"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Utilisateur personnalisé"""
    ROLE_CHOICES = [
        ('superadmin', 'Super Admin'),
        ('psychologist', 'Psychologue'),
        ('assistant', 'Assistant'),
    ]
    
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='users'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='psychologist')
    phone = models.CharField(max_length=20, blank=True)
    license_number = models.CharField(max_length=100, blank=True, verbose_name="Numéro de licence professionnelle")
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

    def is_superadmin(self):
        return self.role == 'superadmin'

    def is_psychologist(self):
        return self.role == 'psychologist'


class License(models.Model):
    """Licence d'utilisation pour une organisation"""
    PLAN_CHOICES = [
        ('trial', 'Essai gratuit (30 jours)'),
        ('lifetime', 'Licence complète (achat unique)'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expirée'),
        ('suspended', 'Suspendue'),
        ('cancelled', 'Annulée'),
    ]
    
    organization = models.OneToOneField(
        Organization, 
        on_delete=models.CASCADE,
        related_name='license'
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='trial')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Limites patients (configurable par le super admin)
    max_patients = models.IntegerField(default=10, verbose_name="Nombre max de patients")
    
    # Modules tests (configurables - par défaut tous à False)
    has_d2r = models.BooleanField(default=False, verbose_name="Accès Test D2R")
    max_tests_d2r = models.IntegerField(default=0, verbose_name="Nombre max de tests D2R (0 = illimité)")
    
    has_vineland = models.BooleanField(default=False, verbose_name="Accès Test Vineland")
    max_tests_vineland = models.IntegerField(default=0, verbose_name="Nombre max de tests Vineland (0 = illimité)")
    
    has_beck = models.BooleanField(default=False, verbose_name="Accès Test Beck")
    max_tests_beck = models.IntegerField(default=0, verbose_name="Nombre max de tests Beck (0 = illimité)")

    has_stai = models.BooleanField(default=False, verbose_name="Accès Test STAI")
    max_tests_stai = models.IntegerField(default=0, verbose_name="Nombre max de tests STAI (0 = illimité)")

    has_pep3 = models.BooleanField(default=False, verbose_name="Accès Test PEP3")
    max_tests_pep3 = models.IntegerField(default=0, verbose_name="Nombre max de tests PEP3 (0 = illimité)")
    
    # Dates
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Date de fin (null = illimité)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Licence"
        verbose_name_plural = "Licences"
        ordering = ['-created_at']

    def __str__(self):
        tests = self.get_available_tests()
        tests_str = ', '.join(tests) if tests else 'Aucun test'
        return f"{self.organization.name} - {self.get_plan_display()} ({tests_str})"

    def save(self, *args, **kwargs):
        # Note: max_patients, max_tests_* sont maintenant configurables manuellement
        # On définit juste les dates selon le plan
        if self.plan == 'trial':
            if not self.end_date:
                self.end_date = timezone.now() + timedelta(days=30)
        elif self.plan == 'lifetime':
            self.end_date = None
        super().save(*args, **kwargs)

    def is_active(self):
        """Vérifie si la licence est active et non expirée"""
        if self.status != 'active':
            return False
        # Lifetime = toujours actif
        if self.plan == 'lifetime':
            return True
        # Trial = vérifier la date
        return self.end_date and self.end_date > timezone.now()

    def days_remaining(self):
        """Nombre de jours restants (trial uniquement)"""
        if self.plan == 'lifetime':
            return 'Illimité'
        if self.end_date and self.end_date > timezone.now():
            return (self.end_date - timezone.now()).days
        return 0
    
    def can_add_patient(self):
        """Vérifie si l'organisation peut ajouter un nouveau patient"""
        from cabinet.models import Patient
        current_count = Patient.objects.filter(organization=self.organization).count()
        return current_count < self.max_patients
    
    def get_patients_remaining(self):
        """Retourne le nombre de patients restants"""
        from cabinet.models import Patient
        current_count = Patient.objects.filter(organization=self.organization).count()
        return max(0, self.max_patients - current_count)
    
    def can_add_test(self, test_name):
        """Vérifie si l'organisation peut créer un nouveau test
        
        Args:
            test_name (str): Nom du test ('d2r', 'vineland', 'pep3')
            
        Returns:
            bool: True si un nouveau test peut être créé
        """
        if not self.has_test_access(test_name):
            return False
        
        # Si max = 0, c'est illimité
        test_limits = {
            'd2r': self.max_tests_d2r,
            'vineland': self.max_tests_vineland,
            'beck': self.max_tests_beck,
            'stai': self.max_tests_stai,
            'pep3': self.max_tests_pep3,
        }
        
        max_tests = test_limits.get(test_name.lower(), 0)
        if max_tests == 0:
            return True  # Illimité
        
        # Compter les tests existants
        from tests_psy.models import TestD2R,TestVineland
        # TODO: Ajouter Vineland et PEP3 quand disponibles
        
        if test_name.lower() == 'd2r':
            current_count = TestD2R.objects.filter(organization=self.organization).count()
            return current_count < max_tests
        elif test_name.lower() == 'vineland':
            current_count = TestVineland.objects.filter(organization=self.organization).count()
            return current_count < max_tests
        elif test_name.lower() == 'beck':  
            current_count = TestBeck.objects.filter(organization=self.organization).count()
            return current_count < max_tests
        elif test_name.lower() == 'stai':
            current_count = TestSTAI.objects.filter(organization=self.organization).count()
            return current_count < max_tests
        elif test_name.lower() == 'pep3':
            # TODO: Implémenter quand PEP3 sera disponible
            return True
        
        return False
    
    def get_tests_remaining(self, test_name):
        """Retourne le nombre de tests restants pour un test donné
        
        Args:
            test_name (str): Nom du test ('d2r', 'vineland', 'pep3')
            
        Returns:
            int or str: Nombre restant ou 'Illimité'
        """
        test_limits = {
            'd2r': self.max_tests_d2r,
            'vineland': self.max_tests_vineland,
            'beck': self.max_tests_beck,
            'stai': self.max_tests_stai,
            'pep3': self.max_tests_pep3,
        }
        
        max_tests = test_limits.get(test_name.lower(), 0)
        if max_tests == 0:
            return 'Illimité'
        
        # Compter les tests existants
        from tests_psy.models import TestD2R, TestVineland
        
        test_name_lower = test_name.lower()
        
        if test_name_lower == 'd2r':
            current_count = TestD2R.objects.filter(organization=self.organization).count()
            return max(0, max_tests - current_count)
        elif test_name_lower == 'vineland':
            current_count = TestVineland.objects.filter(organization=self.organization).count()
            return max(0, max_tests - current_count)
        elif test_name_lower == 'beck':  
            current_count = TestBeck.objects.filter(organization=self.organization).count()
            return max(0, max_tests - current_count)
        elif test_name_lower == 'stai':
            current_count = TestSTAI.objects.filter(organization=self.organization).count()
            return max(0, max_tests - current_count)
        elif test_name_lower == 'pep3':
            # TODO: Implémenter quand PEP3 sera disponible
            return 'Illimité'
        
        return 'Illimité'
    
    def has_test_access(self, test_name):
        """Vérifie si la licence donne accès à un test spécifique
        
        Args:
            test_name (str): Nom du test ('d2r', 'vineland', 'pep3')
            
        Returns:
            bool: True si l'accès est autorisé, False sinon
        """
        if not self.is_active():
            return False
        
        test_mapping = {
            'd2r': self.has_d2r,
            'vineland': self.has_vineland,
            'beck': self.has_beck,
            'stai': self.has_stai,
            'pep3': self.has_pep3,
        }
        
        return test_mapping.get(test_name.lower(), False)
    
    def get_available_tests(self):
        """Retourne la liste des tests disponibles pour cette licence
        
        Returns:
            list: Liste des noms de tests disponibles
        """
        tests = []
        if self.has_d2r:
            tests.append('D2R')
        if self.has_vineland:
            tests.append('Vineland')
        if self.has_beck:
            tests.append('Beck')
        if self.has_stai:
            tests.append('STAI')
        if self.has_pep3:
            tests.append('PEP3')
        return tests
    
    def get_missing_tests(self):
        """Retourne la liste des tests NON disponibles
        
        Returns:
            list: Liste des noms de tests non disponibles
        """
        all_tests = ['D2R', 'Vineland', 'PEP3' , 'Beck' , 'STAI']
        available = self.get_available_tests()
        return [test for test in all_tests if test not in available]