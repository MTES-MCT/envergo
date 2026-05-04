# Contribuer

## Modifications mineures de contenu ou de mise en form

Cas d’usage : certaines modifications peuvent directement être proposées dans le code par le PO. Exemple : wordings, alignements, typos, …

Pour pouvoir réaliser des PR correctement, il faut installer l’environnement de développement sur sa machine :
- [qualité du code](/README.md/#qualit%C3%A9-du-code)
- [configurer son environnement](/README.md/#configurer-son-environnement)

De manière très ponctuelle, le PM est autorisé à pousser des PR avec du code écrit sur Github, mais cela reste une exception.
Si le PO n’a pas la possibilité d’installer l’environnement de développement, les PR sont proscrites.

1. PO crée une nouvelle branche **depuis main** (après git pull)
    ```shell
    git checkout -b nouvelle-branche
    ```

2. **Écriture du code par le PO**
   - modifie le bout de code
   - créer un commit (penser à avoir [Hook pré-commit installé](https://github.com/MTES-MCT/envergo/?tab=readme-ov-file#qualit%C3%A9-du-code) )
   - pousser sa branche sur Github

3. **Création de la PR**
   - crée une PR depuis sa branche sur main
   - modifie le nom de la PR avec le nom du ticket
   - ajoute en commentaire le lien du ticket Trello dans la PR
   - ajoute dans le ticket Trello le lien vers la PR

4. **Process Trello**
   PO passe la carte Trello dans “To Do Dev”
   DEV prend la carte et la met dans “Doing Dev”

5. **Recette**
   DEV review le code, corrige les erreurs de linting et fusionne dans staging
   1. Si PR non validée : itération avec PO. Soit correction triviale, soit discussion sur Github.
   2. Si PR validée : DEV passe la carte dans “Testing”

   PO vérifie que ça colle avec le besoin

   3. Si ça colle pas : itération avec DEV et proposition de modifs dans Github
   4. Si ça colle, PO passe la carte en “Validé”

6. DEV **fusionne** la PR dans main (cf [workflow de collaboration](https://github.com/MTES-MCT/envergo/?tab=readme-ov-file#workflow-de-collaboration))
7. DEV **supprime** la branche si elle n’a pas été supprimée automatiquement.
   (cf [process de déploiement](https://github.com/MTES-MCT/envergo/?tab=readme-ov-file#d%C3%A9ploiement-en-production))
