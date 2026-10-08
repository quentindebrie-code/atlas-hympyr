"""Parc de véhicules routiers par commune (SDES, export DiDo) : poids lourds d'entreprises, etc.

Le fichier est volumineux (toute la France, plusieurs dimensions) : lecture par blocs, filtrage des
départements dès la lecture. Les noms de colonnes et les valeurs à retenir sont à renseigner dans
config/settings.yaml (sources.sdes_parc) : ils n'ont pas pu être vérifiés depuis l'environnement de
développement. Aide : python -m atlas_hympyr.etl.colonnes <fichier> --valeurs <colonne>
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from atlas_hympyr.config import ConfigError
from atlas_hympyr.etl.tabular import (
    check_file,
    in_departements,
    normalize_code,
    require_columns,
    to_number,
)

HOW_TO = "Exporter le jeu « Parc de véhicules routiers » (communal) depuis DiDo (SDES) en CSV."
FILTER_COLUMNS = ("genre", "energie", "utilisateur", "crit_air")


def _norm(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.casefold()


def load_sdes_parc(
    cfg_source: dict[str, Any],
    departements: list[str],
    chunksize: int = 500_000,
) -> tuple[pd.DataFrame, dict[str, int]]:
    cols = dict(cfg_source.get("colonnes") or {})
    require_columns(cols, ["code", "nombre"], "sources.sdes_parc")
    filtres: dict[str, dict[str, list[str]]] = dict(cfg_source.get("filtres") or {})
    if not filtres:
        raise ConfigError("sources.sdes_parc.filtres : aucun indicateur défini")

    for indicateur, regles in filtres.items():
        for colonne, valeurs in regles.items():
            if colonne not in FILTER_COLUMNS:
                raise ConfigError(f"Filtre « {indicateur}.{colonne} » : colonne inconnue")
            if not cols.get(colonne):
                raise ConfigError(
                    f"Filtre « {indicateur}.{colonne} » : renseigner sources.sdes_parc.colonnes.{colonne}"
                )
            if not valeurs:
                raise ConfigError(
                    f"Filtre « {indicateur}.{colonne} » vide : renseigner les valeurs exactes du "
                    "fichier (sinon tout le parc serait compté)."
                )

    annee_col = cfg_source.get("annee_colonne")
    annee_val = cfg_source.get("annee_valeur")
    path = check_file(cfg_source["fichier"], HOW_TO)

    needed = {cols["code"], cols["nombre"]}
    needed |= {cols[c] for r in filtres.values() for c in r}
    if annee_col and annee_val is not None:
        needed.add(annee_col)

    sums: dict[str, pd.Series] = {k: pd.Series(dtype=float) for k in filtres}
    stats = {"lignes_lues": 0, "valeurs_non_numeriques": 0}
    reader = None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            reader = pd.read_csv(
                path,
                sep=cfg_source.get("separateur", ";"),
                encoding=enc,
                dtype=str,
                usecols=sorted(needed),
                chunksize=chunksize,
            )
            break
        except UnicodeDecodeError:
            continue
    if reader is None:
        raise ValueError(f"Encodage illisible : {path}")

    for chunk in reader:
        chunk = chunk.assign(_code=normalize_code(chunk[cols["code"]]))
        chunk = chunk[in_departements(chunk["_code"], departements)]
        if annee_col and annee_val is not None:
            chunk = chunk[chunk[annee_col].astype(str).str.strip() == str(annee_val)]
        stats["lignes_lues"] += len(chunk)
        nombre = to_number(chunk[cols["nombre"]])
        stats["valeurs_non_numeriques"] += int(nombre.isna().sum())
        nombre = nombre.fillna(0.0)
        for indicateur, regles in filtres.items():
            mask = pd.Series(True, index=chunk.index)
            for colonne, valeurs in regles.items():
                mask &= _norm(chunk[cols[colonne]]).isin([str(v).strip().casefold() for v in valeurs])
            part = nombre[mask].groupby(chunk.loc[mask, "_code"]).sum()
            sums[indicateur] = sums[indicateur].add(part, fill_value=0.0)

    out = pd.DataFrame(sums).fillna(0.0)
    out.index.name = "code"
    return out.reset_index(), stats
