"""Cree une vingtaine de patients de test pour l'organisation existante."""
import os
import random
from datetime import date

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import Organization
from cabinet.models import Patient

PRENOMS_H = ['Youssef', 'Karim', 'Amine', 'Mehdi', 'Omar', 'Rachid', 'Hamza', 'Tarik', 'Younes', 'Adil']
PRENOMS_F = ['Fatima', 'Sara', 'Nadia', 'Imane', 'Salma', 'Khadija', 'Meryem', 'Zineb', 'Houda', 'Laila']
NOMS = ['Alaoui', 'Bennani', 'Cherkaoui', 'Idrissi', 'Fassi', 'Berrada', 'Tazi', 'Lahlou', 'Ouazzani', 'Sbai',
        'Benjelloun', 'El Amrani', 'Kabbaj', 'Ziani', 'Chraibi', 'Mansouri', 'Amrani', 'Bouzid', 'Squalli', 'Naciri']

org = Organization.objects.get(slug='redaorg')

created = 0
for i in range(20):
    is_enfant = random.random() < 0.3
    is_homme = random.random() < 0.5
    prenom = random.choice(PRENOMS_H if is_homme else PRENOMS_F)
    nom = random.choice(NOMS)

    if is_enfant:
        annee = random.randint(date.today().year - 15, date.today().year - 4)
    else:
        annee = random.randint(date.today().year - 65, date.today().year - 18)
    mois = random.randint(1, 12)
    jour = random.randint(1, 28)

    patient = Patient.objects.create(
        organization=org,
        nom=nom,
        prenom=f"{prenom} Test{i+1}",
        date_naissance=date(annee, mois, jour),
        categorie_age='enfant' if is_enfant else 'adulte',
        telephone=f"06{random.randint(10000000, 99999999)}",
        email=f"{prenom.lower()}.{nom.lower()}.test{i+1}@example.com",
    )
    created += 1
    print(f"Créé: {patient.nom_complet} ({patient.categorie_age}, né {patient.date_naissance})")

print(f"\n{created} patients de test créés pour l'organisation '{org.name}'.")
