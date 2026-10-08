"""Point d'entrée Streamlit : navigation entre les vues."""

from __future__ import annotations

import streamlit as st

from atlas_hympyr.app import (
    page_accueil,
    page_ciblage,
    page_commercial,
    page_exploitation,
    page_fiche,
    page_methodo,
)


def run() -> None:
    st.set_page_config(page_title="Atlas Hympyr", layout="wide", initial_sidebar_state="expanded")
    pages = [
        st.Page(page_accueil.render, title="Synthèse", url_path="synthese", default=True),
        st.Page(page_commercial.render, title="Vue commerciale", url_path="commercial"),
        st.Page(page_exploitation.render, title="Vue exploitation", url_path="exploitation"),
        st.Page(page_ciblage.render, title="Ciblage", url_path="ciblage"),
        st.Page(page_fiche.render, title="Fiche commune", url_path="commune"),
        st.Page(page_methodo.render, title="Méthodologie", url_path="methodologie"),
    ]
    st.navigation(pages).run()
