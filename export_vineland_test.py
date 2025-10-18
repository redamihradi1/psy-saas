"""
Script pour exporter un test Vineland en JSON
Usage: python export_vineland_test.py <test_id>
"""

import os
import sys
import django
import json
from datetime import date, datetime

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tests_psy.models import TestVineland, ReponseVineland


def export_test_vineland(test_id):
    """Exporte un test Vineland avec toutes ses données"""
    
    try:
        test = TestVineland.objects.get(id=test_id)
    except TestVineland.DoesNotExist:
        print(f"❌ Test Vineland {test_id} introuvable")
        return None
    
    patient = test.patient
    
    # Préparer les données
    data = {
        'export_date': datetime.now().isoformat(),
        'test_id': test.id,
        'patient': {
            'nom': patient.nom,
            'prenom': patient.prenom,
            'date_naissance': str(patient.date_naissance),
            'categorie_age': patient.categorie_age,  # CHANGÉ
            'email': patient.email or '',
            'telephone': patient.telephone or '',
        },
        'test': {
            'date_passation': str(test.date_passation),
            'psychologue_nom': test.psychologue.last_name or '',
            'psychologue_prenom': test.psychologue.first_name or '',
            'psychologue_email': test.psychologue.email,
        },
        'reponses': []
    }
    
    # Récupérer toutes les réponses
    reponses = ReponseVineland.objects.filter(
        test_vineland=test
    ).select_related(
        'question',
        'question__sous_domaine',
        'question__sous_domaine__domain'
    ).order_by(
        'question__sous_domaine__domain__name',
        'question__sous_domaine__name',
        'question__numero_item'
    )
    
    for reponse in reponses:
        data['reponses'].append({
            'domaine': reponse.question.sous_domaine.domain.name,
            'sous_domaine': reponse.question.sous_domaine.name,
            'numero_item': reponse.question.numero_item,
            'question_texte': reponse.question.texte,
            'reponse': reponse.reponse,
        })
    
    # Sauvegarder dans un fichier JSON
    filename = f'vineland_test_{test_id}_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Export réussi : {filename}")
    print(f"📊 Patient : {patient.nom_complet}")
    print(f"📅 Date de passation : {test.date_passation}")
    print(f"📝 Nombre de réponses : {len(data['reponses'])}")
    
    return filename


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python export_vineland_test.py <test_id>")
        print("Exemple: python export_vineland_test.py 1")
        sys.exit(1)
    
    try:
        test_id = int(sys.argv[1])
        export_test_vineland(test_id)
    except ValueError:
        print("❌ L'ID du test doit être un nombre")
        sys.exit(1)