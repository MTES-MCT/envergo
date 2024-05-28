# Le simulateur EnvErgo (aka la Moulinette)

Le simulateur (affectueusement dénommé en interne « la Moulinette ») est un
composant essentiel d'EnvErgo.

Cette page en dresse une rapide présentation technique. Elle est a destination des
personnes qui veulent acquérir une compréhension technique de son fonctionnement.


## Description sommaire

> Moulinette, gentille moulinette…

La moulinette est un algorithme qui prend en entrée les paramètres d'un projet
d'urbanisation (coordonnées du projet et différentes surfaces) et retourne,
pour diverses réglementations, si le projet peut être soumis ou non.

Exemples de réglementations :

 - Loi sur l'eau
 - Natura 2000
 - Évaluation environnementale

Chaque réglementation est évaluée sur plusieurs critères.

Exemples de critères pour la réglementation « Loi sur l'eau » :

 - Zone humide
 - Zone inondable
 - Ruissellement

En fonction des données du projet, la Moulinette peut assigner différentes
valeurs au test sur un critère. Le résultat d'une réglementation dépend des
différentes valeurs pour tous les critères de cette évaluation.

Par exemple, si un des critères de la réglementation « Loi sur l'eau » est
« soumis », alors le résultat de l'évaluation pour cette réglementation sera
« soumis ».

Dans certains cas, le résultat d'une réglementation peut dépendre d'une autre
réglementation.

Par exemple, la réglementation « Natura 2000 » dispose d'un critère « IOTA »
qui sera « soumis » si la réglementation « Loi sur l'eau » est « soumis ».

## Composants individuels

Pour fonctionner, la Moulinette s'appuie sur un certains nombre de composants.


### Réglementation

Une Réglementation est le plus haut niveau d'information que l'on affiche aux
utilisateurs de la moulinette.

Chaque réglementation configurée est évaluée et reçoit un code de résultat unique,
ainsi qu'un texte pédagogique associé.

Ainsi, après une simulation, un porteur de projet pourra recevoir une information :

 - Loi sur l'eau -> Action requise
 - liste des actions requises dans le cadre de l'instruction du dossier Loi sur l'eau.


### Critère

L'évaluation au titre d'une réglementation nécessite d'évaluer les différents
critères qui la composent.

Ainsi, l'évaluation au titre de la réglementation environnementale nécessitent
d'évaluer les critères :

 - Emprise
 - Surface plancher
 - Terrain d'assiette
 - Camping
 - Aire de stationnement
 - etc.

Un critère est la combinaison d'une carte d'activation (la zone géographique où
le critère doit être évalué) et un évaluateur (cf. ci-dessous).


### Évaluateur

Un évaluateur est le code effectif qui réalise le calcul du résultat d'un
critère.

C'est une classe Python qui effectue un calcul sur les données fournies par
le formulaire d'évaluation.

Exemple de calcul :

`Si le projet est dans une zone humide référencée ET la surface finale du projet
est supérieure à 1000 m² ALORS le résultat du critère est SOUMIS.`


### Périmètre

Un périmètre est une entité administrative distincte délimitée par une zone
géographique distincte.

Exemple de périmètre : SAGE Bas Léon

Un périmètre concerne une réglementation, est associé à une carte et permet
d'indiquer des informations de contact distinctes.

Certaines réglementations fonctionnent par périmètres, d'autres non.

Si la réglementation fonctionne par périmètre (e.g), alors elle n'est évaluée
que dans le cas ou le projet se trouve au sein d'un périmètre donné.


### Config

Certains paramètres de configuration de l'évaluateur sont configurés à l'échelle
du département. Pour ces éléments, on utilise les objets « Moulinette Config ».


### Carte

Dans l'admin, une carte est une zone géographique associée à un nom.

Une carte peut être uniquement une zone géographique (par exemple, pour configurer
un périmètre) ou une zone typée (e.g une zone humide, une zh potentielle, etc.)


### Zone

Une carte est simplement une collection de polygones appelés « zones ».


## Fonctionnement global

Le calcul de la Moulinette s'effectue en plusieurs étapes :

 1. on vérifie si la Moulinette est disponible pour le département du
 projet ;
 2. on récupère la liste des périmètres contenant le projet ;
 2. on récupère la liste des critères pour lesquels le projet est dans la carte d'activation ;
 3. on récupère la liste des zones (zh, zi, etc.) dans lesquelles se trouve le projet ;
 4. on calcule le résultat de l'évaluation pour chaque réglementation
 en fonction des résultats des critères qui la composent.

