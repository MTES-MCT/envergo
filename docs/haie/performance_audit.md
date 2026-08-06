# Haie — Audit de performance

- **Date** : 6 août 2026
- **Branche** : `perf_audit`

## 1. Infrastructure

- Gunicorn × 9 workers, timeout 120 s, max-requests 300
- Scalingo M : 1 conteneur web + 1 worker Celery
- PostGIS, CONN_MAX_AGE=60, ATOMIC_REQUESTS=True
- Redis (rate limiting, sessions)
- Templates cachés en prod (cached.Loader)
- Aucun cache applicatif sur les résultats moulinette

## 2. Cas d'usage

Six cas d'usage couvrent l'essentiel du trafic.

**UC1 — Simuler l'impact réglementaire d'un projet de haie.**

Un pétitionnaire (anonyme) sélectionne son département, répond
à des questions de triage, trace sur une carte les haies à
détruire puis à replanter, et obtient un résultat réglementaire
détaillé.

**UC2 — Déposer un dossier.**

À l'issue de la simulation, le pétitionnaire soumet son projet.
L'application crée le dossier en base et le pré-remplit sur
Démarches Simplifiées via l'API GraphQL.

**UC3 — Consulter un dossier déposé.**

Le pétitionnaire (ou toute personne disposant de la référence)
consulte le résultat réglementaire associé à un dossier déposé.
Public, sans authentification.

**UC4 — Parcourir la liste des dossiers.**

Un instructeur authentifié accède à son tableau de bord : la
liste paginée des dossiers de ses départements, avec indicateurs
de suivi, messagerie non lue et filtres.

**UC5 — Instruire un dossier.**

L'instructeur consulte la synthèse réglementaire d'un dossier,
examine chaque réglementation en détail, consulte le dossier DS
complet, rédige des notes et gère les invitations de services
consultés.

**UC6 — Piloter la procédure.**

L'instructeur fait avancer le dossier dans son cycle de vie :
changement d'état, demande de pièces complémentaires, reprise
d'instruction, échange de messages avec le pétitionnaire,
clôture. Chaque action synchronise l'état vers DS.

## 3. Méthodologie de mesure

Mesures réalisées avec le client de test Django + capture des
requêtes SQL, en local sur un dump de la base de production
(15,2 M zones, 20,6 M lignes de haies, 561 dossiers).

Limites connues :

- DEBUG activé, machine de dev : les temps sont indicatifs,
  les nombres de requêtes sont fiables
- API Démarches Simplifiées désactivée localement : les vues qui
  en dépendent ne mesurent que le travail local
- paramètres réalistes issus du dossier PK8A7J (dept 14) :
  `?department=14&element=haie&travaux=destruction&contexte=non
&motif=amelioration_culture&reimplantation=replantation
&localisation_pac=non&date=2026-08-05&haies={uuid}`
- vues instructeur mesurées avec un compte instructeur (dept 14)

Script de mesure : `profile_endpoints.py`.

## 4. Parcours et mesures

### UC1 — Simuler l'impact réglementaire

Parcours public, sans authentification.

