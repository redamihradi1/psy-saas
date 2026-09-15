from django import template
from django.utils.safestring import mark_safe

register = template.Library()
@register.filter
def sum_scores(domain_scores):
    """Calcule la somme des scores bruts d'un domaine"""
    total = 0
    for score in domain_scores.values():
        if isinstance(score, dict) and 'note_brute' in score:
            total += score['note_brute']
    return total

@register.filter
def sum_echelle_v(domain_scores):
    """Calcule la somme des notes échelle-V d'un domaine"""
    total = 0
    
    # Si c'est déjà un dict_values, on itère directement
    if isinstance(domain_scores, type({}.values())):
        for score in domain_scores:
            if isinstance(score, dict) and 'note_echelle_v' in score and score['note_echelle_v'] is not None:
                total += score['note_echelle_v']
    # Si c'est un dict, on prend les values
    elif isinstance(domain_scores, dict):
        for score in domain_scores.values():
            if isinstance(score, dict) and 'note_echelle_v' in score and score['note_echelle_v'] is not None:
                total += score['note_echelle_v']
    
    return total

@register.filter
def subtract(value, arg):
    """Soustraction de deux valeurs"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def multiply(value, arg):
    """Multiplication de deux valeurs"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def split(value, delimiter):
    """Split une chaîne"""
    return value.split(delimiter)

@register.filter
def split_notes(value):
    """
    Split les notes sur les points ou tirets pour affichage en liste
    """
    if not value:
        return []
    
    # Remplacer les différents séparateurs possibles
    value = value.replace('. ', '.|')
    value = value.replace('- ', '-|')
    value = value.replace('• ', '•|')
    
    # Splitter sur le séparateur temporaire
    notes = value.split('|')
    
    # Nettoyer chaque note
    cleaned_notes = []
    for note in notes:
        note = note.strip()
        # Enlever les séparateurs en début de ligne
        note = note.lstrip('.-•').strip()
        if note:
            cleaned_notes.append(note)
    
    return cleaned_notes

@register.filter
def get_item(dictionary, key):
    """Récupère un élément d'un dictionnaire avec une clé"""
    if dictionary is None:
        return None
    if not isinstance(dictionary, dict):
        return None
    
    key_str = str(key)
    result = dictionary.get(key_str)
    return result


@register.filter
def is_checked(initial_data, question_and_value):
    """
    Vérifie si une question doit être cochée
    Usage: {% if initial_data|is_checked:"question_1_5:2" %}checked{% endif %}
    """
    if not initial_data or not question_and_value:
        return False
    
    try:
        question_key, expected_value = question_and_value.split(':')
        current_value = str(initial_data.get(question_key, ''))
        expected_value = str(expected_value)
        return current_value == expected_value
    except (ValueError, AttributeError):
        return False

@register.filter
def divide(value, arg):
    """Division de deux valeurs"""
    try:
        return int(value) / int(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0