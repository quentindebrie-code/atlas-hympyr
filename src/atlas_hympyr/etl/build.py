"""Construction de l'atlas réel.

    pip install -e ".[etl]"
    python -m atlas_hympyr.etl.build                 # toutes les étapes
    python -m atlas_hympyr.etl.build --ignorer rpg   # sans le RPG
    python -m atlas_hympyr.etl.build --strict        # échoue à la première étape non configurée

Étapes : communes (réseau) -> insee -> sdes -> rpg -> trafic (optionnel) -> altitude -> trajets par dépôt.
Une étape non configurée ou dont le fichier est absent est ignorée (le produit correspondant sera
simplement indisponible dans l'application), sauf avec --strict. Un rapport de couverture est écrit
dans meta.json et affiché.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from atlas_hympyr.config import ConfigError, get, load_settings
from atlas_hympyr.data_access import Atlas, save_atlas
from atlas_hympyr.etl.tabular import normalize_code, read_csv_flexible, to_number
from atlas_hympyr.paths import PROCESSED_DIR, ROOT

SEUIL_COUVERTURE = 0.95


def assemble(
    communes: pd.DataFrame, parts: dict[str, pd.DataFrame]
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Fusionne les sources sur le code commune et mesure la couverture de chacune.

    Un faible taux de correspondance trahit presque toujours un problème de millésime des codes
    (fusions de communes) ou de zéros de tête perdus : il est signalé, pas masqué.
    """
    out = communes.copy()
    report: dict[str, dict[str, Any]] = {}
    codes = set(out["code"])
    for name, part in parts.items():
        src_codes = set(part["code"])
        matched = len(codes & src_codes)
        report[name] = {
            "communes_couvertes": matched,
            "taux_couverture": round(matched / len(codes), 4) if codes else 0.0,
            "codes_source_inconnus": len(src_codes - codes),
            "exemples_inconnus": sorted(src_codes - codes)[:10],
            "alerte": bool(codes) and matched / len(codes) < SEUIL_COUVERTURE,
        }
        new_cols = [c for c in part.columns if c == "code" or c not in out.columns]
        out = out.merge(part[new_cols], on="code", how="left")
    return out, report


def _load_trafic(cfg_source: dict[str, Any], departements: list[str]) -> pd.DataFrame:
    path = Path(cfg_source["fichier"])
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"{path} absent (étape optionnelle)")
    raw = read_csv_flexible(path, ";")
    if not {"code", "tmja"} <= set(raw.columns):
        raise ConfigError(f"{path} : colonnes attendues « code » et « tmja »")
    df = pd.DataFrame({"code": normalize_code(raw["code"]), "tmja": to_number(raw["tmja"])})
    df = df[df["code"].str[:2].isin(departements)]
    tmax = df["tmja"].max()
    df["trafic_idx"] = (100 * df["tmja"] / tmax).round(1) if tmax and tmax > 0 else float("nan")
    return df[["code", "trafic_idx"]]


def _abs(cfg_source: dict[str, Any]) -> dict[str, Any]:
    out = dict(cfg_source)
    if not out.get("fichier"):
        raise ConfigError("Source non configurée (clé « fichier » absente dans config/settings.yaml)")
    p = Path(out["fichier"])
    out["fichier"] = str(p if p.is_absolute() else ROOT / p)
    return out


