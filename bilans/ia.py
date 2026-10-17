"""Appels à l'IA (Groq, offre gratuite) pour la première version d'un bilan et le chat.

Fournisseur interchangeable : toute API compatible OpenAI (/chat/completions) fonctionne en
changeant IA_API_URL / IA_MODELE dans .env (Groq par défaut : api.groq.com est autorisé sur
les comptes PythonAnywhere gratuits). Aucune dépendance : urllib de la bibliothèque standard.

Tout texte envoyé passe par anonymisation.Pseudonymiseur ; tout texte reçu est restauré.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone

from .models import AppelIA

logger = logging.getLogger(__name__)

TIMEOUT_SECONDES = 60
LIMITE_TEXTE_BILAN = 9000
NB_MESSAGES_HISTORIQUE = 6

REGLES = """Tu es un assistant de rédaction pour psychologues cliniciens (Maroc, rédaction en français).
Règles impératives :
- N'invente JAMAIS de données : aucun score, aucun fait, aucun antécédent qui ne figure pas dans les données fournies. Si une information manque, écris « [à compléter] ».
- Les scores sont calculés par la plateforme : ne les recalcule pas, ne les modifie pas.
- Ne pose pas de diagnostic définitif : formule des hypothèses prudentes (« les résultats évoquent », « compatible avec »), le psychologue reste seul responsable du bilan.
- Les noms sont anonymisés : désigne le patient par « [PRÉNOM] » (jamais par un autre nom), garde tels quels [NOM], [PSYCHOLOGUE], [CABINET], [PERSONNE_n].
- Style professionnel, clair, bienveillant, à la troisième personne. Pas de markdown sauf des listes « - » quand on te demande une liste. Paragraphes séparés par une ligne vide.
- Ne répète jamais le titre de la section dans ton texte : le document l'affiche déjà."""


class IAErreur(Exception):
    """Erreur affichable telle quelle au psychologue."""


def ia_configuree():
    return bool(settings.IA_API_KEY)


def appels_restants(organization):
    debut = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    utilises = AppelIA.all_objects.filter(organization=organization, date__gte=debut).count()
    return max(0, settings.IA_QUOTA_JOUR_PAR_CABINET - utilises)