- Le pétitionnaire choisit son département sur la page d'accueil
- Il répond au triage (type d'élément, type de travaux, contexte)
- Il arrive sur le formulaire principal ; depuis ce formulaire,
  il ouvre l'interface cartographique et trace les haies à
  détruire (sauvegarde AJAX, retour au formulaire)
- Il soumet le formulaire et obtient le résultat destruction
- Depuis le résultat, il ouvre l'interface cartographique en mode
  plantation ; pendant le tracé, le frontend interroge le serveur
  pour le feedback temps réel (conditions de plantation)
- Il obtient le résultat plantation

| Verbe | URL                                | Requêtes SQL        | Temps SQL  |
| ----- | ---------------------------------- | ------------------- | ---------- |
| GET   | `/`                                | 5                   | 5 ms       |
| GET   | `/simulateur/triage/`              | 9                   | 4 ms       |
| GET   | `/simulateur/formulaire/`          | 15                  | 73 ms      |
| GET   | `/haies/14/removal/`               | 4                   | 3 ms       |
| POST  | `/haies/14/removal/`               | non mesuré (INSERT) | —          |
| GET   | `/simulateur/resultat/`            | 18                  | 120 ms     |
| GET   | `/haies/14/plantation/{uuid}/`     | 16                  | 82 ms      |
| POST  | `/haies/conditions/`               | 16                  | **443 ms** |
| POST  | `/haies/14/plantation/`            | non mesuré (INSERT) | —          |
| GET   | `/simulateur/resultat-plantation/` | 17                  | 128 ms     |

Constats mesurés :

- Le formulaire, les deux résultats, la saisie plantation et les
  conditions exécutent chacun une évaluation moulinette complète
  (voir section 5).
- `POST /haies/conditions/` est le plus coûteux (443 ms SQL) et
  il est appelé à chaque modification du tracé par le frontend.
  Chaque appel crée un `HedgeData` neuf : le cache de densité ne
  s'applique jamais (nouvelle clé), le calcul complet tourne à
  chaque fois, et une ligne est **insérée en base à chaque appel**
  (endpoint anonyme, volume non borné).
- Un parcours complet = au moins 5 évaluations moulinette,
  plus N appels conditions.

### UC2 — Déposer un dossier

Déclenché par le pétitionnaire après la simulation.

- Le frontend envoie l'URL moulinette au serveur
- Le serveur crée le dossier, pré-remplit DS via API GraphQL
- Un snapshot du résultat est créé en arrière-plan

| Verbe | URL        | Requêtes SQL | Temps SQL |
| ----- | ---------- | ------------ | --------- |
| POST  | `/projet/` | non mesuré   | —         |

Le code exécute 2 évaluations moulinette (pré-remplissage DS

- ResultSnapshot en `on_commit`) plus l'appel à l'API DS.

### UC3 — Consulter un dossier déposé

Accessible par quiconque connaît la référence du dossier.

| Verbe | URL                           | Requêtes SQL | Temps SQL |
| ----- | ----------------------------- | ------------ | --------- |
| GET   | `/projet/{ref}/consultation/` | 18           | 120 ms    |

Évaluation moulinette complète reconstruite depuis l'URL stockée.

Constat hors performance : un dossier dont les réglementations
ont évolué depuis sa création lève `NotImplementedError` et
devient inconsultable.

### UC4 — Parcourir la liste des dossiers

Instructeur authentifié.

- L'instructeur se connecte (redirect vers la liste)
- Il parcourt la liste paginée de ses dossiers (30/page)
- Il peut filtrer, suivre/arrêter de suivre un dossier

| Verbe | URL                    | Requêtes SQL | Temps SQL |
| ----- | ---------------------- | ------------ | --------- |
| POST  | `/comptes/connexion/`  | non mesuré   | —         |
| GET   | `/projet/liste`        | **50**       | 92 ms     |
| POST  | `/projet/{ref}/suivi/` | non mesuré   | —         |

Constat : **N+1 sur les permissions**. Le template appelle le
filtre `has_edit_permission` pour chaque dossier affiché, et
chaque appel exécute `user.departments.filter(id=…).exists()` —
42 requêtes pour une page de 30 dossiers.

### UC5 — Instruire un dossier

Instructeur authentifié. Chaque onglet est une requête séparée.

| Verbe | URL                                | Requêtes SQL        | Temps SQL |
| ----- | ---------------------------------- | ------------------- | --------- |
| GET   | `/projet/{ref}/instruction/`       | 28                  | 82 ms     |
| GET   | `/projet/{ref}/instruction/{reg}/` | 27                  | 118 ms    |
| GET   | `…/instruction/dossier-complet/`   | non mesuré (API DS) | —         |
| GET   | `…/instruction/messagerie/`        | non mesuré (API DS) | —         |
| GET   | `…/instruction/notes/`             | 16                  | 2 ms      |
| GET   | `…/instruction/consultations/`     | non mesuré          | —         |
| GET   | `/projet/{ref}/haies.gpkg`         | 4                   | 1 ms      |

Constats :

- La synthèse et chaque vue réglementation exécutent l'évaluation
  moulinette complète en plus du socle instructeur.
- La synthèse répète des lookups department/confighaie (8 SELECT
  `geodata_department` dans la même requête HTTP).
- Les vues dossier-complet et messagerie font un appel bloquant
  à l'API DS (`force_update=True`).

### UC6 — Piloter la procédure

Instructeur authentifié. Actions qui font avancer le dossier.

| Verbe | URL                             | Requêtes SQL        | Temps SQL |
| ----- | ------------------------------- | ------------------- | --------- |
| GET   | `…/instruction/procedure/`      | 21                  | 3 ms      |
| POST  | `…/instruction/procedure/`      | non mesuré (API DS) | —         |
| POST  | `…/instruction/messagerie/`     | non mesuré (API DS) | —         |
| GET   | `…/instruction/alternatives/`   | 18                  | 3 ms      |
| POST  | `…/alternatives/{id}/activate/` | non mesuré          | —         |

Les POST synchronisent l'état vers DS (GraphQL) ; le changement
d'état crée un StatusLog et peut déclencher un message de clôture
via Celery.

## 5. Décomposition d'une évaluation moulinette

Mesuré sur `GET /simulateur/resultat/` (18 requêtes, 120 ms SQL) :

| Requête                                 | Temps  | Note                |
| --------------------------------------- | ------ | ------------------- |
| SELECT hedges_species                   | 41 ms  | espèces protégées   |
| SELECT geodata_zone                     | 36 ms  | zonages spatiaux    |
| SELECT moulinette_criterion             | 24 ms  | filtrage activation |
| SELECT geodata_department               | 5 ms   | lookups répétés     |
| Autres (regulation, perimeter, config…) | ~10 ms |                     |
| INSERT analytics_event                  | 3 ms   | écriture par visite |

Sur `POST /haies/conditions/` s'ajoutent :

| Requête                          | Temps  | Note                     |
| -------------------------------- | ------ | ------------------------ |
| query_hedge_length (WITH inputs) | 253 ms | longueur haies (densité) |
| trim_land (WITH geodata_zone)    | 117 ms | découpe terres émergées  |
| INSERT hedges_hedgedata          | 1 ms   | **une ligne par appel**  |

Le calcul de densité (370 ms cumulés sur `geodata_line` 20,6 M
lignes et `geodata_zone`) domine le coût du endpoint conditions.
Sur les pages résultat, il est absorbé par le cache `_density`
du HedgeData stocké ; sur conditions, jamais (HedgeData neuf à
chaque appel).

## 6. Coût transversal par requête

Vérifié dans les logs de mesure :

- BEGIN/COMMIT sur chaque requête (ATOMIC_REQUESTS)
- SELECT django_session + users_user si authentifié
- SELECT confs_topbar sur chaque page rendue (template tag)
- INSERT analytics_event sur les pages du simulateur
- Rate limiting : 1-3 appels Redis (non visibles en SQL)

## 7. Pistes identifiées (à mesurer/valider)

1. Calcul de densité sur `/haies/conditions/` : 370 ms par appel,
   jamais caché (HedgeData neuf à chaque appel), déclenché à
   chaque modification du tracé
2. N+1 permissions sur `/projet/liste` : filtre template
   `has_edit_permission` → 1 requête `departments…exists()` par
   dossier affiché (42 requêtes/page pour un instructeur)
3. INSERT `hedges_hedgedata` à chaque appel conditions (volume
   non borné, endpoint anonyme)
4. Lookups department/confighaie répétés dans une même requête
   (8× sur la synthèse instructeur)
5. Pas de cache applicatif sur les évaluations moulinette alors
   qu'un parcours en exécute ≥ 5 fois avec les mêmes paramètres

## 8. Tests de charge

_À venir._

## 9. Optimisations appliquées

_À venir._

## 10. Estimation de capacité et plan d'action

_À venir._
