"""Aide à la décision : liste de communes à cibler pour un produit."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from atlas_hympyr.app import ui
from atlas_hympyr.app.state import (
    enriched,
    get_atlas,
    libelle,
    poids_priorite,
    produits_cfg,
)
from atlas_hympyr.scoring import (
    add_priorite,
    concentration_curve,
    produits_disponibles,
    select_targets,
)


def render() -> None:
    atlas = get_atlas()
    ui.banner(atlas)
    st.header("Ciblage : quelles communes viser en priorité ?")
    depot = ui.depot_selector(atlas, "cib_depot")
    df = enriched(depot, None)
    dispo = produits_disponibles(df, produits_cfg())
    if not dispo:
        st.warning("Aucun produit n'a de données de potentiel. Voir le README (données réelles).")
        return

    produit = st.sidebar.selectbox("Produit", dispo, format_func=libelle, key="cib_produit")
    avert = produits_cfg()[produit].get("avertissement")
    if avert:
        st.warning(f"Fiabilité {produits_cfg()[produit].get('fiabilite', 'à vérifier')} — {avert}")
    defaut = poids_priorite()
    st.sidebar.markdown("**Poids de la priorité**")
    w_pot = st.sidebar.slider("Potentiel", 0.0, 1.0, float(defaut.get("potentiel", 0.5)), 0.05, key="cib_wp")
    w_den = st.sidebar.slider(
        "Densité de demande", 0.0, 1.0, float(defaut.get("densite", 0.2)), 0.05, key="cib_wd"
    )
    has_diff = "difficulte" in df and df["difficulte"].notna().any()
    w_fac = (
        st.sidebar.slider(
            "Facilité d'accès", 0.0, 1.0, float(defaut.get("facilite", 0.3)), 0.05, key="cib_wf"
        )
        if has_diff
        else 0.0
    )
    if w_pot + w_den + w_fac == 0:
        st.warning("Au moins un poids doit être supérieur à zéro.")
        return

    depts = sorted(df["dept"].unique())
    sel = st.sidebar.multiselect("Départements", depts, default=depts, key="cib_depts")
    pot_min = st.sidebar.slider("Potentiel minimum (0-100)", 0, 100, 40, key="cib_potmin")
    diff_max = (
        st.sidebar.slider("Difficulté maximum (0-100)", 0, 100, 100, key="cib_diffmax") if has_diff else 100
    )
    n = st.sidebar.number_input("Nombre de communes", 5, 500, 50, 5, key="cib_n")

    d = add_priorite(df, produit, {"potentiel": w_pot, "densite": w_den, "facilite": w_fac})
    cibles = select_targets(
        d,
        produit,
        int(n),
        departements=sel or None,
        potentiel_min=float(pot_min),
        difficulte_max=float(diff_max),
    )

    vol = f"vol_{produit}"
    total = float(d[vol].sum())
    couvert = float(cibles[vol].sum())
    k1, k2, k3 = st.columns(3)
    k1.metric("Communes retenues", ui.fmt_int(len(cibles)))
    k2.metric("Part des communes du territoire", f"{len(cibles) / len(d):.1%}")
    k3.metric("Part du volume estimé couvert", f"{couvert / total:.1%}" if total > 0 else "n.d.")

    if cibles.empty:
        st.info("Aucune commune ne satisfait ces filtres : les assouplir.")
        return

    st.caption(
        f"{libelle(produit)} · priorité = {w_pot:.2f} x potentiel + {w_den:.2f} x densité"
        + (f" + {w_fac:.2f} x facilité d'accès" if has_diff else "")
        + " (normalisée)."
    )

    d_map = d.assign(cible=d["code"].isin(cibles["code"]).map({True: "Cible", False: "Autre"}))
    d_map[f"priorite_{produit}"] = d_map[f"priorite_{produit}"].where(d_map["cible"] == "Cible")
    fig = ui.carte(
        d_map[d_map["cible"] == "Cible"],
        atlas.geojson,
        f"priorite_{produit}",
        "Priorité",
        ui.BLEUS,
        {"dept": "", vol: ":,.0f", f"pot_{produit}": ":.0f", "difficulte": ":.0f"},
        hauteur=520,
    )
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Liste des communes à cibler")
        cols = ["nom", "dept", vol, f"pot_{produit}", "difficulte", f"priorite_{produit}"]
        st.dataframe(
            cibles[[c for c in cols if c in cibles]],
            hide_index=True,
            width="stretch",
            column_config={
                "nom": "Commune",
                "dept": "Dép.",
                vol: ui.num_column("Volume estimé"),
                f"pot_{produit}": ui.score_column("Potentiel"),
                "difficulte": ui.score_column("Difficulté"),
                f"priorite_{produit}": ui.score_column("Priorité"),
            },
        )
    with c2:
        st.subheader("Concentration de la demande")
        courbe = concentration_curve(d[vol])
        fc = go.Figure()
        fc.add_trace(
            go.Scatter(
                x=courbe["part_communes"] * 100,
                y=courbe["part_volume"] * 100,
                mode="lines",
                line={"color": ui.BLEUS[4], "width": 2},
                name="Communes triées par volume",
                hovertemplate="%{x:.0f} % des communes = %{y:.0f} % du volume<extra></extra>",
            )
        )
        fc.add_trace(
            go.Scatter(
                x=[len(cibles) / len(d) * 100],
                y=[couvert / total * 100 if total else 0],
                mode="markers",
                marker={"color": ui.ORANGES[3], "size": 11, "line": {"color": "white", "width": 2}},
                name="Sélection actuelle",
                hovertemplate="Sélection : %{x:.1f} % des communes, %{y:.0f} % du volume<extra></extra>",
            )
        )
        fc.update_layout(
            height=360,
            margin={"l": 0, "r": 0, "t": 10, "b": 0},
            xaxis_title="% des communes",
            yaxis_title="% du volume estimé cumulé",
            legend={"orientation": "h", "y": -0.3},
        )
        st.plotly_chart(fc, width="stretch")
        st.caption(
            "Plus la courbe est bombée, plus quelques communes concentrent la demande : "
            "le ciblage y gagne en efficacité."
        )

    export = cibles[["code", "nom", "dept", vol, f"pot_{produit}", f"priorite_{produit}"]]
    st.download_button(
        "Exporter la liste (CSV)",
        ui.csv_bytes(export),
        file_name=f"cibles_{produit}.csv",
        mime="text/csv",
        key="cib_export",
    )
    ui.methodo_note(
        "Le ciblage classe les communes selon vos poids. Pour une **campagne publicitaire "
        "géociblée**, convertir les codes INSEE en codes postaux avec une table de correspondance "
        "ouverte (non incluse). Ce classement guide un choix : il ne prédit ni le chiffre "
        "d'affaires ni le taux de conversion. Mesurer les résultats de la campagne par zone pour "
        "recalibrer."
    )