def _appeler(messages, max_tokens):
    """Appel brut -> (texte, tokens). Lève IAErreur avec un message lisible."""
    if not ia_configuree():
        raise IAErreur("L'assistant IA n'est pas configuré sur ce serveur (clé API manquante).")
    corps = json.dumps({
        'model': settings.IA_MODELE,
        'messages': messages,
        'temperature': 0.4,
        'max_tokens': max_tokens,
        'response_format': {'type': 'json_object'},
    }).encode('utf-8')
    requete = urllib.request.Request(
        settings.IA_API_URL, data=corps, method='POST',
        headers={
            'Authorization': f'Bearer {settings.IA_API_KEY}',
            'Content-Type': 'application/json',
            'User-Agent': 'psy-saas-bilans/1.0',
        },
    )
    try:
        with urllib.request.urlopen(requete, timeout=TIMEOUT_SECONDES) as reponse:
            donnees = json.loads(reponse.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', 'replace')[:300]
        logger.warning("IA HTTP %s : %s", e.code, detail)
        if e.code == 429:
            raise IAErreur("Limite de l'offre gratuite de l'IA atteinte pour le moment : réessayez dans une minute.")
        if e.code in (401, 403):
            raise IAErreur("Clé API de l'IA refusée : vérifiez la configuration du serveur.")
        raise IAErreur(f"Le service d'IA a répondu une erreur ({e.code}). Réessayez plus tard.")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logger.warning("IA injoignable : %s", e)
        raise IAErreur("Le service d'IA est injoignable pour le moment. Réessayez plus tard.")

    try:
        texte = donnees['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        raise IAErreur("Réponse inattendue du service d'IA.")
    tokens = (donnees.get('usage') or {}).get('total_tokens')
    return texte, tokens


def _json(texte):
    """Le modèle renvoie normalement du JSON pur ; tolère un bloc ```json ... ```."""
    texte = (texte or '').strip()
    if texte.startswith('```'):
        texte = texte.strip('`')
        texte = texte[texte.find('{'):]
    debut, fin = texte.find('{'), texte.rfind('}')
    if debut == -1 or fin == -1:
        raise IAErreur("L'IA n'a pas renvoyé de réponse exploitable. Réessayez.")
    try:
        return json.loads(texte[debut:fin + 1])
    except json.JSONDecodeError:
        raise IAErreur("L'IA n'a pas renvoyé de réponse exploitable. Réessayez.")


def appeler_journalise(type_appel, bilan, utilisateur, messages, max_tokens):
    """Vérifie le quota du cabinet, appelle l'IA, journalise l'appel -> dict JSON de réponse."""
    if appels_restants(bilan.organization) <= 0:
        raise IAErreur(f"Quota quotidien d'appels IA atteint pour ce cabinet "
                       f"({settings.IA_QUOTA_JOUR_PAR_CABINET} par jour). Réessayez demain.")
    journal = AppelIA(organization=bilan.organization, utilisateur=utilisateur, bilan=bilan, type_appel=type_appel)
    try:
        texte, journal.tokens = _appeler(messages, max_tokens)
        resultat = _json(texte)
        journal.succes = True
        return resultat
    except IAErreur as e:
        journal.erreur = str(e)[:255]
        raise
    finally:
        journal.save()


# --- prompts ---------------------------------------------------------------------------------

def messages_premier_jet(titre_modele, contexte_masque, sections):
    """sections : [{'cle', 'titre', 'consigne'}] à rédiger."""
    liste = '\n'.join(f'- "{s["cle"]}" ({s["titre"]}) : {s["consigne"]}' for s in sections)
    cles = ', '.join(f'"{s["cle"]}": "..."' for s in sections)
    utilisateur = (
        f"Rédige la première version des sections d'un « {titre_modele} ».\n\n"
        f"DONNÉES DU PATIENT\n{contexte_masque}\n\n"
        f"SECTIONS À RÉDIGER\n{liste}\n\n"
        f"Réponds uniquement avec un objet JSON de la forme {{\"sections\": {{{cles}}}}}, "
        "chaque valeur étant le texte de la section."
    )
    return [{'role': 'system', 'content': REGLES}, {'role': 'user', 'content': utilisateur}]


def messages_chat(texte_bilan_masque, contexte_masque, historique, demande_masquee, selection_masquee):
    """historique : [(role 'psy'|'ia', texte masqué)] des derniers échanges."""
    consigne = (
        REGLES + "\n\nTu aides le psychologue à retravailler son bilan. Réponds uniquement avec un objet JSON "
        "{\"reponse\": \"message court au psychologue\", \"proposition\": \"texte proposé ou null\"}. "
        "Quand il demande une modification ou un texte, mets le texte prêt à l'emploi dans \"proposition\" "
        "(sans commentaire autour). S'il a sélectionné un passage, ta proposition REMPLACERA ce passage : "
        "renvoie le passage entier réécrit. Pour une simple question, \"proposition\" vaut null."
    )
    contexte = (
        f"DONNÉES DU PATIENT\n{contexte_masque}\n\n"
        f"BILAN ACTUEL\n{texte_bilan_masque[:LIMITE_TEXTE_BILAN]}"
    )
    messages = [{'role': 'system', 'content': consigne}, {'role': 'user', 'content': contexte},
                {'role': 'assistant', 'content': '{"reponse": "J\'ai pris connaissance du bilan et des données.", '
                                                 '"proposition": null}'}]
    for role, texte in historique[-NB_MESSAGES_HISTORIQUE:]:
        if role == 'psy':
            messages.append({'role': 'user', 'content': texte})
        else:
            messages.append({'role': 'assistant', 'content': json.dumps({'reponse': texte, 'proposition': None},
                                                                      ensure_ascii=False)})
    demande = demande_masquee
    if selection_masquee:
        demande = f"Passage sélectionné :\n« {selection_masquee} »\n\nDemande : {demande_masquee}"
    messages.append({'role': 'user', 'content': demande})
    return messages
