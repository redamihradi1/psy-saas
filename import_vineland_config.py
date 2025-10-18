# import_vineland_config.py
import os
import sys
import django
import json

# Ajouter le répertoire du projet au path Python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tests_psy.models import (
    Domain, SousDomain,
    QuestionVineland, PlageItemVineland, EchelleVMapping,
    NoteDomaineVMapping, IntervaleConfianceSousDomaine,
    IntervaleConfianceDomaine, NiveauAdaptatif,
    AgeEquivalentSousDomaine, ComparaisonDomaineVineland,
    ComparaisonSousDomaineVineland, FrequenceDifferenceDomaineVineland,
    FrequenceDifferenceSousDomaineVineland
)


def import_data(json_file):
    """
    Import les données de configuration depuis un fichier JSON
    
    Args:
        json_file: Chemin vers le fichier JSON à importer
    """
    
    if not os.path.exists(json_file):
        print(f"❌ Fichier introuvable : {json_file}")
        return
    
    print("\n" + "="*60)
    print("📦 IMPORT DE CONFIGURATION")
    print("="*60 + "\n")
    print(f"📁 Fichier : {json_file}\n")
    
    # Charger le JSON
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Maps pour stocker les correspondances ID -> Objet
    domain_map = {}
    sous_domain_map = {}
    
    # Import Domaines
    print("📁 Import des domaines...")
    for domain_data in data.get('domains', []):
        domain, created = Domain.objects.get_or_create(
            name=domain_data['name'],
            defaults={
                'description': '',
                'ordre': 0
            }
        )
        domain_map[domain_data['name']] = domain
        if created:
            print(f"   ✅ Créé : {domain.name}")
        else:
            print(f"   ℹ️  Existe déjà : {domain.name}")
    
    # Import Sous-Domaines
    print("\n📂 Import des sous-domaines...")
    for sous_domain_data in data.get('sous_domains', []):
        domain_name = sous_domain_data['domain_name']
        if domain_name not in domain_map:
            print(f"   ⚠️  Domaine parent introuvable pour : {sous_domain_data['name']}")
            continue
        
        sous_domain, created = SousDomain.objects.get_or_create(
            domain=domain_map[domain_name],
            name=sous_domain_data['name'],
            defaults={
                'description': '',
                'ordre': 0
            }
        )
        sous_domain_map[sous_domain_data['name']] = sous_domain
        if created:
            print(f"   ✅ Créé : {domain_name} → {sous_domain.name}")
        else:
            print(f"   ℹ️  Existe déjà : {domain_name} → {sous_domain.name}")
    
    # Import Questions
    print("\n❓ Import des questions...")
    questions_created = 0
    questions_updated = 0
    for question_data in data.get('questions', []):
        sous_domaine_name = question_data['sous_domaine_name']
        if sous_domaine_name not in sous_domain_map:
            print(f"   ⚠️  Sous-domaine introuvable pour question #{question_data['numero_item']}")
            continue
        
        question, created = QuestionVineland.objects.update_or_create(
            sous_domaine=sous_domain_map[sous_domaine_name],
            numero_item=question_data['numero_item'],
            defaults={
                'texte': question_data['texte'],
                'note': question_data.get('note', ''),
                'permet_na': question_data.get('permet_na', False)
            }
        )
        if created:
            questions_created += 1
        else:
            questions_updated += 1
    
    print(f"   ✅ Créées : {questions_created}")
    print(f"   🔄 Mises à jour : {questions_updated}")
    
    # Import Plages d'items
    print("\n📊 Import des plages d'items...")
    plages_created = 0
    for plage_data in data.get('plages_items', []):
        sous_domaine_name = plage_data['sous_domaine_name']
        if sous_domaine_name not in sous_domain_map:
            continue
        
        plage, created = PlageItemVineland.objects.get_or_create(
            sous_domaine=sous_domain_map[sous_domaine_name],
            item_debut=plage_data['item_debut'],
            item_fin=plage_data['item_fin'],
            defaults={
                'age_debut': plage_data['age_debut'],
                'age_fin': plage_data.get('age_fin')
            }
        )
        if created:
            plages_created += 1
    
    print(f"   ✅ Créées : {plages_created}")
    
    # Import Mappings Échelle-V
    print("\n📈 Import des mappings échelle-V...")
    mappings_created = 0
    for mapping_data in data.get('echelle_v_mappings', []):
        sous_domaine_name = mapping_data['sous_domaine_name']
        if sous_domaine_name not in sous_domain_map:
            continue
        
        mapping, created = EchelleVMapping.objects.get_or_create(
            sous_domaine=sous_domain_map[sous_domaine_name],
            age_debut_annee=mapping_data['age_debut_annee'],
            age_debut_mois=mapping_data['age_debut_mois'],
            age_fin_annee=mapping_data['age_fin_annee'],
            age_fin_mois=mapping_data['age_fin_mois'],
            note_brute_min=mapping_data['note_brute_min'],
            note_brute_max=mapping_data['note_brute_max'],
            defaults={
                'age_debut_jour': mapping_data.get('age_debut_jour', 0),
                'age_fin_jour': mapping_data.get('age_fin_jour', 0),
                'note_echelle_v': mapping_data['note_echelle_v']
            }
        )
        if created:
            mappings_created += 1
    
    print(f"   ✅ Créés : {mappings_created}")
    
    # Import Mappings Notes Domaines
    print("\n🎯 Import des mappings notes domaines...")
    note_mappings_created = 0
    for mapping_data in data.get('note_domaine_mappings', []):
        mapping, created = NoteDomaineVMapping.objects.get_or_create(
            tranche_age=mapping_data['tranche_age'],
            note_standard=mapping_data['note_standard'],
            defaults={
                'communication_min': mapping_data.get('communication_min'),
                'communication_max': mapping_data.get('communication_max'),
                'vie_quotidienne_min': mapping_data.get('vie_quotidienne_min'),
                'vie_quotidienne_max': mapping_data.get('vie_quotidienne_max'),
                'socialisation_min': mapping_data.get('socialisation_min'),
                'socialisation_max': mapping_data.get('socialisation_max'),
                'motricite_min': mapping_data.get('motricite_min'),
                'motricite_max': mapping_data.get('motricite_max'),
                'note_composite_min': mapping_data.get('note_composite_min'),
                'note_composite_max': mapping_data.get('note_composite_max'),
                'rang_percentile': mapping_data['rang_percentile']
            }
        )
        if created:
            note_mappings_created += 1
    
    print(f"   ✅ Créés : {note_mappings_created}")
    
    # Import Intervalles Confiance Sous-Domaine
    print("\n📏 Import des intervalles de confiance (sous-domaines)...")
    intervalles_sd_created = 0
    for intervalle_data in data.get('intervalles_confiance_sous_domaine', []):
        sous_domaine_name = intervalle_data['sous_domaine_name']
        if sous_domaine_name not in sous_domain_map:
            continue
        
        intervalle, created = IntervaleConfianceSousDomaine.objects.get_or_create(
            age=intervalle_data['age'],
            niveau_confiance=intervalle_data['niveau_confiance'],
            sous_domaine=sous_domain_map[sous_domaine_name],
            defaults={
                'intervalle': intervalle_data['intervalle']
            }
        )
        if created:
            intervalles_sd_created += 1
    
    print(f"   ✅ Créés : {intervalles_sd_created}")
    
    # Import Intervalles Confiance Domaine
    print("\n📐 Import des intervalles de confiance (domaines)...")
    intervalles_d_created = 0
    for intervalle_data in data.get('intervalles_confiance_domaine', []):
        domain_name = intervalle_data['domain_name']
        if domain_name not in domain_map:
            continue
        
        intervalle, created = IntervaleConfianceDomaine.objects.get_or_create(
            age=intervalle_data['age'],
            niveau_confiance=intervalle_data['niveau_confiance'],
            domain=domain_map[domain_name],
            defaults={
                'intervalle': intervalle_data['intervalle'],
                'note_composite': intervalle_data.get('note_composite')
            }
        )
        if created:
            intervalles_d_created += 1
    
    print(f"   ✅ Créés : {intervalles_d_created}")
    
    # Import Niveaux Adaptatifs
    print("\n🎓 Import des niveaux adaptatifs...")
    niveaux_created = 0
    for niveau_data in data.get('niveaux_adaptatifs', []):
        niveau, created = NiveauAdaptatif.objects.get_or_create(
            niveau=niveau_data['niveau'],
            defaults={
                'echelle_v_min': niveau_data['echelle_v_min'],
                'echelle_v_max': niveau_data['echelle_v_max'],
                'note_standard_min': niveau_data['note_standard_min'],
                'note_standard_max': niveau_data['note_standard_max']
            }
        )
        if created:
            niveaux_created += 1
    
    print(f"   ✅ Créés : {niveaux_created}")
    
    # Import Âges Équivalents
    print("\n👶 Import des âges équivalents...")
    ages_created = 0
    for age_data in data.get('ages_equivalents', []):
        sous_domaine_name = age_data['sous_domaine_name']
        if sous_domaine_name not in sous_domain_map:
            continue
        
        age_eq, created = AgeEquivalentSousDomaine.objects.get_or_create(
            sous_domaine=sous_domain_map[sous_domaine_name],
            note_brute_min=age_data['note_brute_min'],
            note_brute_max=age_data.get('note_brute_max'),
            defaults={
                'age_special': age_data.get('age_special'),
                'age_annees': age_data.get('age_annees'),
                'age_mois': age_data.get('age_mois')
            }
        )
        if created:
            ages_created += 1
    
    print(f"   ✅ Créés : {ages_created}")
    
    # Import Comparaisons Domaines
    print("\n⚖️ Import des comparaisons de domaines...")
    comp_d_created = 0
    for comp_data in data.get('comparaisons_domaines', []):
        d1_name = comp_data['domaine1_name']
        d2_name = comp_data['domaine2_name']
        if d1_name not in domain_map or d2_name not in domain_map:
            continue
        
        comp, created = ComparaisonDomaineVineland.objects.get_or_create(
            age=comp_data['age'],
            niveau_significativite=comp_data['niveau_significativite'],
            domaine1=domain_map[d1_name],
            domaine2=domain_map[d2_name],
            defaults={
                'difference_requise': comp_data['difference_requise']
            }
        )
        if created:
            comp_d_created += 1
    
    print(f"   ✅ Créés : {comp_d_created}")
    
    # Import Comparaisons Sous-Domaines
    print("\n⚖️ Import des comparaisons de sous-domaines...")
    comp_sd_created = 0
    for comp_data in data.get('comparaisons_sous_domaines', []):
        sd1_name = comp_data['sous_domaine1_name']
        sd2_name = comp_data['sous_domaine2_name']
        if sd1_name not in sous_domain_map or sd2_name not in sous_domain_map:
            continue
        
        comp, created = ComparaisonSousDomaineVineland.objects.get_or_create(
            age=comp_data['age'],
            niveau_significativite=comp_data['niveau_significativite'],
            sous_domaine1=sous_domain_map[sd1_name],
            sous_domaine2=sous_domain_map[sd2_name],
            defaults={
                'difference_requise': comp_data['difference_requise']
            }
        )
        if created:
            comp_sd_created += 1
    
    print(f"   ✅ Créés : {comp_sd_created}")
    
    # Import Fréquences Domaines
    print("\n📊 Import des fréquences de différence (domaines)...")
    freq_d_created = 0
    for freq_data in data.get('frequences_domaines', []):
        d1_name = freq_data['domaine1_name']
        d2_name = freq_data['domaine2_name']
        if d1_name not in domain_map or d2_name not in domain_map:
            continue
        
        freq, created = FrequenceDifferenceDomaineVineland.objects.get_or_create(
            age=freq_data['age'],
            domaine1=domain_map[d1_name],
            domaine2=domain_map[d2_name],
            defaults={
                'frequence_16': freq_data['frequence_16'],
                'frequence_10': freq_data['frequence_10'],
                'frequence_5': freq_data['frequence_5']
            }
        )
        if created:
            freq_d_created += 1
    
    print(f"   ✅ Créés : {freq_d_created}")
    
    # Import Fréquences Sous-Domaines
    print("\n📊 Import des fréquences de différence (sous-domaines)...")
    freq_sd_created = 0
    for freq_data in data.get('frequences_sous_domaines', []):
        sd1_name = freq_data['sous_domaine1_name']
        sd2_name = freq_data['sous_domaine2_name']
        if sd1_name not in sous_domain_map or sd2_name not in sous_domain_map:
            continue
        
        freq, created = FrequenceDifferenceSousDomaineVineland.objects.get_or_create(
            age=freq_data['age'],
            sous_domaine1=sous_domain_map[sd1_name],
            sous_domaine2=sous_domain_map[sd2_name],
            defaults={
                'frequence_16': freq_data['frequence_16'],
                'frequence_10': freq_data['frequence_10'],
                'frequence_5': freq_data['frequence_5']
            }
        )
        if created:
            freq_sd_created += 1
    
    print(f"   ✅ Créés : {freq_sd_created}")
    
    print("\n" + "="*60)
    print("✅ IMPORT TERMINÉ AVEC SUCCÈS")
    print("="*60 + "\n")


if __name__ == '__main__':
    # Vérifier si un fichier est fourni en argument
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        # Chercher automatiquement les fichiers JSON dans le répertoire
        json_files = [f for f in os.listdir(BASE_DIR) if f.endswith('_config_data.json')]
        
        if not json_files:
            print("❌ Aucun fichier JSON trouvé !")
            print("Usage: python import_vineland_config.py <fichier.json>")
            sys.exit(1)
        elif len(json_files) == 1:
            json_file = os.path.join(BASE_DIR, json_files[0])
            print(f"📁 Fichier trouvé automatiquement : {json_files[0]}")
        else:
            print("\n📋 Plusieurs fichiers JSON trouvés :")
            for i, f in enumerate(json_files, 1):
                print(f"   {i}. {f}")
            
            choice = input("\n👉 Choisissez le fichier à importer (1-{}): ".format(len(json_files)))
            try:
                choice = int(choice)
                if 1 <= choice <= len(json_files):
                    json_file = os.path.join(BASE_DIR, json_files[choice - 1])
                else:
                    print("❌ Choix invalide !")
                    sys.exit(1)
            except ValueError:
                print("❌ Choix invalide !")
                sys.exit(1)
    
    import_data(json_file)