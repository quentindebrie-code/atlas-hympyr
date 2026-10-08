# Note à la direction : Atlas territorial Hympyr

**Objet** : décision de lancer un pilote de 2 semaines. **Auteur** : Quentin Debrie, Transformation
digitale. **Date** : octobre 2026.

## L'enjeu

Hympyr livre 7 départements, du plat toulousain aux vallées pyrénéennes. En l'absence d'outil dédié, la question
« où concentrer l'effort commercial et logistique ? » repose sur l'expérience des équipes (à
confirmer avec elles). Cette expérience est précieuse, mais elle se transmet et se chiffre mal.

## La proposition

Un **atlas cartographique interne** : une carte où l'on survole une commune pour voir, par produit
(fioul, granulés, GNR, gasoil routier, AdBlue), la demande estimée, et la difficulté d'y livrer
(relief, route sinueuse, temps de trajet, heures d'affluence). Construit uniquement sur des données
officielles ouvertes, **sans toucher aux données clients**.

## Quelles décisions il sert

| Décision | Qui | Ce que l'atlas apporte |
|---|---|---|
| Où prospecter, où appeler en priorité | Commerciales, manager | Liste classée de communes, exportable |
| Où cibler une campagne publicitaire (ex. granulés) | Marketing, direction | Zones à fort potentiel et accès facile |
| Où livrer est coûteux, et à quelle heure | Exploitation | Communes difficiles, effet des heures d'affluence |
| Faut-il un supplément ou une tournée dédiée dans une zone | Direction | Écart entre potentiel et difficulté, par zone |

## Ce que l'outil n'est pas

Pas une prévision de ventes : le potentiel est une **estimation par indicateurs ouverts**
(par exemple, le nombre de logements chauffés au fioul). Pas de temps réel : les décisions
concernées se prennent au mois ou au trimestre. Pas d'intelligence artificielle : des classements
documentés et vérifiables.

## Coût et charge (estimations)

| Poste | Estimation |
|---|---|
| Licences | 0 € (logiciels libres, données ouvertes) |
| Charge de mise en service (données réelles, calibration, tests) | 8 à 15 jours de travail, hors disponibilité de l'exploitation (~3 h) |
| Hébergement | Serveur interne existant ou petite instance ; à chiffrer avec le prestataire informatique |
| Maintenance | ~2 jours par an (mise à jour des sources annuelles) |

Ces chiffres sont des ordres de grandeur, à affiner après la phase 1.

## Risques

1. **Le potentiel estimé peut ne pas refléter les ventes réelles.** Parade : un test unique contre
   des ventes agrégées par commune avant tout usage décisionnel.
2. **Non-adoption.** Parade : deux utilisateurs-pilotes nommés (un commercial, l'exploitation) et un
   point d'usage à 8 semaines.
3. **Données mal appariées** (fusions de communes). Parade : rapport de couverture à chaque construction.
4. **Confidentialité** des paramètres internes. Parade : dépôt privé, hébergement interne, accès authentifié.

## Mesure du succès

Sur 3 mois : usage régulier par au moins deux profils ; au moins une décision documentée
influencée par l'atlas (ciblage de campagne, ordre d'appel, planification d'une zone) ; écart entre
temps prévus et réels de tournée inférieur à 20 %.

## Ce que nous demandons à la direction

1. **Valider le pilote de 2 semaines** (phase 1 de la feuille de route : données réelles et test du potentiel).
2. **Un export des ventes par commune** sur 12 mois, sans donnée client, pour tester le potentiel.
3. **Les coordonnées des dépôts** et 3 heures du responsable exploitation pour la calibration.
4. **Un sponsor** qui arbitre à 8 semaines : on poursuit, on corrige ou on arrête.

## Coût de ne rien faire

Continuer à décider à l'expérience reste possible. Le risque est de ne pas voir ce qui n'est pas
dans la tête de ceux qui connaissent le terrain, et de perdre ce savoir quand ils partent.
