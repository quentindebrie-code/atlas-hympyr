"""Résidences principales par combustible de chauffage (recensement Insee), maille communale.

Les noms de colonnes du fichier téléchargé sont à renseigner dans config/settings.yaml
(sources.insee_logement.colonnes) : ils n'ont pas pu être vérifiés depuis l'environnement de
développement. Aide : python -m atlas_hympyr.etl.colonnes <fichier> --cherche fioul bois
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from atlas_hympyr.etl.tabular import (
    check_file,
    in_departements,
    normalize_code,
    read_csv_flexible,
    require_columns,
    to_number,
)

HOW_TO = (
    "Télécharger le fichier communal du recensement (logements, combustible principal de chauffage) "
    "sur insee.fr et le déposer à cet emplacement."
)


def load_insee_logement(cfg_source: dict[str, Any], departements: list[str]) -> pd.DataFrame:
    cols = dict(cfg_source.get("colonnes") or {})
    require_columns(cols, ["code", "rp_fioul"], "sources.insee_logement")
    path = check_file(cfg_source["fichier"], HOW_TO)
    wanted = [
        c for c in (cols.get("code"), cols.get("rp_total"), cols.get("rp_fioul"), cols.get("rp_bois")) if c
    ]
    raw = read_csv_flexible(path, cfg_source.get("separateur", ";"), usecols=wanted)
    out = pd.DataFrame({"code": normalize_code(raw[cols["code"]])})
    for target in ("rp_total", "rp_fioul", "rp_bois"):
        src = cols.get(target)
        out[target] = to_number(raw[src]) if src else float("nan")
    out = out[in_departements(out["code"], departements)]
    return out.groupby("code", as_index=False).sum(min_count=1)
