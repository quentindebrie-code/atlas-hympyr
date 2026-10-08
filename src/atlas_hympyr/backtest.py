"""Validation du potentiel estimé contre des ventes réelles agrégées par commune.

Entrée : un CSV anonymisé, une ligne par commune : code;volume (litres, tonnes... au choix, mais
cohérent). Aucune donnée client individuelle n'est nécessaire ni souhaitable.

    python -m atlas_hympyr.backtest ventes_fioul.csv --produit fioul
"""

from __future__ import annotations

import argparse
from typing import Any

import pandas as pd

from atlas_hympyr.config import load_settings, produits
from atlas_hympyr.data_access import load_atlas
from atlas_hympyr.scoring import add_potentiel


def evaluate_potential(
    atlas: pd.DataFrame, ventes: pd.DataFrame, produit: str, *, seuil_communes: float = 0.3
) -> dict[str, Any]:
    """Compare le potentiel estimé aux volumes réellement vendus.

    Retourne la corrélation de Spearman et la part du volume réel situé dans les
    `seuil_communes` (30 % par défaut) communes au plus fort potentiel estimé.
    """
    col = f"vol_{produit}"
    if col not in atlas.columns:
        raise ValueError(f"Potentiel indisponible pour « {produit} » dans l'atlas")
    if not {"code", "volume"} <= set(ventes.columns):
        raise ValueError("Le fichier de ventes doit contenir les colonnes : code, volume")
    v = ventes.copy()
    v["code"] = v["code"].astype(str).str.zfill(5)
    v["volume"] = pd.to_numeric(v["volume"], errors="coerce")
    merged = atlas[["code", col]].merge(v.groupby("code", as_index=False)["volume"].sum(), how="left")
    merged["volume"] = merged["volume"].fillna(0.0)
    unmatched = sorted(set(v["code"]) - set(atlas["code"]))
    total = float(merged["volume"].sum())
    if total <= 0 or merged[col].nunique() < 2:
        raise ValueError("Données insuffisantes pour évaluer (volume nul ou potentiel constant)")
    rho = float(merged[col].corr(merged["volume"], method="spearman"))
    top = merged.sort_values(col, ascending=False).head(max(1, int(len(merged) * seuil_communes)))
    return {
        "produit": produit,
        "n_communes": int(len(merged)),
        "spearman": round(rho, 3),
        "part_volume_reel_dans_top": round(float(top["volume"].sum() / total), 3),
        "seuil_communes": seuil_communes,
        "codes_ventes_inconnus": unmatched,
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ventes_csv")
    ap.add_argument("--produit", required=True)
    ap.add_argument("--sep", default=";")
    args = ap.parse_args(argv)
    cfg = load_settings()
    atlas = load_atlas()
    df = add_potentiel(atlas.communes, produits(cfg))
    ventes = pd.read_csv(args.ventes_csv, sep=args.sep, dtype={"code": str})
    res = evaluate_potential(df, ventes, args.produit)
    for k, v in res.items():
        print(f"{k}: {v}")
    print(
        "\nRepères indicatifs (proposition, à ajuster avec la direction) : Spearman > 0,5 et part "
        "du volume réel dans le top 30 % > 0,6 => le potentiel est un guide exploitable. "
        "En dessous, ne pas s'en servir pour décider avant recalibrage."
    )
    if atlas.meta.get("mode") == "demo":
        print("\nATTENTION : atlas en mode démonstration, ce résultat n'a aucune valeur.")


if __name__ == "__main__":
    main()
