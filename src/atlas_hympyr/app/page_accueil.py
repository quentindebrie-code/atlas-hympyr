"""Synthèse : état des données et premières priorités par produit."""

from __future__ import annotations

import streamlit as st

from atlas_hympyr.app import ui
from atlas_hympyr.app.state import (
    enriched,
    get_atlas,
    libelle,
    poids_priorite,
    produits_cfg,
)
from atlas_hympyr.scoring import add_priorite, produits_disponibles


def render() -> None:
    atlas = get_atlas()
    ui.banner(atlas)
    st.title("Atlas territorial Hympyr")
    st.markdown(
        "**Où se trouve la demande, et à quel effort peut-on la livrer ?** L'atlas croise, par "
        "commune, un *potentiel* par produit (données officielles) et une *difficulté d'accès* "
        "depuis le dépôt (relief, sinuosité, temps de trajet). Il sert à trois décisions : "
        "**cibler** (commercial), **planifier** (exploitation), **arbitrer** (direction)."
    )

    depot = ui.depot_selector(atlas, "accueil_depot")
    df = enriched(depot, None)
    dispo = produits_disponibles(df, produits_cfg())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Communes", ui.fmt_int(len(df)))
    c2.metric("Population", ui.fmt_int(df["population"].sum()) if "population" in df else "n.d.")
    c3.metric("Produits renseignés", f"{len(dispo)} / {len(produits_cfg())}")
    comp = df["difficulte_completude"].mean() if "difficulte_completude" in df else 0.0
    c4.metric("Complétude de la difficulté", f"{comp:.0%}")

    if not dispo:
        st.warning(
            "Aucun indicateur de potentiel n'est renseigné. Construire les données réelles "
            "(`python -m atlas_hympyr.etl.build`) après avoir complété config/settings.yaml."
        )
        return

    st.subheader("Communes prioritaires par produit")
    st.caption(
        "Priorité = potentiel, densité de demande et facilité d'accès (poids par défaut de la "
        "configuration, réglables dans la page Ciblage)."
    )
    tabs = st.tabs([libelle(k) for k in dispo])
    for tab, key in zip(tabs, dispo, strict=True):
        with tab:
            d = add_priorite(df, key, poids_priorite())
            top = d.sort_values(f"priorite_{key}", ascending=False).head(10)
            cols = ["nom", "dept", f"vol_{key}", f"pot_{key}", "difficulte", f"priorite_{key}"]
            cols = [c for c in cols if c in top]
            st.dataframe(
                top[cols],
                hide_index=True,
                width="stretch",
                column_config={
                    "nom": "Commune",
                    "dept": "Dép.",
                    f"vol_{key}": ui.num_column("Volume estimé"),
                    f"pot_{key}": ui.score_column("Potentiel"),
                    "difficulte": ui.score_column("Difficulté d'accès"),
                    f"priorite_{key}": ui.score_column("Priorité"),
                },
            )
            unite = produits_cfg()[key].get("unite", "")
            st.caption(f"Volume estimé = {unite}. Segment : {produits_cfg()[key].get('segment', '')}.")

    ui.methodo_note(
        "- **Potentiel** : rang (0-100) du volume estimé par commune, sur le territoire.\n"
        "- **Difficulté d'accès** : 0 = facile, 100 = très difficile (rang composite).\n"
        "- Ce sont des **proxies** issus de données ouvertes, pas des ventes réelles. "
        "Détails dans la page Méthodologie."
    )
