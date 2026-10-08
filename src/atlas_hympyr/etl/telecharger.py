"""Téléchargement des fichiers sources ouverts dans data/raw/ (à lancer avec accès à Internet).

    python -m atlas_hympyr.etl.telecharger                      # insee + altitude + sdes
    python -m atlas_hympyr.etl.telecharger --seulement insee    # un seul fichier
    python -m atlas_hympyr.etl.telecharger --force              # écrase les fichiers existants

Les URL sont lues dans config/settings.yaml (sources.<nom>.url). Aucun identifiant n'est requis.
Le RPG n'est pas téléchargé ici : l'URL officielle n'a pas pu être vérifiée (voir docs/SOURCES.md).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

from atlas_hympyr.config import ConfigError, get, load_settings
from atlas_hympyr.paths import ROOT

SOURCES = ("insee_logement", "altitude", "sdes_parc")
ALIAS = {"insee": "insee_logement", "sdes": "sdes_parc", "altitude": "altitude"}
MAX_CSV_BYTES = 2 * 1024**3  # garde-fou contre une archive piégée (ZIP bomb)
CHUNK = 1024 * 1024


def _target(cfg_source: dict[str, Any]) -> Path:
    p = Path(cfg_source["fichier"])
    return p if p.is_absolute() else ROOT / p


def _looks_like_html(first_bytes: bytes) -> bool:
    head = first_bytes.lstrip()[:15].lower()
    return head.startswith((b"<!doctype", b"<html", b"<?xml"))


def _stream_to(session: Any, url: str, dest: Path, log) -> None:
    """Télécharge url vers dest via un fichier .part (pas de fichier tronqué en cas d'échec)."""
    if not url.startswith("https://"):
        raise ConfigError(f"URL non HTTPS refusée : {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    total = 0
    try:
        with session.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(part, "wb") as fh:
                for chunk in r.iter_content(CHUNK):
                    if total == 0 and _looks_like_html(chunk):
                        raise RuntimeError(f"{url} a renvoyé une page web au lieu d'un fichier de données")
                    fh.write(chunk)
                    total += len(chunk)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    if total == 0:
        part.unlink(missing_ok=True)
        raise RuntimeError(f"{url} : réponse vide")
    part.replace(dest)
    log(f"  {dest.name} : {total / 1e6:.1f} Mo")


def _extract_csv(zip_path: Path, dest: Path) -> str:
    """Extrait le CSV de données (pas le fichier « meta_ ») sous le nom dest, sans extractall."""
    with zipfile.ZipFile(zip_path) as zf:
        candidates = [
            i
            for i in zf.infolist()
            if i.filename.lower().endswith(".csv") and not Path(i.filename).name.lower().startswith("meta")
        ]
        if len(candidates) != 1:
            names = [i.filename for i in zf.infolist()]
            raise RuntimeError(f"{zip_path.name} : un seul CSV de données attendu, contenu : {names}")
        info = candidates[0]
        if info.file_size > MAX_CSV_BYTES:
            raise RuntimeError(f"{info.filename} : taille décompressée suspecte ({info.file_size} octets)")
        part = dest.with_name(dest.name + ".part")
        with zf.open(info) as src, open(part, "wb") as out:
            shutil.copyfileobj(src, out, CHUNK)
        part.replace(dest)
        return info.filename


def telecharger(
    cfg: dict[str, Any], seulement: list[str] | None = None, force: bool = False, session=None, log=print
) -> list[str]:
    """Retourne la liste des sources effectivement téléchargées."""
    if session is None:
        import requests  # extra « etl »

        session = requests.Session()
        session.headers["User-Agent"] = "atlas-hympyr (telechargement donnees ouvertes)"
    names = [ALIAS.get(n, n) for n in seulement] if seulement else list(SOURCES)
    done: list[str] = []
    for name in names:
        if name not in SOURCES:
            raise ConfigError(f"Source inconnue : {name}. Choix : {sorted(ALIAS)}")
        src = get(cfg, f"sources.{name}", {}) or {}
        url, fichier = src.get("url"), src.get("fichier")
        if not url or not fichier:
            log(f"[{name}] IGNORÉ : sources.{name}.url / .fichier absents de la configuration")
            continue
        dest = _target(src)
        if dest.exists() and not force:
            log(f"[{name}] déjà présent ({dest.name}), --force pour le retélécharger")
            continue
        log(f"[{name}] {url}")
        if url.lower().split("?")[0].endswith(".zip"):
            zpath = dest.with_name(dest.name + ".zip")
            try:
                _stream_to(session, url, zpath, log)
                inner = _extract_csv(zpath, dest)
            finally:
                zpath.unlink(missing_ok=True)
            log(f"  extrait : {inner} -> {dest.name}")
        else:
            _stream_to(session, url, dest, log)
        done.append(name)
    return done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--seulement", nargs="*", choices=sorted(ALIAS), default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    try:
        done = telecharger(load_settings(args.config), args.seulement, args.force)
    except Exception as exc:  # noqa: BLE001 - message lisible plutôt que trace réseau
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    print(f"Terminé : {done or 'rien à télécharger'}")
    print("Étape suivante : renseigner sources.sdes_parc (voir colonnes.py), puis `make donnees`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
