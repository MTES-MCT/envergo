# Services externes

## Démarches simplifiées

Un module démarches simplifiées est disponible dans le module petitions.

Il est utilisé principalement dans le guichet unique de la haie, pour faire le lien avec les dossiers déposés dans Démarches Simplifiées.

Celui-ci permet d'envoyer des requêtes GraphQL pour :

- créer un nouveau dossier et le pré-remplir
- récupérer les dossiers d'une démarche
- récupérer un dossier
- lire et envoyer des messages

### Dans le code

Ce client est appelé pour les méthodes

- `envergo.petitions.services.get_demarches_simplifiees_dossier`
- `envergo.petitions.services.get_messages_and_senders_from_ds`
- `envergo.petitions.management.commands.dossier_submission_admin_alert`

Une requête vers DS peut être aussi exécutées hors du client :

- `envergo.petitions.views.pre_fill_demarche_simplifiee`