def build(
    cfg: dict[str, Any],
    out_dir: Path,
    ignorer: set[str] | None = None,
    strict: bool = False,
    log=print,
    get_json=None,
) -> Atlas:
    from atlas_hympyr.etl.communes import build_communes
    from atlas_hympyr.etl.routing import EstimationProvider, OSRMProvider

    ignorer = ignorer or set()
    deps = list(get(cfg, "perimetre.departements", []))
    if not deps:
        raise ConfigError("perimetre.departements est vide")

    log(f"[communes] téléchargement des contours ({', '.join(deps)})")
    communes, geojson = build_communes(
        deps,
        get(cfg, "geo.api_communes"),
        float(get(cfg, "geo.simplification_deg", 0.0005)),
        get_json,
    )
    log(f"[communes] {len(communes)} communes")

    parts: dict[str, pd.DataFrame] = {}
    sources_meta: dict[str, Any] = {}

    def stage(name: str, fn) -> None:
        if name in ignorer:
            log(f"[{name}] ignoré (demande utilisateur)")
            return
        try:
            result = fn()
        except (ConfigError, FileNotFoundError) as exc:
            if strict:
                raise
            log(f"[{name}] IGNORÉ : {exc}")
            return
        parts[name] = result
        log(f"[{name}] {len(result)} communes renseignées")

    def insee() -> pd.DataFrame:
        from atlas_hympyr.etl.insee_logement import load_insee_logement

        src = _abs(get(cfg, "sources.insee_logement", {}))
        df = load_insee_logement(src, deps)
        sources_meta["insee_logement"] = {"millesime": src.get("millesime")}
        return df

    def sdes() -> pd.DataFrame:
        from atlas_hympyr.etl.sdes_parc import load_sdes_parc

        src = _abs(get(cfg, "sources.sdes_parc", {}))
        df, stats = load_sdes_parc(src, deps)
        sources_meta["sdes_parc"] = {"millesime": src.get("millesime"), **stats}
        return df

    def rpg() -> pd.DataFrame:
        from atlas_hympyr.etl.rpg import load_rpg

        src = _abs(get(cfg, "sources.rpg", {}))
        sources_meta["rpg"] = {"fichier": Path(src["fichier"]).name}
        return load_rpg(src, geojson)

    def altitude() -> pd.DataFrame:
        from atlas_hympyr.etl.altitude import load_altitude

        src = _abs(get(cfg, "sources.altitude", {}))
        sources_meta["altitude"] = {"fichier": Path(src["fichier"]).name}
        return load_altitude(src, deps)

    def trafic() -> pd.DataFrame:
        sources_meta["trafic"] = {}
        return _load_trafic(get(cfg, "sources.trafic", {"fichier": "data/raw/trafic_communes.csv"}), deps)

    stage("insee", insee)
    stage("sdes", sdes)
    stage("rpg", rpg)
    stage("trafic", trafic)
    # L'altitude du fichier communal sert de repli ; un MNT configuré la remplace plus bas.
    if not get(cfg, "routage.mnt_geotiff"):
        stage("altitude", altitude)
    table, report = assemble(communes, parts)

    # Altitude de la commune (MNT) si disponible
    dem = None
    mnt = get(cfg, "routage.mnt_geotiff")
    if mnt and "mnt" not in ignorer:
        from atlas_hympyr.etl.dem import DemSampler

        dem = DemSampler(str(ROOT / mnt) if not Path(mnt).is_absolute() else mnt)
        table["altitude_m"] = dem.sample(table["lon"], table["lat"]).round(0)
        log("[mnt] altitude des communes échantillonnée")

    from atlas_hympyr.etl.geocodage import resolve_depots

    depots = resolve_depots(list(get(cfg, "depots", []) or []), get_json, log)
    routes: dict[str, pd.DataFrame] = {}
    if not depots:
        log("[trajets] IGNORÉ : aucun dépôt dans config/settings.yaml (clé « depots »)")
        if strict:
            raise ConfigError("Aucun dépôt configuré")
    else:
        fournisseur = get(cfg, "routage.fournisseur", "estimation")
        coef_pl = float(get(cfg, "routage.coef_temps_poids_lourd", 1.0))
        if fournisseur == "osrm":
            provider = OSRMProvider(
                get(cfg, "routage.osrm.url"),
                get(cfg, "routage.osrm.profil", "driving"),
                float(get(cfg, "routage.osrm.timeout_s", 20)),
                coef_pl,
                dem,
            )
        else:
            provider = EstimationProvider(
                float(get(cfg, "routage.estimation.vitesse_moyenne_kmh", 55)),
                float(get(cfg, "routage.estimation.coef_detour", 1.3)),
                coef_pl,
            )
        for d in depots:
            log(f"[trajets] {d['id']} ({fournisseur})")
            routes[d["id"]] = provider.metrics(d, table)

    meta = {
        "mode": "reel",
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "routage": get(cfg, "routage.fournisseur", "estimation"),
        "coef_temps_poids_lourd": get(cfg, "routage.coef_temps_poids_lourd", 1.0),
        "sources": sources_meta,
        "couverture": report,
    }
    atlas = Atlas(table, geojson, routes, depots, meta)
    save_atlas(atlas, out_dir)
    log(f"Atlas écrit dans {out_dir}")
    for name, r in report.items():
        flag = "  <-- COUVERTURE INSUFFISANTE" if r["alerte"] else ""
        log(f"  {name}: {r['taux_couverture']:.1%} des communes{flag}")
    if dem is not None:
        dem.close()
    return atlas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=str(PROCESSED_DIR))
    ap.add_argument(
        "--ignorer", nargs="*", default=[], choices=["insee", "sdes", "rpg", "trafic", "altitude", "mnt"]
    )
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    try:
        build(load_settings(args.config), Path(args.out), set(args.ignorer), args.strict)
    except (ConfigError, FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
