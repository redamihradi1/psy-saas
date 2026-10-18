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
LIMITE_TEXTE_RELECTURE = 16000
NB_MESSAGES_HISTORIQUE = 6

REGLES = """Tu es un assistant de rédaction pour psychologues cliniciens (Maroc, rédaction en français).
Règles impératives :
- N'invente JAMAIS de données : aucun score, aucun fait, aucun antécédent qui ne figure pas dans les données fournies. Ne comble jamais un manque par des généralités plausibles (« l'enseignant signale », « les parents rapportent », « depuis le CP ») : si une information manque, écris « [à compléter : ce qu'il faut renseigner] ».
- Reprends le niveau de chaque score tel qu'il figure dans les tableaux (colonne de description ou de lecture) : ne le requalifie pas.
- Les scores sont calculés par la plateforme : ne les recalcule pas, ne les modifie pas.
- Ne pose pas de diagnostic définitif : formule des hypothèses prudentes (« les résultats évoquent », « compatible avec »), le psychologue reste seul responsable du bilan.
- Les noms sont anonymisés : désigne le patient par « [PRÉNOM] » (jamais par un autre nom), garde tels quels [NOM], [PSYCHOLOGUE], [CABINET], [PERSONNE_n].
- Style professionnel, clair, bienveillant, à la troisième personne. Pas de markdown sauf des listes « - » quand on te demande une liste. Paragraphes séparés par une ligne vide.
- Ne répète jamais le titre de la section dans ton texte : le document l'affiche déjà.
- Les noms de lieux et de personnes de l'entourage sont aussi anonymisés ([PERSONNE_n]) : garde ces étiquettes telles quelles."""

STYLE = """Style de rédaction attendu (celui des bilans neuropsychologiques du cabinet) :
- Registre clinique soutenu, phrases complètes, présent de l'indicatif, troisième personne.
- Cite les scores entre parenthèses au fil du texte : « (ICV = 129 ; P97) », « (NS = 14) », « (T = 84 ; P98) », « (CCT = 72 ; P3) ». Reprends exactement les valeurs des tableaux.
- Formulations nuancées : « suggère », « évoque », « traduit », « apparaît compatible avec », « sans permettre de conclure à », « à interpréter avec prudence ».
- Pour chaque résultat : le niveau obtenu, ce que l'épreuve sollicite, puis ce que cela traduit concrètement (en classe, pour les devoirs, au travail, au quotidien).
- Mets les épreuves en relation : convergences, dissociations (ex. mémoire de travail préservée en situation structurée mais difficultés rapportées au quotidien), rôle de la contrainte de temps, de la double tâche, de l'anxiété.
- Distingue les ressources (points d'appui) des fragilités.
- Désigne le patient par son prénom [PRÉNOM] ; pour un adulte, si une civilité est indiquée dans les données, utilise « Mme [NOM] » ou « M. [NOM] » selon cette indication, sinon [PRÉNOM]."""

