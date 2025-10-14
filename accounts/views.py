from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import User, Organization, License


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Bienvenue {user.get_full_name()}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Identifiants incorrects')
    
    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'Déconnexion réussie')
    return redirect('login')


@login_required
def dashboard_view(request):
    user = request.user
    organization = user.organization
    license = None
    
    if organization:
        license = organization.license
    
    context = {
        'user': user,
        'organization': organization,
        'license': license,
    }
    
    return render(request, 'accounts/dashboard.html', context)