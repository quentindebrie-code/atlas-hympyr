# Données

- `raw/` : fichiers sources téléchargés (Insee, SDES, RPG, MNT...). **Non versionnés.**
- `processed/` : atlas construit (`atlas.parquet`, `atlas.geojson`, `routes/`, `meta.json`). **Non versionné.**

Sans `processed/atlas.parquet`, l'application charge automatiquement un territoire de
**démonstration synthétique** (communes fictives, bandeau rouge permanent).

Construction : voir le README à la racine et `docs/SOURCES.md`.
