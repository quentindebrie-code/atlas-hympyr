"""Altitude moyenne des communes (data.gouv.fr, « Liste des communes de France », Licence Ouverte v2).

Colonnes vérifiées dans la documentation du jeu : code_insee, altitude_moyenne (m). Valeurs
manquantes possibles : elles restent NaN (la difficulté est alors calculée sans cette composante).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from atlas_hympyr.config import ConfigError
from atlas_hympyr.etl.tabular import (
    check_file,
    in_departements,
    normalize_code,
    read_csv_flexible,
    require_columns,
    to_number,
)

HOW_TO = "Le télécharger avec `python -m atlas_hympyr.etl.telecharger`."


def load_altitude(cfg_source: dict[str, Any], departements: list[str]) -> pd.DataFrame:
    cols = dict(cfg_source.get("colonnes") or {})
    require_columns(cols, ["code", "altitude"], "sources.altitude")
    path = check_file(cfg_source["fichier"], HOW_TO)
    raw = read_csv_flexible(path, cfg_source.get("separateur", ","))
    missing = [c for c in (cols["code"], cols["altitude"]) if c not in raw.columns]
    if missing:
        raise ConfigError(f"sources.altitude : colonnes {missing} absentes de {path.name}")
    out = pd.DataFrame(
        {"code": normalize_code(raw[cols["code"]]), "altitude_m": to_number(raw[cols["altitude"]]).round(0)}
    )
    out = out[in_departements(out["code"], departements)]
    return out.groupby("code", as_index=False).mean()
