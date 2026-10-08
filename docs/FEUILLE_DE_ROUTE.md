# Feuille de route

Les durées sont des **estimations** pour une personne à temps partiel sur le sujet.

## Phase 0 : socle (réalisé)

- Application complète sur territoire de démonstration synthétique (6 vues, export CSV).
- Scripts d'import des données réelles, testés sur fichiers fictifs.
- Documentation, tests (64), CI GitHub Actions, Dockerfile.

*Limite : jamais exécuté sur les vrais fichiers.*

## Phase 1 : quick win, données réelles et validation (1 à 2 semaines)

| Livrable | Critère d'acceptation |
|---|---|
| Fichiers Insee et SDES téléchargés, colonnes renseignées | `etl.build` terminé, couverture >= 95 % pour chaque source |
| Coordonnées des dépôts renseignées | Au moins un dépôt dans `settings.yaml` |
| Vue commerciale fioul, GNR, gasoil routier avec données réelles | Les 10 premières communes ont du sens pour un commercial (revue à 3 personnes) |
| **Test contre les ventes réelles** | Spearman et part du volume lus avec la direction ; décision sur les produits utilisables |
| Démo à la direction | Décision go / no-go phase 2 |

## Phase 2 : accès et exploitation (2 à 4 semaines)

| Livrable | Critère d'acceptation |
|---|---|
| Serveur OSRM sur extrait OpenStreetMap + MNT | Sinuosité et dénivelé calculés pour >= 98 % des communes |
| Calibration des temps de trajet | Erreur relative moyenne < 20 % sur 20 à 30 trajets réels |
| Coefficients d'affluence renseignés par l'exploitation | Fichier `penalites_horaires.csv` validé par le responsable |
| Granulés : proxy affiné si le test le montre insuffisant | Spearman amélioré ou produit retiré de l'outil |

## Phase 3 : intégration et pérennisation (en continu)

- Page « potentiel de la commune » dans le cockpit d'appels (consultation par code commune, sans
  donnée client dans l'atlas).
- Coefficient de pénalité de l'atlas dans l'optimiseur de tournées.
- Hébergement interne authentifié ; mise à jour annuelle des sources, assignée à une personne nommée.
- Revue à 8 semaines puis à 6 mois selon les indicateurs de `CALIBRATION.md`.

## Hors périmètre volontaire

Temps réel du trafic, prévision de ventes par apprentissage automatique, données clients
individuelles. À rouvrir seulement si une décision précise l'exige et que les phases 1 et 2 ont
prouvé leur utilité.
