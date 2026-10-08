"""Chargement de la configuration YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from atlas_hympyr.paths import CONFIG_FILE


class ConfigError(ValueError):
    """Configuration absente ou incomplète (message destiné à l'utilisateur)."""


def load_settings(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else CONFIG_FILE
    if not p.exists():
        raise ConfigError(f"Fichier de configuration introuvable : {p}")
    with p.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    if not isinstance(cfg, dict):
        raise ConfigError(f"Configuration invalide (un dictionnaire YAML est attendu) : {p}")
    return cfg


def get(cfg: dict[str, Any], dotted: str, default: Any = None) -> Any:
    """Lecture d'une clé imbriquée : get(cfg, "scoring.poids_priorite.potentiel")."""
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur if cur is not None else default


def require(cfg: dict[str, Any], dotted: str, why: str) -> Any:
    """Comme get(), mais lève une erreur explicite si la valeur n'est pas renseignée."""
    value = get(cfg, dotted)
    if value in (None, "", []):
        raise ConfigError(f"Paramètre « {dotted} » non renseigné dans config/settings.yaml ({why}).")
    return value


def produits(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return dict(get(cfg, "produits", {}) or {})