Il faut donc noter qu'il y a deux étapes d'un point de vue géographique :
 - d'abord on vérifie quels critères on va devoir évaluer
 (e.g faut-il calculer le critère LSE > ZH à cet emplacement ?)
  - ensuite on vérifie l'existence de zones humides, zones inondables, etc. pour
  réaliser l'évaluation).


## Données complémentaires

En fonction des données du projet, la Moulinette peut avoir besoin de données
complémentaires pour réaliser une évaluation. Ces données seront récupérées
via des formulaires injectés dans la page présentée à l'utilisateur.


## Données optionnelles

Dans le simulateur, les admins ont accès à des critères supplémentaires qui
resteront invisibles et ne seront pas pris en compte par les utilisateurs.

En revanche, ces critères apparaissent dans les avis réglementaires.


## Disponibilité de la Moulinette

Comme la Moulinette nécessite des données géographiques pour fonctionner, elle
n'est active que dans certains départements tests.

Pour vérifier si la moulinette est active ou non, on effectue une requête
géographique pour récupérer dans quel département se trouve le projet. On
considère que la Moulinette est active si les données de contact sont disponibles
pour ce département.

https://github.com/MTES-MCT/envergo/blob/2c92d89bc56f2af29f9a6fe3f6e2d10d3e326165/envergo/moulinette/models.py#L228-L235


## Fonctionnement des évaluateurs

Le calcul des critères se fait en fonction de plusieurs éléments :

 - les données par l'utilisateur ;
 - les données géographiques trouvées en base ;
 - éventuellement, le résultat du calcul d'autres critères.

Pour réaliser le calcul des différents critères, on vérifie si le projet se
trouve dans une zone humide, une zone inondable, une zone Natura 2000, etc.

Ces données sont contenues dans la classe `Map`.

https://github.com/MTES-MCT/envergo/blob/main/envergo/geodata/models.py#L154

Cette classe permet aux admins d'importer des fichiers shapefile. Une carte
est associée à un type de zone (humide, inondable…) et éventuellement un niveau
de certitude (zone humide certaine ou zone humide probable…)

Les véritables données géographique sont stockés dans les objets `Zone`. Une
zone est liée à une carte et contient un polygone.

https://github.com/MTES-MCT/envergo/blob/2c92d89bc56f2af29f9a6fe3f6e2d10d3e326165/envergo/geodata/models.py#L202

Comme il serait coûteux d'effectuer une requête géographique en base pour
chaque critère, on récupère en une seule requête toutes les zones à proximité des
coordonnées du projet.

https://github.com/MTES-MCT/envergo/blob/2c92d89bc56f2af29f9a6fe3f6e2d10d3e326165/envergo/moulinette/models.py#L153-L162

Note : on récupère aussi les zones proches mais ne contenant pas directement
les coordonnées du projet parce que ces zones seront potentiellement affichées
sur les cartes Leaflet dans le template.


## Calcul du résultat

Les évaluateurs fonctionnent de la façon suivante :

 - récupération des données nécessaires au calcul ;
 - génération d'un code de résultat unique, e.g `action_requise_dans_doute` ;
 - conversion en code d'affichage de résultat, e.g `action_requise` ;


## Affichage des résultats

Chaque combinaison de critère / code de résultat unique doit être associée à un
template qui sera utilisé lors de l'affichage.

Exemple : https://github.com/MTES-MCT/envergo/blob/2c92d89bc56f2af29f9a6fe3f6e2d10d3e326165/envergo/templates/moulinette/loi_sur_leau/zone_humide_action_requise_proche.html


## Cartes

Chaque critère peut définir une méthode `_get_map` qui retourne un objet `Map`.

https://github.com/MTES-MCT/envergo/blob/2c92d89bc56f2af29f9a6fe3f6e2d10d3e326165/envergo/moulinette/regulations/__init__.py#L98

Note : il s'agit d'une classe différente des cartes utilisées pour stocker les
données géographique.

`Map` est une classe qui contient quelques données qui seront converties en
json, injectées dans le template, et passées à un script de configuration Leaflet.
