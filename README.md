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
$ docker-compose -f local.yml exec postgres bash -c 'dropdb envergo -U "$POSTGRES_USER" -f'
$ docker-compose -f local.yml exec postgres bash -c 'createdb envergo -U "$POSTGRES_USER" -O "$POSTGRES_USER"'
$ . .envs/.local/.postgres
$ cat /tmp/envergo.dump | docker exec -i postgres psql -U $POSTGRES_USER -d $POSTGRES_DB
$ docker-compose -f local.yml run --rm django python manage.py migrate
```
