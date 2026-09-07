"""
Vue Vineland, découpée en modules :
- scoring: calcul des scores bruts, mapping échelle-V, scores de domaine
- comparisons: comparaisons par paires (domaines/sous-domaines/inter-domaines)
- pdf: génération du rapport PDF
- views: les vues Django elles-mêmes

Tout est ré-exporté ici pour que `tests_psy.views.vineland.<nom>` continue
de fonctionner exactement comme avant (utilisé par tests_psy/urls.py et
les tests), sans changer l'API publique du module.
"""
from .scoring import (
    get_patient_age, get_age_tranches, calculate_item_plancher, calculate_all_scores,
    find_echelle_v_mapping, get_domain_mapping, calculate_domain_scores,
)
from .comparisons import (
    extract_number, get_frequency_percentage, find_domain_comparison, find_domain_frequency,
    find_sous_domaine_comparison, find_sous_domaine_frequency, generate_domain_comparisons,
    generate_sous_domaine_comparisons, generate_interdomaine_comparisons,
)
from .pdf import (
    create_pdf_styles, create_cover_page, create_scores_summary, create_domain_score_table,
    create_subdomain_score_table, get_score_table_style, create_comparisons_section,
    get_simple_age_range, create_domain_comparison_table, create_subdomain_comparison_table,
    create_interdomain_comparison_table, get_comparison_table_style,
)
from .views import (
    vineland_liste, vineland_nouveau, vineland_questionnaire, vineland_scores,
    vineland_echelle_v, vineland_resultats, vineland_pdf, vineland_comparaisons,
)

__all__ = [
    'get_patient_age', 'get_age_tranches', 'calculate_item_plancher', 'calculate_all_scores',
    'find_echelle_v_mapping', 'get_domain_mapping', 'calculate_domain_scores',
    'extract_number', 'get_frequency_percentage', 'find_domain_comparison', 'find_domain_frequency',
    'find_sous_domaine_comparison', 'find_sous_domaine_frequency', 'generate_domain_comparisons',
    'generate_sous_domaine_comparisons', 'generate_interdomaine_comparisons',
    'create_pdf_styles', 'create_cover_page', 'create_scores_summary', 'create_domain_score_table',
    'create_subdomain_score_table', 'get_score_table_style', 'create_comparisons_section',
    'get_simple_age_range', 'create_domain_comparison_table', 'create_subdomain_comparison_table',
    'create_interdomain_comparison_table', 'get_comparison_table_style',
    'vineland_liste', 'vineland_nouveau', 'vineland_questionnaire', 'vineland_scores',
    'vineland_echelle_v', 'vineland_resultats', 'vineland_pdf', 'vineland_comparaisons',
]