CONSIGNES_TESTS = {
    'wechsler': "Interprète l'échelle de Wechsler : commence par l'homogénéité du profil et la valeur du QIT "
                "(interprétable ou non, selon l'écart entre indices indiqué), puis consacre un sous-titre « ## » à "
                "chaque indice (ex. « ## Compétences verbales - ICV = 103 ») avec son niveau, les subtests qui le "
                "composent et leurs notes standard, ce que cela traduit concrètement ; signale les points forts et "
                "faibles relatifs. Termine par un sous-titre « ## Analyse du profil » sur les dissociations entre "
                "indices et leur retentissement.",
    'brief': "Interprète le BRIEF échelle par échelle : pour chaque échelle et chaque indice, une ligne « **Nom de "
             "l'échelle** : définition en une phrase », puis une ligne « Note T = x | Percentile = y », puis un "
             "paragraphe d'interprétation selon les seuils (65 et plus cliniquement significatif, 60 à 64 "
             "légèrement élevé, sinon dans la norme ; un score bas signifie l'absence de difficulté). Termine par "
             "les indices (IRC, IM, CEG) et ce que le profil dit du fonctionnement quotidien.",
    'd2r': "Interprète le d2-R : attention sélective (exactitude, taux d'erreurs), rythme de traitement (CCT), "
           "capacité de concentration (CC), puis le profil (réfléchi, impulsif...) : précision privilégiée au "
           "détriment de la vitesse ou l'inverse.",
    'teach': "Interprète la TEA-Ch par composante, avec un sous-titre « ## » pour chacune : attention sélective, "
             "attention soutenue, attention divisée, contrôle attentionnel et flexibilité. Pour chaque subtest, "
             "cite le pourcentage cumulé et ce qu'il traduit. Termine par les ressources préservées et les secteurs "
             "de fragilité.",
    'tmt': "Interprète le TMT : vitesse et exploration visuelle (partie A), flexibilité et alternance (partie B), "
           "coût de l'alternance (B - A et B/A), erreurs. Conclus sur ce que le profil évoque (lenteur d'exécution, "
           "difficulté spécifique de flexibilité ou non).",
    'stroop': "Interprète le Stroop : automatismes (lecture, dénomination) puis contrôle inhibiteur en condition "
              "d'interférence (temps, erreurs) et sensibilité à l'interférence.",
    'rcads': "Interprète la RCADS : situe chaque total et les échelles élevées par rapport aux seuils (65 zone "
             "limite, 70 seuil clinique) sans exagérer : un score T inférieur à 65 est dans la norme. Puis une "
             "phrase de synthèse sur le profil émotionnel.",
    'bhk': "Interprète le BHK : qualité graphique (note de dégradation et critères les plus touchés), vitesse si "
           "elle est fournie, et retentissement sur les tâches écrites (coût cognitif, fatigabilité).",
    'questionnaire': "Interprète ce questionnaire ou entretien : résultat par rapport au seuil indiqué et ce qu'il "
                     "évoque, en rappelant qu'un questionnaire ne suffit pas à poser un diagnostic.",
    'emotionnel': "Interprète ce score : niveau indiqué dans le tableau (ne le modifie pas) et manifestations "
                  "possibles au quotidien, en lien avec le reste du bilan.",
    'defaut': "Interprète les résultats de cette épreuve : ce qu'elle mesure, le niveau obtenu à chaque mesure, "
              "ce que cela traduit concrètement, et les liens avec les autres épreuves.",
}


def consigne_test(item):
    """Consigne d'interprétation d'un chapitre de test (item de donnees.tests_inclus)."""
    from .tests_externes import TESTS
    cle = item['cle']
    if cle in ('brief', 'brief_papier'):
        cle_consigne = 'brief'
    elif cle in ('d2r', 'd2r_papier'):
        cle_consigne = 'd2r'
    elif TESTS.get(cle, {}).get('type') == 'wechsler':
        cle_consigne = 'wechsler'
    elif cle in CONSIGNES_TESTS:
        cle_consigne = cle
    elif item['domaine'] in ('questionnaire', 'emotionnel'):
        cle_consigne = item['domaine']
    else:
        cle_consigne = 'defaut'
    return (f"Interprétation des résultats « {item['titre']} » (le tableau est déjà dans le document, ne le "
            f"recopie pas). " + CONSIGNES_TESTS[cle_consigne])


class IAErreur(Exception):
    """Erreur affichable telle quelle au psychologue. `attendre` : secondes avant de réessayer
    (limite par minute de l'offre gratuite) - l'éditeur relance alors tout seul."""

    def __init__(self, message, attendre=None):
        super().__init__(message)
        self.attendre = attendre


def ia_configuree():
    return bool(settings.IA_API_KEY)


def appels_restants(organization):
    debut = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    # Seuls les appels réussis comptent : une limite atteinte ou une panne ne coûte rien au cabinet
    utilises = AppelIA.all_objects.filter(organization=organization, date__gte=debut, succes=True).count()
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
        # Modèles à raisonnement (gpt-oss) : raisonnement bref, pour garder les jetons pour le texte
        **({'reasoning_effort': 'low'} if 'gpt-oss' in settings.IA_MODELE else {}),
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
        if e.code == 413:
            raise IAErreur("Demande trop longue pour l'offre gratuite de l'IA : réduisez les données envoyées "
                           "(moins de notes de séance) ou rédigez section par section.")
        if e.code == 429:
            try:
                attendre = min(90, max(5, int(float(e.headers.get('retry-after') or 20))))
            except (TypeError, ValueError, AttributeError):
                attendre = 20
            raise IAErreur("Limite par minute de l'offre gratuite de l'IA atteinte : reprise dans quelques secondes.",
                           attendre=attendre)
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


