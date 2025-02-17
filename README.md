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


#### Avec Docker

> NB : pour les commandes `docker compose`, cette documentation utilise la syntaxe de la version 2 en remplacant le tiret (`-`) par un espace et utlisant donc `docker compose` à la place de `docker-compose`.
> Si vous avez une version plus ancienne, vous pouvez utiliser la syntaxe `docker-compose`.
> [Plus d'infos…](https://docs.docker.com/compose/releases/migrate/#what-are-the-differences-between-compose-v1-and-compose-v2)

Pour lancer l'environnement rapidement :

```bash
$ git clone … && cd envergo
$ touch .env
```

Remplir le fichier `.env` avec les variables d'environnement pour travailler en local

```
DJANGO_SETTINGS_MODULE=config.settings.local
ENV_NAME=development
```

Créez les conteneurs et démarrez-les

```bash
$ docker compose build
$ docker compose up
```

Pour construire la base de données (dans un autre shell) :

```bash
$ docker compose run --rm django python manage.py migrate
```

Pour avoir accès aux fichiers `static` depuis le serveur de debug :

```bash
$ npm install
$ npm  run build
$ docker compose run --rm django python manage.py collectstatic

```

Ajoutez dans `/etc/hosts` les domaines utilisés pour EnvErgo (http://envergo.local:8000/) et le Guichet Unique de la Haie (http://haie.local:8000/).

```
<url du conteneur envergo_django> envergo.local haie.local
```


#### En local

```bash
$ git clone … && cd envergo
$ touch .env
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install pip-tools
$ pip-sync requirements/local.txt
```

Remplir le fichier `.env` avec des valeurs appropriées.

Il est nécessaire d'avoir au préalable configuré un utilisateur dans postgres avec
les droits de création de base et d'extension.


#### Résoudre l'erreur "raster does not exist"

Dans les versions les plus récentes de postgis, il est nécessaire [d'installer l'extension "raster"](https://docs.djangoproject.com/fr/5.0/ref/contrib/gis/install/postgis/#post-installation).
Si, lors du `docker compose up` ci-dessus vous avez ce type d'erreur :

    envergo_postgres  | 2024-05-13 14:35:21.651 UTC [35] ERROR:  type "raster" does not exist at character 118

Il vous faudra créer cette extension (dans un autre terminal, avec le `docker compose up` qui tourne en parallèle) :

```bash
$ docker compose run --rm postgres create_raster
```

Puis interrompre et relancer le `docker compose up`. Les migrations Django devraient alors s'exécuter sans erreur.


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
  - [Flake8 pour le linting](https://marketplace.visualstudio.com/items?itemName=ms-python.flake8)
  - [Black pour le formattage](https://marketplace.visualstudio.com/items?itemName=ms-python.black-formatter)
  - [Isort pour l'organisation des imports](https://marketplace.visualstudio.com/items?itemName=ms-python.isort)
  - [Prettier pour le formattage du code css / sass](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode)


Voici un fichier `settings.json` à enregistres dans `.vscode/settings.json` pour configurer
correctement VSCode :

```json
{
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    },
    "editor.rulers": [
      88
    ],
  },
  "[html]": {
    "editor.defaultFormatter": "vscode.html-language-features"
  },
  "[django-html]": {
    "editor.rulers": [
      120,
    ],
    "editor.defaultFormatter": "monosans.djlint",
    "editor.wordWrap": "wordWrapColumn"
  },
  "[css][scss][less]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "isort.args": [
    "--profile",
    "black"
  ],
  "black-formatter.args": [
    "--line-length=88"
  ],
  "files.associations": {
    "**/templates/*.html": "django-html",
    "**/templates/*": "django-txt",
    "**/requirements{/**,*}.{txt,in}": "pip-requirements"
  },
  "emmet.includeLanguages": {
    "django-html": "html"
  },
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


## Tests unitaires

Les tests sont écrits avec [pytest](https://docs.pytest.org/). Tous les helpers de [pytest-django](https://pytest-django.readthedocs.io/en/latest/) sont disponibles.

Pour lancer les tests :

En local :

```bash
pytest
```

Via Docker :

```bash
docker compose run --rm django pytest
```


## Tests End-to-End

Les tests end-to-end sont écrits avec [Playwright](https://playwright.dev/).
Les tests E2E permet de valider que les chemins utilisateurs critiques (faire une simulation, demander un avis, répondre à une demande d'avis, etc) fonctionnent correctement.
Cela permet en outre de vérifier le bon fonctionnement des composants JavaScript de plus en plus présent sur les pages et pour le moment non couvert par d'autre tests.

Ils se basent sur une base de données de tests dédiée contenant une jeu de données minimum présent dans ce [fichier](e2e/fixtures/db_seed.json)  et que l’on peut remplir pour les besoins de chaque test.

Ils tournent dans la CI de Github.


### Lancer les tests E2E en local

#### Prérequis
Pour lancer les tests E2E en local, il faut avant tout créer une base de données dédiée similaire à celle qui sera utilisée par la CI.
Pour cela, il faut lancer les commandes suivantes :

```bash
$ . envs/postgres
$ docker compose exec postgres bash -c 'dropdb --if-exists envergo-test -U "$POSTGRES_USER" -f'
$ docker compose exec postgres bash -c 'createdb envergo-test -U "$POSTGRES_USER" -O "$POSTGRES_USER"'
$ docker compose run -e POSTGRES_DB=envergo-test --rm django python manage.py migrate
$ docker compose run -e POSTGRES_DB=envergo-test --rm django python manage.py loaddata e2e/fixtures/db_seed.json
```

Vous devez ensuite installer Playwright avec les commandes suivantes:
```bash
$ npm install @playwright/test
$ npx playwright install
```

#### Lancer les tests

Vous devez tout d'abord lancer l'application en pointant vers la base de test et avec le bon fichier de settings :

```bash
$ POSTGRES_DB=envergo-test docker compose -f docker-compose.yml -f docker-compose.e2e.yml  up -d
```

Enfin vous pouvez lancer les tests avec l'une des commandes suivantes :

```bash
$ npx playwright test --ui # pour lancer les tests dans un navigateur
$ npx playwright test # pour lancer les tests dans un shell
```

## Recette et déploiement

### Environnement de recette

Deux possibilités existent pour la mise en disponibilité d'un environnement de recette :

 - 1/ création d'une « review app » manuellement via scalingo ;
 - 2/ utilisation de l'environnement de recette permanent `envergo.incubateur.net`.

Les « review app » peuvent être créées manuellement à l'envie depuis l'interface
de Scalingo.  Une review app est automatiquement supprimée lorsque la Pull Request
correspondante est fusionnée.

L'environnement de staging est permanent, avec un déploiement automatique de la
branche `staging`.


### Workflow de collaboration

Le workflow de collaboration git en vigueur est le suivant :

 - la branche `main` ne contient que du code absolument prêt à passer en prod (revue de code ok, review PO ok)
 - sauf commit absolument trivial, tous les devs sont effectués sur des branches dédiées
 avant de pouvoir être fusionnées
 - sauf en cas de branche triviale et au jugé, les branches doivent passer par une revue de code avant d'être fusionnées
 - la branche `staging` contient du code fonctionnel, mais en cours de validation ; cette branche est déployée automatiquement sur l'environnement de staging permanent
 - Les Pull Requests doivent systématiquement être fusionnées dans `main`, et uniquement après validation complete
 - si la création d'une review app dédiée est jugée trop fastidieuse, une branche de dev peut être fusionnée dans `staging` pour en faciliter la validation.
 - il est interdit de pusher du code sur `prod` qui ne soit pas déjà dans `main`
 - pour effectuer une mise en prod, on fusionne `main` dans `prod` (fast forward)
 - de façon exceptionnelle, pour déployer un correctif urgemment en prod sans
 devoir déployer toute la branche `main`, on peut :
   - publier et valider le correctif sur `main` ;
   - effectuer un `cherry-pick` du commit pour les intégrer de manière unitaire
   à la branche `prod`.


### Déploiement en production

Le déploiement se fait sur la plateforme Scalingo. Pour lancer un déploiement, il suffit de pousser de nouveaux commits sur la branche `prod`.

Le déploiement se lancera automatiquement si les actions github sont au vert.

Le point d'entrée se trouve dans le fichier `Procfile`.

Les scripts utilisés sont dans le répertoire `bin`.


### Installation des dépendances Géo sur Scalingo

EnvErgo utilise GeoDjango, une version de Django s'appuyant sur des dépendances
externes pour les fonctions géographiques (gdal, geos, proj…).

Pour installer ces dépendances, [Scalingo proposait un buildpack
dédié](https://github.com/Scalingo/geo-buildpack), qui est tombé en désuétude.

À titre de solution temporaire, les actions suivantes ont été réalisées :


1/ Forker le `heroku-geo-buildpack` et [modifier cette ligne](https://github.com/thibault/heroku-geo-buildpack/blob/master/bin/compile#L9) pour obtenir la bonne url.

2/ Remplacer le buildpack scalingo par l'url du buildpack clôné : https://github.com/MTES-MCT/envergo/blob/fix_geo_buildpack/.buildpacks#L3

3/ Configurer la variable d'environnement `DISABLE_COLLECTSTATIC`. (On appelle déjà manuellement collectstatic dans notre build https://github.com/MTES-MCT/envergo/blob/main/bin/build_assets.sh#L35).

4/ Lancer le déploiement. L'app build sans soucis. Je n'ai pas encore noté de bugs sur les fonctions geo.


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

Alternative : récupérer le backup nocture depuis Scalingo.

## Comment charger une BD de dev depuis un dump

```bash
$ . envs/postgres
$ docker compose exec postgres bash -c 'dropdb envergo -U "$POSTGRES_USER" -f'
$ docker compose exec postgres bash -c 'createdb envergo -U "$POSTGRES_USER" -O "$POSTGRES_USER"'
$ cat /tmp/envergo.dump | docker exec -i envergo_postgres psql -U $POSTGRES_USER -d $POSTGRES_DB
$ docker compose run --rm django python manage.py migrate
```


## Stockage de fichiers

Les documents sont stockés sur un répertoire distant compatible avec le protocole S3 sur [Scaleway](https://console.scaleway.com/object-storage/buckets) ce processus est géré via la librairie python boto en combinaison avec le package default_storage de Django


### Backup des buckets S3

Chaque semaine, on souhaite faire un backup du contenu des buckets s3 de production.
Pour executer ce back up on utilise [github action](.github/workflows/s3_backup.yml)

Pour s'exécuter, github action a besoin des identifiants s3 à configurer dans [Settings](https://github.com/MTES-MCT/envergo/settings) > Secrets and variables > [Actions](https://github.com/MTES-MCT/envergo/settings/secrets/actions).

Ajouter les `Repository secrets` :
* S3_ACCESS_KEY
* S3_SECRET_KEY

## Glossaire

Voici un petit index des acronymes et termes métiers fréquemment rencontrés.

 * LSE : Loi sur l'eau
 * 3.2.2.1, 2.1.5.0… : références à certaines rubriques de la Loi sur l'eau, décrivant les critères qui font que certains projets sont soumis ou non à déclaration Loi sur l'eau.
 * IOTA : Installations, ouvrages, travaux et aménagements, i.e un « projet ».
 * DREAL : Direction régionale de l'Environnement, de l'aménagement et du logement.
 * CEREMA : Centre d'études et d'expertise sur les risques, l'environnement, la mobilité et l'aménagement
 * DGALN : Direction générale de l'Aménagement, du Logement et de la Nature
