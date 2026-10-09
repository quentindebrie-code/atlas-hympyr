# Données

- `raw/` : fichiers sources téléchargés (Insee, SDES, RPG, MNT...). **Non versionnés.**
- `processed/` : atlas construit (`atlas.parquet`, `atlas.geojson`, `routes/`, `meta.json`).
  **Versionné** pour que l'application hébergée affiche les vraies données. Il contient des données
  ouvertes agrégées et les coordonnées des dépôts : **le dépôt doit rester privé.**

Sans `processed/atlas.parquet`, l'application charge automatiquement un territoire de
**démonstration synthétique** (communes fictives, bandeau rouge permanent).

Construction : voir le README à la racine et `docs/SOURCES.md`.
