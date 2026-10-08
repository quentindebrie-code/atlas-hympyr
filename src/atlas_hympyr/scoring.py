"""Calcul des scores : potentiel, densité, difficulté d'accès, priorité de ciblage.

Principe : des rangs en percentile (0-100) sur le territoire, jamais de valeurs magiques.
Les volumes bruts restent affichés à côté des scores.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CLASSES_DIFFICULTE = ("Facile", "Moyen", "Difficile", "Très difficile")
CLASSES_POTENTIEL = ("Faible", "Moyen", "Élevé", "Très élevé")

# Composante de difficulté -> colonne source dans la table des communes
COMPOSANTES_DIFFICULTE = {
    "temps": "trajet_min",
    "sinuosite": "sinuosite_deg_km",
    "altitude": "altitude_m",
    "denivele": "denivele_m",
    "trafic": "trafic_idx",
}


def pct_rank(s: pd.Series, zero_is_floor: bool = False) -> pd.Series:
    """Rang en percentile 0-100 (NaN conservés).

    zero_is_floor=True : les valeurs <= 0 reçoivent 0 et ne participent pas au classement
    (une commune sans demande ne doit pas obtenir un score intermédiaire).
    """
    s = pd.to_numeric(s, errors="coerce")
    out = pd.Series(np.nan, index=s.index, dtype=float)
    valid = s.notna()
    if zero_is_floor:
        pos = valid & (s > 0)
        out.loc[valid & ~pos] = 0.0
        valid = pos
    if valid.any():
        out.loc[valid] = s.loc[valid].rank(pct=True, method="average") * 100
    return out


def weighted_mean(parts: Mapping[str, pd.Series], weights: Mapping[str, float]) -> pd.Series:
    """Moyenne pondérée ligne à ligne en ignorant les composantes NaN (poids renormalisés)."""
    keys = [k for k in parts if weights.get(k, 0) > 0]
    if not keys:
        raise ValueError("Aucune composante avec un poids > 0")
    index = parts[keys[0]].index
    num = pd.Series(0.0, index=index)
    den = pd.Series(0.0, index=index)
    for k in keys:
        s = parts[k]
        w = float(weights[k])
        ok = s.notna()
        num = num + (s.fillna(0.0) * w).where(ok, 0.0)
        den = den + pd.Series(np.where(ok, w, 0.0), index=index)
    return (num / den).where(den > 0)


def classer(s: pd.Series, labels: tuple[str, ...]) -> pd.Series:
    """Classe par quartile de rang (quatre libellés)."""
    p = pct_rank(s)
    out = pd.cut(p, bins=[-0.001, 25, 50, 75, 100.001], labels=list(labels))
    return out.astype("object").where(p.notna(), None)


# --- potentiel -------------------------------------------------------------------------------


def produits_disponibles(df: pd.DataFrame, produits: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Produits dont la colonne indicateur existe et contient au moins une valeur."""
    out = []
    for key, p in produits.items():
        col = p.get("indicateur")
        if col in df.columns and df[col].notna().any():
            out.append(key)
    return out


def add_potentiel(df: pd.DataFrame, produits: Mapping[str, Mapping[str, Any]]) -> pd.DataFrame:
    """Ajoute, par produit : vol_, pot_ (percentile du volume), dens_ (par km²), densp_, cls_pot_."""
    out = df.copy()
    surface = pd.to_numeric(out["surface_km2"], errors="coerce").where(lambda s: s > 0)
    for key in produits_disponibles(out, produits):
        vol = pd.to_numeric(out[produits[key]["indicateur"]], errors="coerce")
        out[f"vol_{key}"] = vol
        out[f"pot_{key}"] = pct_rank(vol, zero_is_floor=True)
        dens = vol / surface
        out[f"dens_{key}"] = dens
        out[f"densp_{key}"] = pct_rank(dens, zero_is_floor=True)
        out[f"cls_pot_{key}"] = classer(out[f"pot_{key}"], CLASSES_POTENTIEL)
    return out


# --- difficulté d'accès ----------------------------------------------------------------------


def add_difficulte(
    df: pd.DataFrame,
    poids: Mapping[str, float],
    temps_col: str = "trajet_min",
) -> pd.DataFrame:
    """Ajoute d_<composante>, difficulte (0-100), difficulte_completude (0-1), cls_difficulte."""
    out = df.copy()
    sources = dict(COMPOSANTES_DIFFICULTE)
    sources["temps"] = temps_col
    parts: dict[str, pd.Series] = {}
    for name, col in sources.items():
        if col in out.columns and pd.to_numeric(out[col], errors="coerce").notna().any():
            out[f"d_{name}"] = pct_rank(out[col])
            parts[name] = out[f"d_{name}"]
    total_w = sum(float(w) for w in poids.values() if w and w > 0)
    if not parts or total_w <= 0:
        out["difficulte"] = np.nan
        out["difficulte_completude"] = 0.0
        out["cls_difficulte"] = None
        return out
    out["difficulte"] = weighted_mean(parts, poids)
    avail_w = sum(float(poids.get(k, 0)) for k in parts)
    out["difficulte_completude"] = avail_w / total_w
    out["cls_difficulte"] = classer(out["difficulte"], CLASSES_DIFFICULTE)
    return out


