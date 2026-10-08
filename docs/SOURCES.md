# Sources de données

**Légende du statut.** *Vérifié* : consulté pendant le développement (08/10/2026) via la
documentation en ligne. *Non vérifié* : connaissance générale, à confirmer avant usage. Les
fichiers eux-mêmes n'ont **jamais** pu être téléchargés depuis l'environnement de développement
(accès réseau bloqué) : un « vérifié » porte sur la documentation, pas sur le fichier.

| Source | Usage | Maille | Statut | Point d'attention |
|---|---|---|---|---|
| Insee, base-cc-logement-2022 (CSV zippé) | `rp_fioul` (`P22_RP_CFIOUL`), `rp_autre` (`P22_RP_CAUT`), `rp_total` (`P22_RP`), code `CODGEO` | Commune | **URL et noms de colonnes vérifiés** dans la documentation Insee (08/10/2026) ; fichier non ouvert, en-tête contrôlé à la lecture | **Pas de variable bois** ; fioul plus répandu en zone rurale (Insee Première n° 2088, janv. 2026) |
| data.gouv.fr, « Liste des communes de France 2026 » (Licence Ouverte v2) | `altitude_m` (`altitude_moyenne`, code `code_insee`) | Commune | **URL et colonnes vérifiés** dans la documentation du jeu ; fichier non ouvert | Altitude de repli quand aucun MNT n'est configuré ; valeurs manquantes possibles |
| SDES, parc de véhicules routiers | `pl_entreprises`, `pl_diesel_recents` | Commune | **Fichier réel ouvert le 08/10/2026** (221 Mo) : colonnes COMMUNE_CODE, CARBURANT, CRIT_AIR, STATUT_UTILISATEUR, GROUPE, CATEGORIE, PARC_2011 à PARC_2026 ; valeurs relevées et configurées | Diffusé via DiDo depuis mai 2025 (explorateur + API) ; données récentes provisoires ; localisation = adresse de la carte grise |
| RPG (IGN / ASP) | `surf_agri_ha` | Parcelle ou îlot | Description vérifiée (parcelles agricoles déclarées PAC, version anonymisée) ; **URL de téléchargement officielle non vérifiée** : récupération manuelle | Surfaces recalculées par l'outil depuis la géométrie ; les exploitations non déclarées PAC sont absentes |
| API Découpage administratif (geo.api.gouv.fr) | Contours, noms, population | Commune | Endpoint et paramètres vérifiés (`/departements/{code}/communes`, `format=geojson`, `geometry=contour`) ; noms des propriétés renvoyées **non vérifiés** (le parseur échoue avec un message clair s'ils diffèrent) | Surface et centroïde recalculés depuis la géométrie |
| DREAL Occitanie, cartes de trafic | `trafic_idx` (optionnel, saisie manuelle) | Poste de comptage, réseau national | Vérifié : publications **PDF** annuelles (trafic moyen journalier annuel et mensuel, part de poids lourds) | **Pas de profil horaire ouvert vérifié** : les heures d'affluence passent par des coefficients de calibration |
| MNT IGN (RGE ALTI / BD ALTI) ou équivalent | Altitude, dénivelé | Raster | Non vérifié | À télécharger ; l'outil lit tout GeoTIFF (n'importe quel CRS) |
| OpenStreetMap + OSRM | Temps, distance, tracé | Réseau routier | Non vérifié | Licence ODbL (attribution) ; serveur à auto-héberger ; profil voiture par défaut |

## Liens

- Insee Première n° 2088 (janvier 2026) : https://www.insee.fr/fr/statistiques/fichier/8722051/IP2088.pdf
- SDES, données sur le parc automobile : https://www.statistiques.developpement-durable.gouv.fr/donnees-sur-le-parc-automobile-francais-au-1er-janvier-2026
- data.gouv.fr, Parc de véhicules routiers : https://www.data.gouv.fr/datasets/parc-de-vehicules-routiers
- IGN, services RPG : https://geoservices.ign.fr/services-web-experts-agriculture
- API Découpage administratif : https://geo.api.gouv.fr/decoupage-administratif/communes
- DREAL Occitanie, trafics 2024 : https://www.occitanie.developpement-durable.gouv.fr/IMG/pdf/carte_flux_occitanie_2024_vf-2.pdf

## Licences

Vérifier la licence de chaque jeu avant diffusion (les jeux de l'administration française sont
généralement sous Licence Ouverte, **à confirmer jeu par jeu**). Citer les sources dans tout
document produit à partir de l'atlas. OpenStreetMap impose l'attribution ODbL.
