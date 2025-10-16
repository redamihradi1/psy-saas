from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import User, Organization, License


def login_view(request):
    if request.user.is_authenticated:
        return redirect('cabinet:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Bienvenue {user.get_full_name()}!')
            return redirect('cabinet:dashboard')
        else:
            messages.error(request, 'Identifiants incorrects')
    
    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'Déconnexion réussie')
    return redirect('login')

@login_required
def profile_view(request):
    """Page Mon compte - Affichage des infos (lecture seule)"""
    return render(request, 'accounts/profile.html')


@login_required
def settings_view(request):
    """Page Paramètres - Modification des infos et mot de passe"""
    if request.method == 'POST':
        # Modification des infos personnelles
        if 'update_profile' in request.POST:
            user = request.user
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.email = request.POST.get('email', '')
            user.phone = request.POST.get('phone', '')
            user.license_number = request.POST.get('license_number', '')
            user.save()
            
            messages.success(request, 'Vos informations ont été mises à jour avec succès !')
            return redirect('accounts:settings')
        
        # Changement de mot de passe
        elif 'change_password' in request.POST:
            form = PasswordChangeForm(request.user, request.POST)
            if form.is_valid():
                user = form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Votre mot de passe a été changé avec succès !')
                return redirect('accounts:settings')
            else:
                messages.error(request, 'Erreur lors du changement de mot de passe.')
                return render(request, 'accounts/settings.html', {'form': form})
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/settings.html', {'form': form})