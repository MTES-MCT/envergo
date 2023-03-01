# Le simulateur EnvErgo (aka la Moulinette)

Le simulateur (affectueusement dénommé en interne « la Moulinette ») est un
composant essentiel d'EnvErgo.

Cette page en dresse une rapide présentation technique.


## Moulinette, gentille moulinette…

La moulinette est un algorithme qui prends en entrée les paramètres d'un projet
d'urbanisation (coordonnées du projet et différentes surfaces) et retourne,
pour diverses réglementations, si le projet peut être soumis ou non.

Exemples de réglementations :

 - Loi sur l'eau
 - Natura 2000
 - Évaluation environnementale

Chaque réglementation est composée de plusieurs critères.

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


## Données complémentaires

En fonction des données du projet, la Moulinette peut avoir besoin de données
complémentaires pour réaliser une évaluation. Ces données seront récupérées
via des formulaires injectés dans la page présentée à l'utilisateur.


## Fonctionnement global

Le calcul de la Moulinette s'effectue en plusieurs étapes :

 1. on vérifie si la Moulinette est disponible pour le département du
 projet ;
 2. on récupère la liste des critères qui doivent être calculés
 individuellement ;
 3. on récupère la liste des zones dans lesquelles se trouve le projet ;
 4. on calcule le résultat de l'évaluation pour chaque réglementation
 en fonction des résultats des critères qui la composent.

Il faut donc noter qu'il y a deux étapes avec une requête géographiques :
la récupération des critères à calculer d'abord, la liste des zones (zone humide,
zone inondable, zone Natura 2000…) ensuite.

Par exemple, on peut configurer la Moulinette de façon à ce que :

 1. le critère `Loi sur l'eau > Zone Inondable` soit évalué sur tout le
 département 44 ;
 2. la carte des zones inondables définisse certains polygones spécifiques dans
 le département.


## Disponibilité de la Moulinette

Comme la Moulinette nécessite des données géographiques pour fonctionner, elle
n'est active que dans certains départements tests.

Pour vérifier si la moulinette est active ou non, on effectue une requête
géographique pour récupérer dans quel département se trouve le projet. On
considère que la Moulinette est active si les données de contact sont disponibles
pour ce département.

https://github.com/MTES-MCT/envergo/blob/2c92d89bc56f2af29f9a6fe3f6e2d10d3e326165/envergo/moulinette/models.py#L228-L235


## Périmètres réglementaires et activation des critères

Dans certains cas, il n'est tout simplement pas pertinent de calculer un critère
donné. On doit donc configurer manuellement dans l'admin dans quelles zones
chaque critère doit être calculé ou non.

Pour ce faire, on utilise les objets `Perimeter` qui permettent d'associer une
carte et une classe Python héritant de la classe `Criterion`.

Important : les critères peuvent définir une distance d'activation. Par exemple,
on calcule les critères Natura 2000 si un projet se trouve à moins de 500m d'une
zone Natura 2000.

https://github.com/MTES-MCT/envergo/blob/2c92d89bc56f2af29f9a6fe3f6e2d10d3e326165/envergo/moulinette/models.py#L196-L212

Si un critère n'est pas activé, il n'est pas calculé et n'entre pas en compte
dans le calcul de l'évaluation pour la réglementation associée.


## Calcul des critères individuels

Le calcul des critères se fait en fonction de plusieurs éléments :

 - les données d'entrées fournies par l'utilisateur ;
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


## Organisation du code

Les données géographique sont définies dans les modèles du module `geodata`.

https://github.com/MTES-MCT/envergo/blob/2c92d89bc56f2af29f9a6fe3f6e2d10d3e326165/envergo/geodata/models.py

Les modèles du module `moulinette` contiennent deux classes importantes :

 - `Perimeter` décrit plus haut ;
 - `Moulinette` le point d'entrée de l'algorithme.

La classe Moulinette récupère les données nécessaires aux différents calculs,
mais délègue ensuite ces calculs à des classes héritant de `MoulinetteRegulation`.

https://github.com/MTES-MCT/envergo/blob/2c92d89bc56f2af29f9a6fe3f6e2d10d3e326165/envergo/moulinette/regulations/__init__.py#L9

Chaque `MoulinetteRegulation` récupère à son tour la liste des résultats pour des
objets héritant de `MoulinetteCriterion`.

https://github.com/MTES-MCT/envergo/blob/2c92d89bc56f2af29f9a6fe3f6e2d10d3e326165/envergo/moulinette/regulations/__init__.py#L146

Chaque réglementation et ses critères sont définies dans un fichier distinct
du répertoire `regulations`.


## Calcul du résultat

Chaque critère effectue un calcul à partir des données fournies par la Moulinette,
et renvoie un code de résultat unique.

Par exemple, le critère `Loi sur l'eau > Zone humide` peut retourner les codes
`action_requise`, `action_requise_proche`, `action_requise_dans_doute`…

Ce code de résultat est ensuite converti en code d'affichage.

Par exemple, les codes `action_requise`, `action_requise_proche`,
`action_requise_dans_doute` correspondent tous à un résultat « Action requise ».

Il est toutefois nécessaire de distinguer ces codes uniques parce que les
templates utilisés pour afficher le résultat du critères seront distincts.


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
