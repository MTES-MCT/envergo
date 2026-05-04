# Services externes

## Démarche numérique (ex Démarches simplifiées)

Un module démarches simplifiées est disponible dans le module petitions.

Il est utilisé principalement dans le guichet unique de la haie, pour faire le lien avec les dossiers déposés dans Démarche Numérique.

Celui-ci permet d'envoyer des requêtes GraphQL pour :

- créer un nouveau dossier et le pré-remplir
- récupérer les dossiers d'une démarche
- récupérer un dossier
- lire et envoyer des messages

Pour fonctionner, un compte dédié doit être créé au niveau de Démarche Numérique.

### Dans le code

Ce client est appelé pour les méthodes

- `envergo.petitions.services.get_demarches_simplifiees_dossier`
- `envergo.petitions.services.get_messages_and_senders_from_ds`
- `envergo.petitions.management.commands.dossier_submission_admin_alert`

Une requête vers DN peut être aussi exécutées hors du client :

- `envergo.petitions.views.pre_fill_demarche_simplifiee`

### Configuration

Dans le compte créé dans Démarche Numérique,

1. Créer un token en lecture / écriture pour permettre au client d'accéder à Démarche Numérique

    Pour des raisons de sécurité, il est préférable de restreindre les réseaux ayant accès à ce token à l'IP
    du serveur qui héberge votre application.

2. Récupérer l'id instructeur du compte (via la première démarche créée)

3. Dans les variables d'environnement, activer Démarche Numérique

    ```dotenv
    DJANGO_DEMARCHES_SIMPLIFIEES_ENABLED=True
    DJANGO_DEMARCHE_SIMPLIFIEE_TOKEN=<votre_token>
    DJANGO_DEMARCHE_SIMPLIFIEE_INSTRUCTEUR_ID=<id_instructeur>
   ```

### Ajouter une nouvelle démarche

Pour ajouter une nouvelle démarche,

- donner les droits d'administration et d'instruction de cette démarche au compte Démarche Numérique sur lequel
  est configuré le token.
- depuis ce compte, modifier le token et ajouter la démarche.
