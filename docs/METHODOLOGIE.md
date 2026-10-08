## Méthodologie

### Principe

Pour chaque commune, l'atlas calcule des **rangs en percentile (0-100) sur le territoire**. On
classe, on ne prédit pas : un score de 90 signifie « mieux placé que 90 % des communes de la zone »,
pas « 90 % de chances de vendre ». Les valeurs brutes (volumes, minutes, mètres) restent
affichées à côté des scores.

### 1. Potentiel par produit

| Produit | Proxy du volume estimé | Ce que le proxy ne dit pas |
|---|---|---|
| Fioul domestique | Résidences principales chauffées au fioul (recensement Insee) | Consommation réelle (surface, isolation), résidences secondaires, tertiaire, cuves collectives |
| Granulés | Résidences principales chauffées avec un combustible « autre » (recensement Insee, `P22_RP_CAUT`) | **Proxy faible.** La base communale Insee n'a pas de variable « bois » (fioul, électricité, gaz de ville, gaz bouteille/citerne, autre). « Autre » mélange bois (bûches comprises), charbon et divers ; il ne distingue pas poêles à granulés et cheminées. Le test contre les ventes réelles décide s'il reste affiché |
| GNR | Surface agricole déclarée (RPG) | Intensité de consommation selon les cultures, élevage, **chantiers et travaux publics (hors RPG)** |
| Gasoil routier | Poids lourds diesel détenus par des professionnels (SDES, parc par commune, millésime 2024) | Où ils s'approvisionnent réellement (stations, cartes carburant, dépôts) |
| AdBlue | Poids lourds diesel professionnels Crit'Air 2 et 3 (SDES) | Idem. **Hypothèse non vérifiée** : Crit'Air 2 ~ Euro VI et 3 ~ Euro IV/V, normes où la dépollution SCR (AdBlue) domine ; à faire confirmer |

Pour chaque produit : `vol_` (volume estimé), `pot_` (rang du volume, 0-100), `dens_` (volume par
km²) et `densp_` (rang de la densité). **Une commune sans demande vaut 0** et ne participe pas au
classement (elle ne reçoit pas un score intermédiaire).

La **densité** compte parce qu'une tournée se rentabilise par le nombre de clients livrables par
kilomètre parcouru, pas par la taille d'une commune.

### 2. Difficulté d'accès (0 = facile, 100 = très difficile)

Moyenne pondérée de rangs, depuis le dépôt choisi :

| Composante | Définition | Poids par défaut |
|---|---|---|
| Temps | Durée de trajet (min), éventuellement ajustée de l'heure de départ | 0,35 |
| Sinuosité | Somme des changements de cap par km de route (°/km), tracé rééchantillonné tous les 250 m | 0,20 |
| Altitude | Altitude de la commune (m), proxy de l'exposition hivernale | 0,15 |
| Dénivelé | Dénivelé positif cumulé le long du trajet (m), filtre d'hystérésis de 5 m | 0,20 |
| Circulation | Indice 0-100 du trafic (optionnel, saisi par vos soins) | 0,10 |

- Si une composante est **indisponible**, les poids des autres sont renormalisés et la
  **complétude** est affichée (part du poids total réellement utilisée). En dessous de 70 %,
  l'application avertit.
- Les poids sont **des choix de jugement**, pas des paramètres estimés : à discuter avec
  l'exploitation et à tester (sensibilité : le classement des 50 communes les plus difficiles
  change-t-il beaucoup si on déplace un poids de 0,10 ?).
- Classes : quartiles du score (Facile, Moyen, Difficile, Très difficile).

**Routage.** Deux modes : *estimation* (vol d'oiseau x coefficient de détour, ordre de grandeur, ni
sinuosité ni dénivelé) et *OSRM* auto-hébergé sur OpenStreetMap (durée, distance, tracé). Le profil
OSRM par défaut est « voiture » : un coefficient poids lourd à calibrer corrige les durées. Les
points d'arrivée sont les centroïdes des communes, recalés sur la route la plus proche par OSRM.

**Heures d'affluence.** `config/penalites_horaires.csv` définit des coefficients (>= 1) par zone
(`ALL`, `DEP:31` ou code commune) et plage horaire ; quand plusieurs règles s'appliquent, on prend la
plus forte (elles ne se cumulent pas). Le gabarit livré est **neutre (1,00)** : aucune valeur
inventée, à calibrer par l'exploitation.

### 3. Priorité de ciblage

`priorité = (w_pot x potentiel + w_dens x rang de densité + w_fac x (100 - difficulté)) / somme des poids`,
poids réglables dans la page Ciblage (valeurs par défaut dans `config/settings.yaml`). Si la
difficulté est indisponible, seule la demande compte.

### 4. Validation

Le potentiel est un proxy : **il faut le tester**. `python -m atlas_hympyr.backtest` compare le
potentiel estimé aux ventes réelles agrégées par commune (corrélation de Spearman, part du volume
réel située dans les 30 % de communes au plus fort potentiel). Repères indicatifs proposés :
Spearman > 0,5 et part > 0,6 ; en dessous, recalibrer avant de décider. Ces seuils sont une
proposition, pas une norme.

### 5. Représentation

Cartes en dégradés d'une seule teinte (bleu pour le potentiel, orange pour la difficulté), plus
foncé = plus élevé. La rampe bleue est celle de la palette de référence validée ; **la rampe orange
est dérivée de la teinte orange de cette même palette et n'a pas été passée au validateur de
daltonisme** (usage séquentiel monochrome, donc risque faible, mais non vérifié). Les valeurs sont
toujours lisibles au survol et dans les tableaux.

### 6. Limites connues

- Les proxys ne mesurent ni les parts de marché ni la concurrence.
- Les fusions de communes entre millésimes peuvent désapparier des codes : voir le rapport de couverture.
- Les données SDES les plus récentes sont provisoires (révisées pendant plusieurs années).
- Les temps estimés hors OSRM sont approximatifs, et ceux d'OSRM sont ceux d'un véhicule léger
  sans correction poids lourd.
- Aucune restriction de tonnage ou de hauteur n'est modélisée (OpenStreetMap les renseigne
  de façon inégale).
- Le score n'est pas un modèle prédictif : il ne contient aucun apprentissage automatique.
