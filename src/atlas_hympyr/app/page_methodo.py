"""Méthodologie, sources et qualité des données."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from atlas_hympyr.app import ui
from atlas_hympyr.app.state import get_atlas, poids_difficulte, poids_priorite
from atlas_hympyr.paths import DOCS_DIR


def render() -> None:
    atlas = get_atlas()
    ui.banner(atlas)
    st.header("Méthodologie et qualité des données")

    st.subheader("Qualité des données")
    couv = atlas.meta.get("couverture")
    if couv:
        rows = [
            {
                "Source": nom,
                "Communes couvertes": r["communes_couvertes"],
                "Couverture": r["taux_couverture"] * 100,
                "Codes source inconnus": r["codes_source_inconnus"],
                "Alerte": "OUI" if r["alerte"] else "non",
            }
            for nom, r in couv.items()
        ]
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            width="stretch",
            column_config={"Couverture": st.column_config.NumberColumn("Couverture (%)", format="%.1f")},
        )
        st.caption(
            "Une couverture < 95 % signale souvent un problème de millésime des codes communes "
            "(fusions) ou de zéros de tête : corriger avant de s'en servir."
        )
    else:
        st.info("Mode démonstration : pas de contrôle de couverture (données synthétiques).")

    st.subheader("Paramètres de calcul actifs")
    c1, c2 = st.columns(2)
    c1.markdown("**Poids de la difficulté d'accès**")
    c1.json(poids_difficulte())
    c2.markdown("**Poids de priorité par défaut**")
    c2.json(poids_priorite())
    st.caption(
        f"Routage : {atlas.meta.get('routage', 'n.d.')} · "
        f"sources : {', '.join(atlas.meta.get('sources', {}) or ['aucune (démo)'])}"
    )

    doc = DOCS_DIR / "METHODOLOGIE.md"
    if doc.exists():
        st.divider()
        st.markdown(doc.read_text(encoding="utf-8"))
    else:
        st.info("docs/METHODOLOGIE.md introuvable : voir le dépôt.")
