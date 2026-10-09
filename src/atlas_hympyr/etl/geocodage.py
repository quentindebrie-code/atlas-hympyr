"""Géocodage des adresses de dépôts (Géoplateforme IGN, repli sur l'API Adresse).

Un dépôt de config/settings.yaml peut être donné par `adresse` au lieu de `lat`/`lon`. Le résultat
(adresse retrouvée et score) est affiché à la construction pour être relu par un humain : un
géocodage qui tombe sur la mauvaise commune fausserait tous les temps de trajet.

Format de réponse supposé (GeoJSON de type BAN : features[].geometry.coordinates = [lon, lat],
properties.label / properties.score). Les points d'accès n'ont pas pu être vérifiés depuis
l'environnement de développement : toute réponse inattendue produit une erreur explicite.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from atlas_hympyr.config import ConfigError
from atlas_hympyr.etl.communes import GetJson, default_get_json

ENDPOINTS = (
    "https://data.geopf.fr/geocodage/search",
    "https://api-adresse.data.gouv.fr/search/",
)
SCORE_MIN = 0.5  # seuil proposé ; sous ce score l'adresse est considérée comme non fiable


def slugify(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def geocode(adresse: str, get_json: GetJson | None = None) -> dict[str, Any]:
    get = get_json or default_get_json
    errors: list[str] = []
    for url in ENDPOINTS:
        try:
            fc = get(url, {"q": adresse, "limit": "1"})
            feat = (fc.get("features") or [None])[0]
            if feat is None:
                errors.append(f"{url} : aucun résultat")
                continue
            lon, lat = feat["geometry"]["coordinates"][:2]
            props = feat.get("properties") or {}
            return {
                "lat": round(float(lat), 6),
                "lon": round(float(lon), 6),
                "adresse_trouvee": props.get("label", "?"),
                "score": round(float(props.get("score", 0.0)), 3),
            }
        except (RuntimeError, KeyError, TypeError, ValueError, IndexError) as exc:
            errors.append(f"{url} : {exc}")
    raise ConfigError(f"Géocodage impossible pour « {adresse} » : {' ; '.join(errors)}")


def resolve_depots(
    depots: list[dict[str, Any]], get_json: GetJson | None = None, log=print
) -> list[dict[str, Any]]:
    """Complète lat/lon des dépôts donnés par adresse ; vérifie unicité des id et score."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for d in depots:
        d = dict(d)
        nom = d.get("nom") or d.get("adresse") or "dépôt"
        d.setdefault("id", slugify(nom))
        if d["id"] in seen:
            raise ConfigError(f"Identifiant de dépôt en double : {d['id']}")
        seen.add(d["id"])
        if d.get("lat") is None or d.get("lon") is None:
            if not d.get("adresse"):
                raise ConfigError(f"Dépôt « {nom} » : renseigner `adresse` ou `lat` et `lon`")
            g = geocode(d["adresse"], get_json)
            d.update(g)
            flag = "" if g["score"] >= SCORE_MIN else "  <-- SCORE FAIBLE, À VÉRIFIER"
            log(f"[depots] {nom} -> {g['adresse_trouvee']} (score {g['score']}){flag}")
            if g["score"] < SCORE_MIN:
                raise ConfigError(
                    f"Dépôt « {nom} » : adresse trouvée « {g['adresse_trouvee']} » avec un score de "
                    f"{g['score']} (< {SCORE_MIN}). Corriger l'adresse ou fournir lat/lon."
                )
        out.append(d)
    return out
