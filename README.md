# Atlas territorial Hympyr

Outil d'aide à la décision pour Hympyr Energies : **où est la demande, par produit, et à quel effort
peut-on la livrer ?** Une carte interactive (survol = détail de la commune) croise, pour chaque
commune des 7 départements desservis, un **potentiel commercial** et une **difficulté d'accès**
calculés à partir de données officielles et ouvertes. Aucune donnée client n'est utilisée.

| Vue | Pour qui | Question |
|---|---|---|
| Synthèse | Direction | Où sont les communes prioritaires, par produit ? |
| Vue commerciale | Commerciales, manager | Qui consomme quoi, où (fioul, granulés, GNR, gasoil routier, AdBlue) ? |
| Vue exploitation | Responsable exploitation | Où est-ce long, sinueux, montagneux ? Quel effet des heures d'affluence ? |
| Ciblage | Commerciaux, marketing, direction | Quelles N communes viser, avec quels arbitrages potentiel / accès ? Export CSV |
| Fiche commune | Tous | Tous les indicateurs d'une commune, comparés au territoire |
| Méthodologie | Tous | Sources, couverture des données, paramètres actifs |

> **État au 08/10/2026 : l'application fonctionne en mode démonstration** (communes fictives, valeurs
> aléatoires, bandeau rouge permanent). Les scripts d'import des données réelles sont écrits et
> testés sur des fichiers fictifs, **mais n'ont jamais tourné sur les vrais fichiers Insee / SDES /
> IGN** (accès réseau impossible depuis l'environnement de développement). Les noms de colonnes
> réels sont à renseigner dans `config/settings.yaml` : voir « Passer aux données réelles ».

## Démarrage rapide (démonstration)

```bash
python -m venv .venv && source .venv/bin/activate     # Python >= 3.11
pip install -e ".[dev]"
streamlit run app.py
pytest                                                # 57 tests
```

## Passer aux données réelles

1. `pip install -e ".[etl]"`
2. Télécharger les fichiers sources dans `data/raw/` (liste, liens et statut de vérification :
   [`docs/SOURCES.md`](docs/SOURCES.md)).
3. Repérer les colonnes avec l'aide fournie :
   ```bash
   python -m atlas_hympyr.etl.colonnes data/raw/insee_logement.csv --cherche fioul bois
   python -m atlas_hympyr.etl.colonnes data/raw/sdes_parc.csv --valeurs GENRE
   ```
4. Compléter `config/settings.yaml` : colonnes et filtres des sources, **coordonnées des dépôts**
   (`depots`), éventuellement le serveur OSRM et le MNT.
5. Construire l'atlas (les étapes non configurées sont ignorées avec un message, `--strict` pour
   échouer) :
   ```bash
   python -m atlas_hympyr.etl.build
   ```
   Le rapport de **couverture** par source s'affiche : en dessous de 95 % de communes
   appariées, corriger avant d'utiliser (millésime des codes communes, zéros de tête).
6. `streamlit run app.py` : le bandeau de démonstration disparaît.
7. **Valider le potentiel contre les ventes réelles** (voir `docs/CALIBRATION.md`) :
   ```bash
   python -m atlas_hympyr.backtest ventes_fioul_par_commune.csv --produit fioul
   ```

## Ce que l'outil est, et n'est pas

- C'est une **carte de potentiel estimé et de difficulté d'accès**, à partir de *proxies* ouverts
  (ex. nombre de logements chauffés au fioul). Ce n'est pas une prévision de ventes.
- Le temps réel est volontairement absent : relief, parc de logements et surfaces agricoles ne
  bougent pas à l'échelle d'une décision commerciale. Les heures d'affluence sont gérées par des
  **coefficients calibrés par l'exploitation** (`config/penalites_horaires.csv`), faute de données
  ouvertes horaires sur l'ensemble du réseau.
- Le score est un **classement relatif** (rangs sur le territoire), avec des poids de jugement
  réglables, pas un modèle statistique estimé.

## Structure

```
app.py                      point d'entrée Streamlit
config/settings.yaml        périmètre, dépôts, poids, sources et colonnes
config/penalites_horaires.csv   coefficients d'affluence (gabarit neutre)
src/atlas_hympyr/
  scoring.py                potentiel, difficulté, priorité, pénalités horaires
  geo.py                    surface, centroïde, sinuosité, dénivelé cumulé
  demo.py                   territoire synthétique de démonstration
  backtest.py               validation du potentiel contre des ventes agrégées
  data_access.py            lecture / écriture de l'atlas
  etl/                      import : communes, Insee, SDES, RPG, MNT, routage, build
  app/                      pages Streamlit
docs/                       méthodologie, sources, sécurité/RGPD, calibration, note direction, feuille de route
tests/                      57 tests (logique, import sur fichiers fictifs, application)
```

## Déploiement

Pas d'authentification intégrée : **ne pas exposer l'application sur Internet sans passerelle
d'authentification** (voir `docs/SECURITE_RGPD.md`).

```bash
docker build -t atlas-hympyr .      # non testé dans l'environnement de développement
docker run -p 8501:8501 -v "$(pwd)/data/processed:/app/data/processed:ro" atlas-hympyr
```

`ATLAS_MAP_STYLE=white-bg` supprime le fond de carte externe (aucune requête du navigateur vers un
tiers) ; par défaut, le fond CARTO est chargé par le navigateur.

## Documentation

[Méthodologie](docs/METHODOLOGIE.md) · [Sources](docs/SOURCES.md) ·
[Sécurité et RGPD](docs/SECURITE_RGPD.md) · [Calibration et validation](docs/CALIBRATION.md) ·
[Note à la direction](docs/NOTE_DIRECTION.md) · [Feuille de route](docs/FEUILLE_DE_ROUTE.md)

Licence : à définir par Hympyr Energies (dépôt privé, usage interne).
