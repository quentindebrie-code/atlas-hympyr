"""Résidences principales par combustible de chauffage (recensement Insee), maille communale.

Fichier : « Logement — base des principaux indicateurs » (base-cc-logement-2022), CSV séparé par des
points-virgules. Colonnes vérifiées dans la documentation Insee (08/10/2026) :
CODGEO, P22_RP, P22_RP_CFIOUL (fioul), P22_RP_CAUT (« autre » combustible).

Il n'existe PAS de colonne « bois » dans ce fichier : le chauffage au bois y est noyé dans
« autre » (P22_RP_CAUT). Voir docs/METHODOLOGIE.md pour la conséquence sur les granulés.
"""

from __future__ import annotations

import difflib
import warnings
from typing import Any

import pandas as pd

from atlas_hympyr.config import ConfigError
from atlas_hympyr.etl.colonnes import read_header
from atlas_hympyr.etl.tabular import (
    check_file,
    in_departements,
    normalize_code,
    read_csv_flexible,
    require_columns,
    to_number,
)

HOW_TO = (
    "Le télécharger avec `python -m atlas_hympyr.etl.telecharger` ou depuis insee.fr "
    "(base-cc-logement-2022, format CSV) et le déposer à cet emplacement."
)
TARGETS = ("rp_total", "rp_fioul", "rp_autre")


def load_insee_logement(cfg_source: dict[str, Any], departements: list[str]) -> pd.DataFrame:
    cols = dict(cfg_source.get("colonnes") or {})
    require_columns(cols, ["code", "rp_fioul"], "sources.insee_logement")
    path = check_file(cfg_source["fichier"], HOW_TO)
    sep = cfg_source.get("separateur", ";")

    # On lit d'abord l'en-tête : une colonne absente doit produire un message utile, pas un KeyError.
    header = read_header(path, sep)
    for key in ("code", "rp_fioul"):
        if cols[key] not in header:
            close = difflib.get_close_matches(cols[key], header, n=5, cutoff=0.5)
            raise ConfigError(
                f"sources.insee_logement : colonne « {cols[key]} » ({key}) absente de {path.name}. "
                f"Colonnes proches : {close or 'aucune'}. Le millésime a peut-être changé (P22_ -> P23_ ?)."
            )
    wanted = [cols["code"]]
    for target in TARGETS:
        name = cols.get(target)
        if not name:
            continue
        if name in header:
            wanted.append(name)
        else:
            warnings.warn(
                f"Colonne optionnelle « {name} » ({target}) absente de {path.name} : ignorée.", stacklevel=2
            )
            cols[target] = None

    raw = read_csv_flexible(path, sep, usecols=list(dict.fromkeys(wanted)))
    out = pd.DataFrame({"code": normalize_code(raw[cols["code"]])})
    for target in TARGETS:
        src = cols.get(target)
        out[target] = to_number(raw[src]) if src else float("nan")
    out = out[in_departements(out["code"], departements)]
    return out.groupby("code", as_index=False).sum(min_count=1)
