"""Outils communs de lecture des fichiers CSV officiels (codes, nombres, encodage)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from atlas_hympyr.config import ConfigError

ENCODINGS = ("utf-8-sig", "latin-1")


def check_file(path: str | Path, how_to: str) -> Path:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Fichier introuvable : {p}. {how_to}")
    return p


def require_columns(mapping: dict[str, str | None], needed: list[str], where: str) -> None:
    missing = [k for k in needed if not mapping.get(k)]
    if missing:
        raise ConfigError(
            f"{where} : colonnes non renseignées {missing}. Utiliser "
            "`python -m atlas_hympyr.etl.colonnes <fichier>` pour lister les colonnes du fichier."
        )


def normalize_code(s: pd.Series) -> pd.Series:
    """Code commune sur 5 caractères (les zéros de tête sont souvent perdus : 09001 -> 9001)."""
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(5)


def to_number(s: pd.Series) -> pd.Series:
    """Convertit en nombres (virgule décimale acceptée) ; valeurs illisibles -> NaN."""
    if s.dtype.kind in "if":
        return s.astype(float)
    return pd.to_numeric(s.astype(str).str.strip().str.replace(",", ".", regex=False), errors="coerce")


def read_csv_flexible(path: Path, sep: str, **kwargs) -> pd.DataFrame:
    last: Exception | None = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, sep=sep, encoding=enc, dtype=str, **kwargs)
        except UnicodeDecodeError as exc:
            last = exc
    raise ValueError(f"Encodage illisible pour {path} : {last}")


def in_departements(codes: pd.Series, departements: list[str]) -> pd.Series:
    return codes.str[:2].isin(departements)
