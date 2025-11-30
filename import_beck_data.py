#!/usr/bin/env python
"""
Script d'import des items et phrases du Beck Depression Inventory (BDI-II)
Usage: python import_beck_data.py
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tests_psy.models import ItemBeck, PhraseBeck

def import_beck_data():
    """Importe tous les items et phrases du BDI-II"""

    print("🔄 Import des données Beck Depression Inventory...")

    # Supprimer les données existantes (optionnel)
    PhraseBeck.objects.all().delete()
    ItemBeck.objects.all().delete()

    # Données complètes du BDI-II
    beck_data = [
        {
            'numero': 1,
            'categorie': 'Tristesse',
            'phrases': [
                (0, "Je ne me sens pas triste."),
                (1, "Je me sens morose ou triste."),
                (2, "Je suis morose ou triste tout le temps et je ne peux pas me remettre d'aplomb."),
                (2, "Je suis tellement triste ou malheureux(se) que cela me fait mal."),
                (3, "Je suis tellement triste ou malheureux(se) que je ne peux plus le supporter."),
            ]
        },
        {
            'numero': 2,
            'categorie': 'Pessimisme',
            'phrases': [
                (0, "Je ne suis pas particulièrement pessimiste ou découragé(e) à propos du futur."),
                (1, "Je me sens découragé(e) à propos du futur."),
                (2, "Je sens que je n'ai rien à attendre du futur."),
                (2, "Je sens que je n'arriverai jamais à surmonter mes difficultés."),
                (3, "Je sens que le futur est sans espoir et que les choses ne peuvent pas s'améliorer."),
            ]
        },
        {
            'numero': 3,
            'categorie': 'Échec',
            'phrases': [
                (0, "Je ne sens pas que je suis un échec."),
                (1, "Je sens que j'ai échoué plus que la moyenne des gens."),
                (2, "Je sens que j'ai accompli très peu de choses qui aient de la valeur ou une signification quelconque."),
                (2, "Quand je pense à ma vie passée, je ne peux voir rien d'autre qu'un grand nombre d'échecs."),
                (3, "Je sens que je suis un échec complet en tant que personne (parent, mari, femme)."),
            ]
        },
        {
            'numero': 4,
            'categorie': 'Perte de plaisir',
            'phrases': [
                (0, "Je ne suis pas particulièrement mécontent(e)."),
                (1, "Je me sens \"tanné(e)\" la plupart du temps."),
                (2, "Je ne prends pas plaisir aux choses comme auparavant."),
                (2, "Je n'obtiens plus de satisfaction de quoi que ce soit."),
                (3, "Je suis mécontent(e) de tout."),
            ]
        },
        {
            'numero': 5,
            'categorie': 'Sentiment de culpabilité',
            'phrases': [
                (0, "Je ne me sens pas particulièrement coupable."),
                (1, "Je me sens souvent mauvais(e) ou indigne."),
                (1, "Je me sens plutôt coupable."),
                (2, "Je me sens mauvais(e) et indigne presque tout le temps."),
                (3, "Je sens que je suis très mauvais(e) ou très indigne."),
            ]
        },
        {
            'numero': 6,
            'categorie': 'Sentiment de punition',
            'phrases': [
                (0, "Je n'ai pas l'impression d'être puni(e)."),
                (1, "J'ai l'impression que quelque chose de malheureux peut m'arriver."),
                (2, "Je sens que je suis ou serai puni(e)."),
                (3, "Je sens que je mérite d'être puni(e)."),
                (3, "Je veux être puni(e)."),
            ]
        },
        {
            'numero': 7,
            'categorie': 'Déception de soi',
            'phrases': [
                (0, "Je ne me sens pas déçu(e) de moi-même."),
                (1, "Je suis déçu(e) de moi-même."),
                (1, "Je ne m'aime pas."),
                (2, "Je suis dégoûté(e) de moi-même."),
                (3, "Je me hais."),
            ]
        },
        {
            'numero': 8,
            'categorie': 'Autocritique',
            'phrases': [
                (0, "Je ne sens pas que je suis pire que les autres."),
                (1, "Je me critique pour mes faiblesses et mes erreurs."),
                (2, "Je me blâme pour mes fautes."),
                (3, "Je me blâme pour tout ce qui m'arrive de mal."),
            ]
        },
        {
            'numero': 9,
            'categorie': 'Idées suicidaires',
            'phrases': [
                (0, "Je n'ai aucune idée de me faire du mal."),
                (1, "J'ai des idées de me faire du mal mais je ne les mettrais pas à exécution."),
                (2, "Je sens que je serais mieux mort(e)."),
                (2, "Je sens que ma famille serait mieux si j'étais mort(e)."),
                (3, "J'ai des plans définis pour un acte suicidaire."),
                (3, "Je me tuerais si je le pouvais."),
            ]
        },
        {
            'numero': 10,
            'categorie': 'Pleurs',
            'phrases': [
                (0, "Je ne pleure pas plus que d'habitude."),
                (1, "Je pleure plus maintenant qu'auparavant."),
                (2, "Je pleure tout le temps maintenant. Je ne peux plus m'arrêter."),
                (3, "Auparavant, j'étais capable de pleurer mais maintenant je ne peux pas pleurer du tout, même si je le veux."),
            ]
        },
        {
            'numero': 11,
            'categorie': 'Agitation',
            'phrases': [
                (0, "Je ne suis pas plus irrité(e) maintenant que je le suis d'habitude."),
                (1, "Je deviens contrarié(e) ou irrité(e) plus facilement maintenant qu'en temps ordinaire."),
                (2, "Je me sens irrité(e) tout le temps."),
                (3, "Je ne suis plus irrité(e) du tout par les choses qui m'irritent habituellement."),
            ]
        },
        {
            'numero': 12,
            'categorie': 'Perte d\'intérêt',
            'phrases': [
                (0, "Je n'ai pas perdu intérêt aux autres."),
                (1, "Je suis moins intéressé(e) aux autres maintenant qu'auparavant."),
                (2, "J'ai perdu la plupart de mon intérêt pour les autres et j'ai peu de sentiment pour eux."),
                (3, "J'ai perdu tout mon intérêt pour les autres et je ne me soucie pas d'eux du tout."),
            ]
        },
        {
            'numero': 13,
            'categorie': 'Indécision',
            'phrases': [
                (0, "Je prends des décisions aussi bien que d'habitude."),
                (1, "J'essaie de remettre à plus tard mes décisions."),
                (2, "J'ai beaucoup de difficultés à prendre des décisions."),
                (3, "Je ne suis pas capable de prendre des décisions du tout."),
            ]
        },
        {
            'numero': 14,
            'categorie': 'Dévalorisation',
            'phrases': [
                (0, "Je n'ai pas l'impression de paraître pire qu'auparavant."),
                (1, "Je m'inquiète de paraître vieux(vieille) et sans attrait."),
                (2, "Je sens qu'il y a des changements permanents dans mon apparence et que ces changements me font paraître sans attrait."),
                (3, "Je me sens laid(e) et répugnant(e)."),
            ]
        },
        {
            'numero': 15,
            'categorie': 'Perte d\'énergie',
            'phrases': [
                (0, "Je peux travailler pratiquement aussi bien qu'avant."),
                (1, "J'ai besoin de faire des efforts supplémentaires pour commencer à faire quelque chose."),
                (1, "Je ne travaille pas aussi bien qu'avant."),
                (2, "J'ai besoin de me pousser fort pour faire quoi que ce soit."),
                (3, "Je ne peux faire aucun travail."),
            ]
        },
        {
            'numero': 16,
            'categorie': 'Modifications du sommeil',
            'phrases': [
                (0, "Je peux dormir aussi bien que d'habitude."),
                (1, "Je me réveille plus fatigué(e) que d'habitude."),
                (2, "Je me réveille 1-2 heures plus tôt que d'habitude et j'ai de la difficulté à me rendormir."),
                (3, "Je me réveille tôt chaque jour et je ne peux dormir plus de cinq heures."),
            ]
        },
        {
            'numero': 17,
            'categorie': 'Irritabilité',
            'phrases': [
                (0, "Je ne suis pas plus fatigué(e) que d'habitude."),
                (1, "Je me fatigue plus facilement qu'avant."),
                (2, "Je me fatigue à faire quoi que ce soit."),
                (3, "Je suis trop fatigué(e) pour faire quoi que ce soit."),
            ]
        },
        {
            'numero': 18,
            'categorie': 'Perte d\'appétit',
            'phrases': [
                (0, "Mon appétit est aussi bon que d'habitude."),
                (1, "Mon appétit n'est plus aussi bon que d'habitude."),
                (2, "Mon appétit est beaucoup moins bon maintenant."),
                (3, "Je n'ai plus d'appétit du tout."),
            ]
        },
        {
            'numero': 19,
            'categorie': 'Perte de poids',
            'phrases': [
                (0, "Je n'ai pas perdu beaucoup de poids (si j'en ai vraiment perdu dernièrement)."),
                (1, "J'ai perdu plus de 5 livres."),
                (2, "J'ai perdu plus de 10 livres."),
                (3, "J'ai perdu plus de 15 livres."),
            ]
        },
        {
            'numero': 20,
            'categorie': 'Préoccupations somatiques',
            'phrases': [
                (0, "Je ne suis pas plus préoccupé(e) de ma santé que d'habitude."),
                (1, "Je suis préoccupé(e) par des maux ou des douleurs, ou des problèmes de digestion ou de constipation."),
                (2, "Je suis tellement préoccupé(e) par ce que je ressens ou comment je me sens qu'il est difficile pour moi de penser à autre chose."),
                (3, "Je pense seulement à ce que je ressens ou comment je me sens."),
            ]
        },
        {
            'numero': 21,
            'categorie': 'Perte d\'intérêt pour le sexe',
            'phrases': [
                (0, "Je n'ai noté aucun changement récent dans mon intérêt pour le sexe."),
                (1, "Je suis moins intéressé(e) par le sexe qu'auparavant."),
                (2, "Je suis beaucoup moins intéressé(e) par le sexe maintenant."),
                (3, "J'ai complètement perdu mon intérêt pour le sexe."),
            ]
        },
    ]

    # Import des données
    total_items = 0
    total_phrases = 0

    for data in beck_data:
        # Créer l'item
        item = ItemBeck.objects.create(
            numero=data['numero'],
            categorie=data['categorie']
        )
        total_items += 1
        print(f"  ✓ Item {item.numero}: {item.categorie}")

        # Créer les phrases
        for ordre, (score, texte) in enumerate(data['phrases'], start=1):
            PhraseBeck.objects.create(
                item=item,
                score_valeur=score,
                texte=texte,
                ordre=ordre
            )
            total_phrases += 1

    print(f"\n✅ Import terminé !")
    print(f"   📊 {total_items} items créés")
    print(f"   📝 {total_phrases} phrases créées")
    print(f"\n🎯 Le test Beck est prêt à être utilisé !")


if __name__ == '__main__':
    import_beck_data()