# --- priorité de ciblage -----------------------------------------------------------------------


def add_priorite(df: pd.DataFrame, produit: str, poids: Mapping[str, float]) -> pd.DataFrame:
    """Ajoute priorite_<produit> = moyenne pondérée de potentiel, densité et facilité d'accès."""
    out = df.copy()
    parts = {
        "potentiel": out[f"pot_{produit}"],
        "densite": out[f"densp_{produit}"],
    }
    if "difficulte" in out.columns and out["difficulte"].notna().any():
        parts["facilite"] = 100 - out["difficulte"]
    out[f"priorite_{produit}"] = weighted_mean(parts, poids)
    return out


def select_targets(
    df: pd.DataFrame,
    produit: str,
    n: int,
    *,
    departements: list[str] | None = None,
    potentiel_min: float = 0.0,
    difficulte_max: float = 100.0,
) -> pd.DataFrame:
    """Communes à cibler : filtres puis classement par priorité décroissante."""
    d = df
    if departements:
        d = d[d["dept"].isin(departements)]
    d = d[d[f"pot_{produit}"].fillna(0) >= potentiel_min]
    if "difficulte" in d.columns:
        d = d[d["difficulte"].fillna(0) <= difficulte_max]
    return d.sort_values(f"priorite_{produit}", ascending=False).head(n)


def concentration_curve(volumes: pd.Series) -> pd.DataFrame:
    """Courbe de concentration : part cumulée du volume selon la part de communes (triées)."""
    v = pd.to_numeric(volumes, errors="coerce").dropna()
    v = v[v > 0].sort_values(ascending=False)
    if v.empty:
        return pd.DataFrame({"part_communes": [0.0], "part_volume": [0.0]})
    n = len(v)
    cum = v.cumsum() / v.sum()
    return pd.DataFrame(
        {
            "part_communes": np.concatenate([[0.0], np.arange(1, n + 1) / n]),
            "part_volume": np.concatenate([[0.0], cum.to_numpy()]),
        }
    )


# --- heures d'affluence ---------------------------------------------------------------------


PENALITES_COLONNES = ["zone", "heure_debut", "heure_fin", "coef", "commentaire"]


def load_penalites(path: str | Path) -> pd.DataFrame:
    """Charge le CSV des pénalités horaires (séparateur ;). Fichier absent -> tableau vide."""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=PENALITES_COLONNES)
    df = pd.read_csv(p, sep=";", decimal=".", dtype={"zone": str})
    manquantes = [c for c in PENALITES_COLONNES[:4] if c not in df.columns]
    if manquantes:
        raise ValueError(f"Colonnes manquantes dans {p} : {manquantes}")
    if (df["coef"] < 1).any():
        raise ValueError(f"{p} : un coefficient < 1 est incohérent (une pénalité allonge le temps)")
    return df


def coef_penalite(codes: pd.Series, depts: pd.Series, penalites: pd.DataFrame, heure: float) -> pd.Series:
    """Coefficient multiplicatif du temps de trajet à l'heure donnée (max des règles applicables).

    zone : "ALL", "DEP:31" ou un code commune.
    """
    coef = pd.Series(1.0, index=codes.index)
    for row in penalites.itertuples(index=False):
        if not (float(row.heure_debut) <= heure < float(row.heure_fin)):
            continue
        zone = str(row.zone).strip()
        if zone.upper() == "ALL":
            mask = pd.Series(True, index=codes.index)
        elif zone.upper().startswith("DEP:"):
            mask = depts == zone.split(":", 1)[1].strip()
        else:
            mask = codes == zone
        coef = coef.where(~mask, np.maximum(coef, float(row.coef)))
    return coef


def add_temps_ajuste(df: pd.DataFrame, penalites: pd.DataFrame, heure: float) -> pd.DataFrame:
    out = df.copy()
    if "trajet_min" not in out.columns:
        return out
    out["coef_horaire"] = coef_penalite(out["code"], out["dept"], penalites, heure)
    out["trajet_ajuste_min"] = out["trajet_min"] * out["coef_horaire"]
    return out
