# Services externes

## Démarches simplifiées

TODO: Mettre à jour

### Fonctionnement actuel

Voici les endroits où est exécutée une requête vers Démarches Simplifiées :


- Une méthode `pre_fill_demarche_simplifiee` de la vue `PetitionProjectCreate` pour pré-remplir les données dans DS à la soumission d'un dossier

    L'appel à DS est fait L165

    ```python
    response = requests.post(
        api_url, json=body, headers={"Content-Type": "application/json"}
    )
    ```

- Une méthode `synchronize_with_demarches_simplifiees` de `PetitionProject` pour récupérer les données depuis DS si le dossier existe est n'est pas soumis

    On dirait que contrairement à ce qu'indique son nom, elle ne fait qu'envoyer un message vers mattermost, je sais pas comment elle récupère les données depuis DS

    Celle-ci est appelée depuis 2 endroits
    - la commande `envergo/petitions/management/commands/dossier_submission_admin_alert.py`
    - la méthode `fetch_project_details_from_demarches_simplifiees`

- Une fonction `fetch_project_details_from_demarches_simplifiees` dans `envergo/petitions/services.py` qui permet de récupérer les données depuis DS.

    Celle-ci est uniquement appelée depuis la fonction `compute_instructor_informations`, appelée dans la vue `PetitionProjectInstructorView`

    ```python
    response = requests.post(
        api_url,
        json=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.DEMARCHES_SIMPLIFIEES['GRAPHQL_API_BEARER_TOKEN']}",
        },
    )
    ```

- Une commande pour récupérer les dossier récemment déposés sur DS et alerter les admins `envergo/petitions/management/commands/dossier_submission_admin_alert.py`

    Celle-ci si elle est déclenchée envoie une requête vers `DEMARCHES_SIMPLIFIEES["GRAPHQL_API_URL"]` qui est renseignée dans `base.py`.

    L'appel à DS est fait L94

    ```python
    response = requests.post(
        api_url,
        json=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.DEMARCHES_SIMPLIFIEES['GRAPHQL_API_BEARER_TOKEN']}",
        },
    )
    ```
