"""Aide au paramétrage : liste les colonnes d'un fichier et les valeurs d'une colonne.

python -m atlas_hympyr.etl.colonnes fichier.csv --cherche fioul autre
python -m atlas_hympyr.etl.colonnes fichier.csv --valeurs GENRE
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from atlas_hympyr.etl.tabular import ENCODINGS


def read_header(path: str | Path, sep: str) -> list[str]:
    for enc in ENCODINGS:
        try:
            return list(pd.read_csv(path, sep=sep, nrows=0, encoding=enc).columns)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Encodage illisible : {path}")


def find_columns(columns: list[str], keywords: list[str]) -> dict[str, list[str]]:
    """Pour chaque mot-clé, les colonnes dont le nom le contient (insensible à la casse)."""
    return {k: [c for c in columns if k.casefold() in c.casefold()] for k in keywords}


def distinct_values(
    path: str | Path, sep: str, column: str, limit: int = 50, chunksize: int = 500_000
) -> list[str]:
    seen: set[str] = set()
    for enc in ENCODINGS:
        try:
            for chunk in pd.read_csv(
                path, sep=sep, usecols=[column], dtype=str, encoding=enc, chunksize=chunksize
            ):
                seen.update(chunk[column].dropna().unique().tolist())
                if len(seen) > limit:
                    break
            break
        except UnicodeDecodeError:
            seen.clear()
            continue
    return sorted(seen)[: limit + 1]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("fichier")
    ap.add_argument("--sep", default=";")
    ap.add_argument("--cherche", nargs="*", default=[], help="mots-clés à repérer dans les colonnes")
    ap.add_argument("--valeurs", help="affiche les valeurs distinctes de cette colonne")
    args = ap.parse_args(argv)

    cols = read_header(args.fichier, args.sep)
    print(f"{len(cols)} colonnes dans {args.fichier}\n")
    if args.cherche:
        for k, found in find_columns(cols, args.cherche).items():
            print(f"« {k} » -> {found if found else 'aucune colonne'}")
        print("\nChoisir les colonnes à la main : ces correspondances sont indicatives.")
    else:
        for i, c in enumerate(cols):
            print(f"{i:>3}  {c}")
    if args.valeurs:
        vals = distinct_values(args.fichier, args.sep, args.valeurs)
        more = " (liste tronquée)" if len(vals) > 50 else ""
        print(f"\nValeurs de {args.valeurs}{more} :")
        for v in vals[:50]:
            print(f"  {v}")


if __name__ == "__main__":
    main()
