# Données BRIEF (non versionnées)

Le repo est public : le texte des items, la répartition item -> échelle, les items de
Négativité, les paires d'Incohérence et les tables d'étalonnage de la BRIEF sont sous droit
d'auteur et ne doivent **jamais** être commités. Ils vivent dans deux fichiers JSON ignorés
par git (`.gitignore` : `tests_psy/data/brief/*.json`, sauf les `*.example.json`) :

| Fichier | Contenu |
|---|---|
| `brief_parent_items.json` | 86 items, échelle de chaque item (vide pour les items non cotés), items de Négativité, paires d'Incohérence |
| `brief_parent_normes.json` | Tables d'étalonnage : une table par sexe / tranche d'âge / échelle ou indice |

Format : voir `brief_parent_items.example.json` et `brief_parent_normes.example.json`.
Dans les normes, `scores` associe chaque score brut à `[score T, percentile]` ; `ic90` est la
valeur de l'intervalle de confiance à 90 % (à ajouter/soustraire au score T). Codes des
échelles : `inhibition`, `flexibilite`, `controle_emotionnel`, `initiation`,
`memoire_travail`, `planification`, `organisation_materiel`, `controle` ; indices : `irc`,
`im`, `ceg`. Sexe : `M` (garçons) / `F` (filles).

## Chargement (local et serveur)

1. Copier les deux fichiers dans ce dossier (sur PythonAnywhere : onglet *Files*, upload).
2. `python manage.py import_brief`

La commande est idempotente (relancer = mise à jour) et refuse une table de normes dont le
score T ou le percentile décroît quand le score brut augmente (erreur de recopie probable).
