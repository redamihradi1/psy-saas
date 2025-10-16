# import_d2r_config.py
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tests_psy.models import (
    SymboleReference, 
    NormeExactitude, 
    NormeRythmeTraitement, 
    NormeCapaciteConcentration
)

def import_data():
    # Charger les données depuis le fichier JSON exporté
    json_file = 'd2r_config_data.json'
    
    if not os.path.exists(json_file):
        print(f"❌ Erreur : Le fichier {json_file} n'existe pas")
        print("Place le fichier d2r_config_data.json à la racine du projet psy-saas")
        return
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("🔄 Début de l'import des données de configuration D2R...")
    print("ℹ️  Ces données sont partagées par tous les utilisateurs\n")
    
    # Import Symboles (SANS organization)
    print("📝 Import des symboles...")
    count_before = SymboleReference.objects.count()
    SymboleReference.objects.all().delete()
    
    symboles_created = 0
    for symbole_data in data['symboles']:
        SymboleReference.objects.create(**symbole_data)
        symboles_created += 1
    
    print(f"✅ {symboles_created} symboles importés (remplacé {count_before} existants)")
    
    # Import Normes Exactitude
    print("\n📊 Import des normes d'exactitude...")
    count_before = NormeExactitude.objects.count()
    NormeExactitude.objects.all().delete()
    
    normes_exactitude_created = 0
    for norme_data in data['normes_exactitude']:
        NormeExactitude.objects.create(**norme_data)
        normes_exactitude_created += 1
    
    print(f"✅ {normes_exactitude_created} normes exactitude importées (remplacé {count_before} existantes)")
    
    # Import Normes Rythme
    print("\n⏱️ Import des normes de rythme...")
    count_before = NormeRythmeTraitement.objects.count()
    NormeRythmeTraitement.objects.all().delete()
    
    normes_rythme_created = 0
    for norme_data in data['normes_rythme']:
        NormeRythmeTraitement.objects.create(**norme_data)
        normes_rythme_created += 1
    
    print(f"✅ {normes_rythme_created} normes rythme importées (remplacé {count_before} existantes)")
    
    # Import Normes Concentration
    print("\n🧠 Import des normes de concentration...")
    count_before = NormeCapaciteConcentration.objects.count()
    NormeCapaciteConcentration.objects.all().delete()
    
    normes_concentration_created = 0
    for norme_data in data['normes_concentration']:
        NormeCapaciteConcentration.objects.create(**norme_data)
        normes_concentration_created += 1
    
    print(f"✅ {normes_concentration_created} normes concentration importées (remplacé {count_before} existantes)")
    
    print("\n" + "="*50)
    print("🎉 Import terminé avec succès !")
    print("="*50)
    print(f"\n📊 Résumé :")
    print(f"  - Symboles : {symboles_created}")
    print(f"  - Normes Exactitude : {normes_exactitude_created}")
    print(f"  - Normes Rythme : {normes_rythme_created}")
    print(f"  - Normes Concentration : {normes_concentration_created}")
    print(f"  - TOTAL : {symboles_created + normes_exactitude_created + normes_rythme_created + normes_concentration_created} entrées")

if __name__ == '__main__':
    import_data()