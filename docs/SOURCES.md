# Sources de données

**Légende du statut.** *Vérifié* : consulté pendant le développement (08/10/2026) via la
documentation en ligne. *Non vérifié* : connaissance générale, à confirmer avant usage. Les
fichiers eux-mêmes n'ont **jamais** pu être téléchargés depuis l'environnement de développement
(accès réseau bloqué) : les noms de colonnes sont donc toujours « à confirmer ».

| Source | Usage | Maille | Statut | Point d'attention |
|---|---|---|---|---|
| Insee, recensement 2022, combustible principal de chauffage | `rp_fioul`, `rp_bois`, `rp_total` | Commune | Existence vérifiée (études Insee par commune, base logement) ; colonnes à confirmer | Le fioul est plus répandu en zone rurale (Insee Première n° 2088, janv. 2026) ; « bois » inclut les bûches |
| SDES, parc de véhicules routiers | `pl_entreprises`, `pl_diesel_recents` | Commune | Contenu vérifié : genre, motorisation, Crit'Air, PTAC, utilisateur et secteur d'activité, jusqu'au 01/01/2026 ; colonnes et valeurs à confirmer | Diffusé via DiDo depuis mai 2025 (explorateur + API) ; données récentes provisoires ; localisation = adresse de la carte grise |
| RPG (IGN / ASP) | `surf_agri_ha` | Parcelle ou îlot | Description vérifiée (parcelles agricoles déclarées PAC, version anonymisée) ; téléchargement à confirmer | Surfaces recalculées par l'outil depuis la géométrie ; les exploitations non déclarées PAC sont absentes |
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