def jetons_estimes(messages):
    """Estimation prudente (environ 3,3 caractères par jeton en français)."""
    return int(sum(len(m['content']) for m in messages) / 3.3) + 50


def max_tokens_pour(messages, souhaite):
    """L'offre gratuite compte demande + réponse maximale dans la limite par minute : on réduit la
    réponse maximale pour que la demande passe."""
    return max(1200, min(souhaite, settings.IA_LIMITE_JETONS_MINUTE - jetons_estimes(messages)))


def trop_long(messages, reponse_min=1800):
    return jetons_estimes(messages) + reponse_min > settings.IA_LIMITE_JETONS_MINUTE


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

def messages_premier_jet(titre_modele, contexte_masque, sections, bilan_en_cours_masque=''):
    """sections : [{'cle', 'titre', 'consigne'}] à rédiger. `bilan_en_cours_masque` : texte déjà
    rédigé du bilan (interprétations), fourni pour la conclusion et les recommandations."""
    liste = '\n'.join(f'- "{s["cle"]}" ({s["titre"]}) : {s["consigne"]}' for s in sections)
    cles = ', '.join(f'"{s["cle"]}": "..."' for s in sections)
    deja = (f"\n\nBILAN DÉJÀ RÉDIGÉ (pour assurer la cohérence ; ne le répète pas)\n"
            f"{bilan_en_cours_masque[:LIMITE_TEXTE_BILAN]}") if bilan_en_cours_masque else ''
    utilisateur = (
        f"Rédige la première version des sections d'un « {titre_modele} ».\n\n"
        f"DONNÉES DU PATIENT\n{contexte_masque}{deja}\n\n"
        f"SECTIONS À RÉDIGER\n{liste}\n\n"
        "Pour les sous-titres, utilise « ## Sous-titre » ; pour le gras, **texte**.\n"
        f"Réponds uniquement avec un objet JSON de la forme {{\"sections\": {{{cles}}}}}, "
        "chaque valeur étant le texte de la section."
    )
    return [{'role': 'system', 'content': REGLES + "\n\n" + STYLE}, {'role': 'user', 'content': utilisateur}]


def messages_relecture(texte_bilan_masque, contexte_masque):
    consigne = (
        REGLES + "\n\nTu relis un bilan avant sa finalisation, comme un collègue attentif. Compare le texte aux "
        "données et aux tableaux de résultats et repère uniquement les problèmes réels : score cité différent du "
        "tableau, niveau qualitatif qui contredit le score ou son seuil, test mal nommé ou mauvaise édition, "
        "contradiction entre deux passages, conclusion non étayée par les résultats, phrase répétée, faute "
        "gênante. Réponds uniquement avec un objet JSON {\"problemes\": [{\"passage\": \"extrait court du texte\", "
        "\"probleme\": \"ce qui ne va pas\", \"suggestion\": \"correction proposée\"}]} (liste vide s'il n'y a "
        "rien à signaler, 15 problèmes au plus)."
    )
    utilisateur = f"DONNÉES DU PATIENT\n{contexte_masque}\n\nBILAN À RELIRE\n{texte_bilan_masque[:LIMITE_TEXTE_RELECTURE]}"
    return [{'role': 'system', 'content': consigne}, {'role': 'user', 'content': utilisateur}]


def messages_chat(texte_bilan_masque, contexte_masque, historique, demande_masquee, selection_masquee):
    """historique : [(role 'psy'|'ia', texte masqué)] des derniers échanges."""
    consigne = (
        REGLES + "\n\n" + STYLE + "\n\nTu aides le psychologue à retravailler son bilan. Réponds uniquement avec un objet JSON "
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
