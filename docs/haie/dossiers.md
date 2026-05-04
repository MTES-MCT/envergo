# Dossiers

## Accès aux Dossiers

Les dossiers sont accessibles :

- aux administrateurs et administratrices (lecture et écriture)
- aux utilisateurs et utilisatrices ayant accès au département du projet (en lecture par défaut, en écriture si la case instructeur est cochée)
- aux utilisateurs et utilisatrices invitées par jeton d'invitation (en lecture seule)

### Avec les droits par département instructeur

Pour ajouter les droits d'un utilisateur à un département, aller dans l'interface d'administration de django, section utilisateurs.

Un utilisateur avec la case instructeur cochée aura les droits d'écriture sur les projets des départements pour lesquels il a les droits.

### Par jeton d'invitation

Depuis la page services consultés, un instructeur ou une instructrice peut créer un jeton d'invitation
pour inviter d'autres services que le service instructeur à consulter un projet.

Il constitue un lien entre le projet et l’invité.

- Un jeton disponible = jeton qui n’a pas encore d'utilisateur invité dessus
- un jeton indisponible/utilisé = jeton qui a été utilisé par un user, donc l'utilisateur invité est bien relié
- Un jeton expiré = jeton encore disponible, mais dont la date d’expiration est dépassée.

L'utilisateur invité a un mois pour utiliser ce jeton, au-delà, il sera expiré.
La date d'expiration ne sert que pour vérifier la validité d'un jeton au moment où l'utilisateur invité accepte ce jeton.
