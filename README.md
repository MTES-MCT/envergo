# EnvErgo

Améliorer la prise en compte de l'environnement dans les projets d'urbanisme.


## À propos

Cette page concerne le code source du projet EnvErgo. Pour en savoir plus sur le
projet lui-même, se référer au site [EnvErgo.beta.gouv.fr](https://envergo.beta.gouv.fr).


## Démarrage

Le projet a été [initialisé grâce à Cookiecutter-Django](https://cookiecutter-django.readthedocs.io/en/latest/).


## Développement local

Pour développer en local, deux solutions :

1/ [Créer un environnement local sur sa machine.](https://cookiecutter-django.readthedocs.io/en/latest/developing-locally.html)

2/ [Utiliser l'image Docker](https://cookiecutter-django.readthedocs.io/en/latest/developing-locally-docker.html).


## Tests

En local :

```bash
pytest
```

Via Docker :

```bash
docker-compose -f local.yml run --rm django pytest
```


## Déploiement

Le déploiement se fait sur la plateforme Scalingo.

Le point d'entrée se trouve dans le fichier `Procfile`.

Les scripts utilisés sont dans le répertoire `bin`.
