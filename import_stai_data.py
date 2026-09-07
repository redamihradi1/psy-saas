"""
Script d'import des données de référence pour le test STAI (State-Trait Anxiety Inventory).

Importe les 40 items du questionnaire de Spielberger.

Usage:
    python import_stai_data.py
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tests_psy.models import ItemSTAI


def import_items_stai():
    """
    Importe les 40 items du STAI (20 ÉTAT + 20 TRAIT).
    Items inversés : affirmations positives où le score est inversé.
    """

    # Items inversés (positifs) : 1, 2, 5, 8, 10, 11, 15, 16, 19, 20
    items_inverses_etat = {1, 2, 5, 8, 10, 11, 15, 16, 19, 20}
    # Items inversés (positifs) : 21, 23, 26, 27, 30, 33, 34, 36, 39
    items_inverses_trait = {21, 23, 26, 27, 30, 33, 34, 36, 39}

    items_data = [
        # SECTION ÉTAT (Y1) - Items 1-20
        {'numero': 1, 'texte': 'Je me sens calme.', 'section': 'ETAT'},
        {'numero': 2, 'texte': 'Je me sens en sécurité.', 'section': 'ETAT'},
        {'numero': 3, 'texte': 'Je suis tendu(e).', 'section': 'ETAT'},
        {'numero': 4, 'texte': 'Je me sens surmené(e).', 'section': 'ETAT'},
        {'numero': 5, 'texte': 'Je me sens tranquille.', 'section': 'ETAT'},
        {'numero': 6, 'texte': 'Je me sens ému(e), bouleversé(e).', 'section': 'ETAT'},
        {'numero': 7, 'texte': "Je m'inquiète à l'idée de malheurs possibles.", 'section': 'ETAT'},
        {'numero': 8, 'texte': 'Je me sens comblé(e).', 'section': 'ETAT'},
        {'numero': 9, 'texte': 'Je me sens effrayé(e).', 'section': 'ETAT'},
        {'numero': 10, 'texte': "Je me sens bien, à l'aise.", 'section': 'ETAT'},
        {'numero': 11, 'texte': 'Je me sens sûr(e) de moi.', 'section': 'ETAT'},
        {'numero': 12, 'texte': 'Je me sens nerveux(se).', 'section': 'ETAT'},
        {'numero': 13, 'texte': 'Je suis agité(e).', 'section': 'ETAT'},
        {'numero': 14, 'texte': 'Je me sens indécis(e).', 'section': 'ETAT'},
        {'numero': 15, 'texte': 'Je suis détendu(e).', 'section': 'ETAT'},
        {'numero': 16, 'texte': 'Je me sens satisfait(e).', 'section': 'ETAT'},
        {'numero': 17, 'texte': 'Je suis inquiet(e).', 'section': 'ETAT'},
        {'numero': 18, 'texte': 'Je me sens troublé(e).', 'section': 'ETAT'},
        {'numero': 19, 'texte': "Je sens que j'ai les nerfs solides.", 'section': 'ETAT'},
        {'numero': 20, 'texte': 'Je me sens dans de bonnes dispositions.', 'section': 'ETAT'},

        # SECTION TRAIT (Y2) - Items 21-40
        {'numero': 21, 'texte': 'Je me sens dans de bonnes dispositions.', 'section': 'TRAIT'},
        {'numero': 22, 'texte': 'Je me sens nerveux(se) et agité(e).', 'section': 'TRAIT'},
        {'numero': 23, 'texte': 'Je me sens content(e) de moi-même.', 'section': 'TRAIT'},
        {'numero': 24, 'texte': "Je voudrais être aussi heureux(se) que les autres semblent l'être.", 'section': 'TRAIT'},
        {'numero': 25, 'texte': "J'ai l'impression d'être un(e) raté(e).", 'section': 'TRAIT'},
        {'numero': 26, 'texte': 'Je me sens reposé(e).', 'section': 'TRAIT'},
        {'numero': 27, 'texte': "Je suis d'un grand calme.", 'section': 'TRAIT'},
        {'numero': 28, 'texte': "Je sens que les difficultés s'accumulent au point où je n'arrive pas à les surmonter.", 'section': 'TRAIT'},
        {'numero': 29, 'texte': "Je m'en fais trop pour des choses qui n'en valent pas vraiment la peine.", 'section': 'TRAIT'},
        {'numero': 30, 'texte': 'Je suis heureux(se).', 'section': 'TRAIT'},
        {'numero': 31, 'texte': "J'ai des pensées troublantes.", 'section': 'TRAIT'},
        {'numero': 32, 'texte': 'Je manque de confiance en moi.', 'section': 'TRAIT'},
        {'numero': 33, 'texte': 'Je me sens en sécurité.', 'section': 'TRAIT'},
        {'numero': 34, 'texte': "Prendre des décisions m'est facile.", 'section': 'TRAIT'},
        {'numero': 35, 'texte': "Je sens que je ne suis pas à la hauteur de la situation.", 'section': 'TRAIT'},
        {'numero': 36, 'texte': 'Je suis satisfait(e).', 'section': 'TRAIT'},
        {'numero': 37, 'texte': 'Des idées sans importance me passent par la tête et me tracassent.', 'section': 'TRAIT'},
        {'numero': 38, 'texte': "Je prends les déceptions tellement à cœur que je n'arrive pas à les chasser de mon esprit.", 'section': 'TRAIT'},
        {'numero': 39, 'texte': 'Je suis une personne qui a les nerfs solides.', 'section': 'TRAIT'},
        {'numero': 40, 'texte': 'Je deviens tendu(e) ou bouleversé(e) quand je songe à mes préoccupations et à mes intérêts récents.', 'section': 'TRAIT'},
    ]

    # Détermine est_inverse à partir des listes officielles ci-dessus,
    # au lieu de le coder en dur par item (source du bug précédent : les 40
    # items s'étaient retrouvés à est_inverse=True).
    for item in items_data:
        if item['section'] == 'ETAT':
            item['est_inverse'] = item['numero'] in items_inverses_etat
        else:
            item['est_inverse'] = item['numero'] in items_inverses_trait

    print(f"🚀 Import des {len(items_data)} items STAI...")

    created_count = 0
    updated_count = 0

    for item_data in items_data:
        item, created = ItemSTAI.objects.update_or_create(
            numero=item_data['numero'],
            defaults={
                'texte': item_data['texte'],
                'section': item_data['section'],
                'est_inverse': item_data['est_inverse']
            }
        )

        if created:
            created_count += 1
            print(f"✅ Item {item.numero} créé ({item.section}) {'[INVERSÉ]' if item.est_inverse else ''}")
        else:
            updated_count += 1
            print(f"🔄 Item {item.numero} mis à jour ({item.section}) {'[INVERSÉ]' if item.est_inverse else ''}")

    print(f"\n✨ Import terminé !")
    print(f"   - {created_count} items créés")
    print(f"   - {updated_count} items mis à jour")
    print(f"   - Total: {created_count + updated_count} items")

    # Statistiques
    etat_count = ItemSTAI.objects.filter(section='ETAT').count()
    trait_count = ItemSTAI.objects.filter(section='TRAIT').count()
    inverse_count = ItemSTAI.objects.filter(est_inverse=True).count()

    print(f"\n📊 Statistiques:")
    print(f"   - Items ÉTAT (Y1): {etat_count}")
    print(f"   - Items TRAIT (Y2): {trait_count}")
    print(f"   - Items inversés: {inverse_count}")


if __name__ == '__main__':
    import_items_stai()
