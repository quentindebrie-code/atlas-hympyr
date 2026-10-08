# Calibration et validation

Trois réglages rendent l'atlas fiable. Aucun ne demande de donnée client individuelle.

## 1. Temps de trajet (responsable exploitation, ~2 h)

L'outil sous-estime les temps tant qu'il n'est pas calé sur vos tournées.

1. Relever 20 à 30 trajets réels dépôt -> commune (heure de départ, durée, distance), répartis entre
   plaine, zone urbaine et montagne.
2. Comparer à l'atlas (page Vue exploitation, Temps de trajet) : calculer l'erreur relative
   moyenne par type de zone.
3. En mode *estimation* : ajuster `vitesse_moyenne_kmh` et `coef_detour`. En mode *OSRM* : ajuster
   `coef_temps_poids_lourd` (le profil OSRM par défaut est celui d'une voiture).
4. Si l'erreur reste forte en montagne, c'est un signal : sinuosité et dénivelé doivent compter
   davantage (poids de `config/settings.yaml`).

Critère d'acceptation proposé (à valider avec l'exploitation) : erreur relative moyenne < 20 % sur
l'ensemble des trajets relevés, sans biais systématique par zone.

## 2. Heures d'affluence (responsable exploitation, ~1 h)

Compléter `config/penalites_horaires.csv` (séparateur `;`) :

```
zone;heure_debut;heure_fin;coef;commentaire
DEP:31;7.0;9.0;1.30;Rocade et accès nord-ouest, retours chauffeurs
31555;17.0;19.0;1.40;Centre-ville : stationnement et circulation
```

- `zone` : `ALL`, `DEP:<code>` ou un code commune. Heures décimales (`7.5` = 7 h 30).
- `coef` >= 1 : multiplicateur du temps de trajet. Quand plusieurs règles s'appliquent, la plus
  forte est retenue.
- Les valeurs ci-dessus sont des **exemples de format, pas des mesures**. Renseigner ce que les
  chauffeurs observent, puis comparer à des trajets chronométrés.

## 3. Validation du potentiel (direction / ADV, ~1 jour)

Le test qui dit si le potentiel est utile :

1. Extraire des ventes de l'exercice écoulé, **agrégées par commune de livraison** (colonnes
   `code;volume`), un fichier par produit. Pas de nom, pas d'adresse. Masquer ou regrouper les
   communes de moins de 5 clients.
2. Lancer :
   ```bash
   python -m atlas_hympyr.backtest ventes_fioul.csv --produit fioul
   ```
3. Lire : la corrélation de Spearman et la part du volume réel située dans les 30 % de communes au
   plus fort potentiel.

| Résultat | Lecture proposée |
|---|---|
| Spearman > 0,5 et part > 0,6 | Le potentiel est un guide exploitable pour cibler |
| Entre les deux | Utilisable pour dégrossir, pas pour arbitrer finement ; chercher ce qui manque (concurrence, canal) |
| En dessous | Ne pas décider avec ce score avant d'avoir recalibré le proxy |

Ces seuils sont un repère proposé, pas une norme : à valider avec la direction avant de s'engager
sur un usage.

Un résultat faible n'est pas un échec du projet : il dit que le proxy ne suffit pas pour ce produit
(typiquement les granulés, dont le proxy « autre combustible » est le plus fragile).

## 4. Sensibilité des poids

Avant la présentation à la direction : déplacer chaque poids de difficulté de ±0,10 et vérifier que
la liste des 50 communes les plus difficiles reste stable. Si elle change beaucoup, le classement
dépend du jugement plus que des données : le dire.

## 5. Mesure en continu

| Indicateur | Fréquence | Seuil de décision |
|---|---|---|
| Utilisation (sessions par profil) | Mensuelle | Pas d'usage régulier à 8 semaines : arrêter ou repenser |
| Part des appels / prospections vers les communes du quartile supérieur | Trimestrielle | Hausse mesurable vs baseline |
| Écart temps prévus / réels de tournée | Trimestrielle | Dérive > 20 % : recalibrer |
