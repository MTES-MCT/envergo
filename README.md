# EnvErgo

Améliorer la prise en compte de l'environnement dans les projets d'urbanisme.


## À propos

Cette page concerne le code source du projet EnvErgo. Pour en savoir plus sur le
projet lui-même, se référer au site [EnvErgo.beta.gouv.fr](https://envergo.beta.gouv.fr).

## Solution technique

Les outils principaux suivants sont utilisés :

 - le [framework Django](https://www.djangoproject.com/)
 - le [système de design de l'état français](https://www.systeme-de-design.gouv.fr/)
 - le [projet Cookiecutter-Django pour l'initialisation du dépôt](https://cookiecutter-django.readthedocs.io/en/latest/).


## Démarrage

Cookiecutter-Django est un initialiseur de projet, par les auteurs de [Two Scoops of Django](https://www.feldroy.com/books/two-scoops-of-django-3-x).

Par conséquent, [on se référera à sa doc](https://cookiecutter-django.readthedocs.io/en/latest/index.html) pour en savoir plus sur l'organisation du projet et les différents outils mis en place.


### Développement local

Pour développer en local, deux solutions :

1/ [Créer un environnement local sur sa machine.](https://cookiecutter-django.readthedocs.io/en/latest/developing-locally.html)

2/ [Utiliser l'image Docker](https://cookiecutter-django.readthedocs.io/en/latest/developing-locally-docker.html).

Il est recommandé de se baser sur la version docker.

Pour lancer l'environnement rapidement :

```bash
$ docker-compose build
$ docker-compose up
```

Pour construire la base de données (dans un autre shell) :

```bash
$ docker-compose run --rm django python manage.py migrate
```

### Qualité du code

De nombreux outils sont mis en place pour garantir la qualité et l'homogénéité du code.

 - [pre-commit](https://pre-commit.com/) qui lance plusieurs outils de validation au moment du commit (cf. [sa configuration](https://github.com/MTES-MCT/envergo/blob/main/.pre-commit-config.yaml))
 - [flake8 pour la validation du code python](https://flake8.pycqa.org/en/latest/)
 - [black pour l'auto-formattage du code python](https://github.com/psf/black)
 - [isort pour l'ordonnancement des imports python](https://github.com/PyCQA/isort)
 - [Djhtml pour l'indentation des templates](https://github.com/rtts/djhtml)

Pour activer tout ça :

```bash
pre-commit install
```

### Intégration continue

L'intégration continue est [réalisée par des actions Github](https://github.com/MTES-MCT/envergo/blob/main/.github/workflows/ci.yml).

## Configurer son environnement

Le projet propose un fichier [Editorconfig](https://editorconfig.org/) pour [configurer globalement les éditeurs de code](https://github.com/MTES-MCT/envergo/blob/main/.editorconfig).

### VSCode

Pour VSCode, il est recommandé d'utiliser la configuration suivante.

Installer les extensions :

 - [EditorConfig pour vscode](https://marketplace.visualstudio.com/items?itemName=EditorConfig.EditorConfig)
  - [External formatter](https://marketplace.visualstudio.com/items?itemName=SteefH.external-formatters) (pour djhtml)

Pour activer le formatage à l'enregistrement et correctement affecter les bons "linters" aux bons types de fichiers :

```json
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "files.trimFinalNewlines": true,
  "files.trimTrailingWhitespace": true,
  "files.associations": {
    "**/templates/*.html": "django-html",
    "**/templates/*": "django-txt",
    "**/requirements{/**,*}.{txt,in}": "pip-requirements"
  },
  "emmet.includeLanguages": {
    "django-html": "html"
  },
  "[django-html]": {
    "editor.defaultFormatter": "SteefH.external-formatters"
  },
  "externalFormatters.languages": {
    "django-html": {
      "command": "djhtml",
        "arguments": [
          "-t 2"
        ],
    },
  },
  "beautify.language": {
    "html": [
      "htm",
      "html",
      "django-html"
    ]
  },
  "beautify.config": {
    "brace_style": "collapse,preserve-inline",
    "indent_size": 2,
    "indent_style": "space",
  },
  "[python]": {
    "pythonPath": ".venv/bin/python",
    "linting.enabled": true,
    "linting.flake8Enabled": true,
    "linting.pylintEnabled": false,
    "formatting.provider": "black",
    "formatting.blackArgs": [
      "--line-length=88"
    ],
    "sortImports.args": [
      "--profile",
      "black"
    ],
  }
}
```

Pour être certain de la présence de tous les outils configurés, il est recommandé de créer un environnement virtuel python, puis d'installer toutes les dépendances locales (cf. plus bas).

## Gestion des dépendances

Les [dépendances sont gérées avec pip-tools](https://github.com/jazzband/pip-tools).

Pour installer une nouvelle dépendance, il faut éditer l'un des fichiers *.in présents dans le répertoire `/requirements`.

```bash
cd requirements
echo "<nomdupaquet>"  >> local.in
./compile.sh
pip-sync local.txt
```

Pour mettre à jour l'image Docker, relancer `build` puis `up`.


## Tests

Les tests sont écrits avec [pytest](https://docs.pytest.org/). Tous les helpers de [pytest-django](https://pytest-django.readthedocs.io/en/latest/) sont disponibles.

Pour lancer les tests :

En local :

```bash
pytest
```

Via Docker :

```bash
docker-compose run --rm django pytest
```


## Déploiement

Le déploiement se fait sur la plateforme Scalingo. Pour lancer un déploiement, il suffit de pousser de nouveaux commits sur la branche `prod`.

Le point d'entrée se trouve dans le fichier `Procfile`.

Les scripts utilisés sont dans le répertoire `bin`.


## Faire un dump de la base de prod

[Se référer à cette documentation.](https://doc.scalingo.com/databases/postgresql/dump-restore)

```bash
$ scalingo -a envergo env | grep POSTGRESQL
$ scalingo -a envergo db-tunnel DATABASE_URL
Building tunnel to envergo-1234.postgresql.dbs.scalingo.com:35314
You can access your database on:
127.0.0.1:10000
```

Depuis un autre shell :

```bash
pg_dump --dbname postgresql://<user>:<pass>@localhost:10000/<db> > /tmp/envergo.dump
```


## Comment charger une BD de dev depuis un dump

```bash
$ docker-compose exec postgres bash -c 'dropdb envergo -U "$POSTGRES_USER" -f'
$ docker-compose exec postgres bash -c 'createdb envergo -U "$POSTGRES_USER" -O "$POSTGRES_USER"'
$ . .envs/.local/.postgres
$ cat /tmp/envergo.dump | docker exec -i postgres psql -U $POSTGRES_USER -d $POSTGRES_DB
$ docker-compose run --rm django python manage.py migrate
```
