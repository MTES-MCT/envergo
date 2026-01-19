## Scalingo

- git push
- ajouter les variables d'environnement
  - USE_DOCKER="yes"
  - DJANGO_SETTINGS_MODULE="config.settings.production"

- Pour gdal
https://doc.scalingo.com/platform/app/app-with-gdal

variables d'environnement

```bash
PYTHONPATH=/app/.apt/usr/lib/python3/dist-packages/
LD_LIBRARY_PATH=/app/.apt/usr/lib/x86_64-linux-gnu/blas/:/app/.apt/usr/lib/x86_64-linux-gnu/lapack/
PROJ_LIB=/app/.apt/usr/share/proj
DISABLE_COLLECTSTATIC=1
```

mais ça alourdit l'image dont la limite est 1,5GB

pour que ça fonctionne, j'ai dégagé staticfiles de l'image, mais y a erreur  `The directory '/app/node_modules' in the STATICFILES_DIRS setting does not exist`

Retour à iso prod :
- scalingo-22
- enlever la ligne staticfiles de .slugignore
- ajout builpack geo-heroku-22
- enlever gdal de Aptfile

déploiement success mais toujours erreur `The directory '/app/node_modules' in the STATICFILES_DIRS setting does not exist`

## Domaine

- ajouter une entrée DNS pour votre domaine https://doc.scalingo.com/platform/app/domain#configure-your-domain-name
- ajouter le domaine dans settings > public routing

## Celery

Ajouter un conteneur Celery et cliquer sur scale

## Sentry

c'est bon avec les mêmes variables d'environnement que sur staging et prod

## Configuration post déploiement

Se connecter à l'application via le CLI scalingo

```bash
scalingo --region osc-secnum-fr1 --app haie-formation run bash
```

### Configuration du site

Créer un site avec le nom de domaine utilisé

```bash
./manage.py shell
```

```pycon
>>> from django.contrib.sites.models import Site
>>> Site.objects.get_or_create(domain="formation.haie.beta.gouv.fr", name="Haie formation")
(<Site: formation.haie.beta.gouv.fr>, True)
>>>
```

Mais là j'ai cette erreur

https://sentry.incubateur.net/organizations/betagouv/issues/237123

J'ai mis comme pour les deux autres `COMPRESS_ENABLED=False` et c'est corrigé.

### Création d'un superuser

- S'inscrire via https://formation.haie.beta.gouv.fr/comptes/enregistrement/
- Récupérer le lien de validation d'email depuis la console Scalingo
- Mettre à jour l'utilisateur créé avec is_superuser=True et is_staff=True

```pycon
>>> from envergo.users.models import User
>>> user1 = User.objects.get(email=<votre_email>)
>>> user1.is_superuser = True
>>> user1.is_staff = True
>>> user1.save()
```

### Import des données carto

- les départements
- les haies
- pour le reste on laisse Théo faire

### Démarches numériques

- créer un jeton sur votre compte démarches numériques, de préférence un compte dédié à votre projet
- déterminez l'id de l'instructeur qui sera indiqué sur les communications email
- renseigner les variables d'environnement

```dotenv
DJANGO_DEMARCHES_SIMPLIFIEES_ENABLED=True
DJANGO_DEMARCHE_SIMPLIFIEE_INSTRUCTEUR_ID=
DJANGO_DEMARCHE_SIMPLIFIEE_TOKEN=
```

### Brevo

TODO

### S3

cf doc, liste des variables d'environnement à saisir :

```dotenv
DJANGO_AWS_ACCESS_KEY_ID=
DJANGO_AWS_S3_ENDPOINT_URL=https://envergo-stage.s3.fr-par.scw.cloud
DJANGO_AWS_S3_REGION_NAME=fr-par
DJANGO_AWS_SECRET_ACCESS_KEY=
DJANGO_AWS_STORAGE_BUCKET_NAME=
DJANGO_AWS_UPLOAD_BUCKET_NAME=
```

### Mattermost

accès
créer un webhook
l'ajouter dans les variables d'environnement
