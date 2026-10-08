# Sécurité, RGPD et conformité

*Ce document est une analyse de conception, pas un avis juridique : à faire valider par le DPO ou le
conseil habituel de l'entreprise.*

## Données traitées

| Donnée | Nature | Sensibilité |
|---|---|---|
| Insee, SDES, RPG, OSM, MNT | Open data agrégées par commune | Publique |
| `config/settings.yaml` (dépôts, poids, coefficients) | Paramètres internes | **Interne** : les coordonnées des dépôts et les coefficients de calibration ne sont pas publics |
| Fichier de validation (ventes par commune) | Volumes agrégés Hympyr | **Confidentiel commercial** ; pas de donnée personnelle s'il est agrégé |

Conception : **aucune donnée client individuelle n'entre dans l'outil.** L'atlas ne contient aucun
nom, adresse ou identifiant de client.

## RGPD

- Pas de donnée personnelle traitée par l'application elle-même. La population communale et les
  effectifs sont des statistiques agrégées.
- **Point de vigilance** : le fichier de ventes du `backtest` doit être agrégé par commune. Les
  communes à très faible effectif de clients peuvent permettre une réidentification ; masquer ou
  regrouper celles de moins de 5 clients (seuil proposé, à valider avec le DPO) et ne jamais y
  inclure d'adresse, de nom ou de numéro de client. Ne pas versionner ce fichier (`data/raw/` est
  ignoré par Git).
- Si une version future croise des adresses de clients, ce serait un nouveau traitement : analyse
  d'impact, mention au registre, base légale et information des personnes à prévoir.

## AI Act

L'outil ne contient **aucun système d'intelligence artificielle ou d'apprentissage automatique** :
les scores sont des rangs et des moyennes pondérées documentés. Si un modèle prédictif ou un LLM est
ajouté plus tard, ré-évaluer la classification et les obligations de transparence.

## Contrôles de sécurité

| Risque | Mesure en place ou recommandée |
|---|---|
| Accès non autorisé | **L'application n'a pas d'authentification intégrée.** La déployer uniquement sur le réseau interne ou derrière une passerelle d'authentification (proxy inverse avec SSO ou authentification basique sur HTTPS). Ne pas l'exposer directement sur Internet |
| Fuite de paramètres internes | Dépôt GitHub **privé** ; ne pas publier `config/settings.yaml` rempli (dépôts, coefficients) hors du dépôt privé |
| Hébergement sur un service tiers (ex. Streamlit Community Cloud) | À éviter pour les données réelles configurées : hébergement interne ou UE de votre choix, selon la politique de l'entreprise |
| Requêtes vers des tiers depuis le navigateur | Le fond de carte par défaut (CARTO) est chargé directement par le navigateur de l'utilisateur. `ATLAS_MAP_STYLE=white-bg` le supprime |
| Chaîne d'approvisionnement | Dépendances à versions minimales dans `pyproject.toml` ; `pip-audit` en CI (informatif) ; figer les versions (`pip freeze`) pour la production |
| Secrets | Aucun secret requis. Ne jamais mettre de jeton dans `settings.yaml`. `.env` et `secrets.toml` sont ignorés par Git |
| Intégrité des données | Rapport de couverture à chaque construction ; mode démonstration signalé par un bandeau permanent pour éviter qu'une valeur fictive soit prise pour réelle |
| Conteneur | Image sans données ni secrets ; exécution en utilisateur non root ; données montées en lecture seule |

## Pérennité

Documentation dans `docs/`, tests automatisés (57), configuration externalisée : l'outil survit à
son auteur si la procédure de mise à jour annuelle (voir `FEUILLE_DE_ROUTE.md`) est assignée à une
personne nommée.
