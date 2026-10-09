"""Téléchargeur, altitude et chargeur Insee renforcé : tout est testé hors ligne."""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from atlas_hympyr.config import ConfigError
from atlas_hympyr.etl.altitude import load_altitude
from atlas_hympyr.etl.insee_logement import load_insee_logement
from atlas_hympyr.etl.telecharger import telecharger


class FakeResponse:
    def __init__(self, content: bytes, status: int = 200):
        self.content, self.status = content, status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    def iter_content(self, size):
        for i in range(0, len(self.content), size):
            yield self.content[i : i + size]


class FakeSession:
    def __init__(self, routes: dict[str, bytes]):
        self.routes, self.calls = routes, []

    def get(self, url, stream=True, timeout=0):
        self.calls.append(url)
        if url not in self.routes:
            return FakeResponse(b"", 404)
        return FakeResponse(self.routes[url])


def make_zip(members: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in members.items():
            zf.writestr(name, text)
    return buf.getvalue()


def cfg_for(tmp_path) -> dict:
    return {
        "sources": {
            "insee_logement": {"fichier": str(tmp_path / "insee.csv"), "url": "https://x/insee.zip"},
            "altitude": {"fichier": str(tmp_path / "alt.csv"), "url": "https://x/alt.csv"},
            "sdes_parc": {"fichier": str(tmp_path / "sdes.csv"), "url": "https://x/sdes.csv"},
        }
    }


def test_download_extracts_data_csv_not_meta(tmp_path):
    z = make_zip(
        {"meta_base-cc-logement-2022.CSV": "A;B\n", "base-cc-logement-2022.CSV": "CODGEO;P22_RP\n1;2\n"}
    )
    sess = FakeSession({"https://x/insee.zip": z})
    done = telecharger(cfg_for(tmp_path), ["insee"], session=sess, log=lambda *_: None)
    assert done == ["insee_logement"]
    assert (tmp_path / "insee.csv").read_text().startswith("CODGEO;P22_RP")
    assert not list(tmp_path.glob("*.part")) and not list(tmp_path.glob("*.zip"))


def test_download_skips_existing_unless_force(tmp_path):
    (tmp_path / "alt.csv").write_text("old")
    sess = FakeSession({"https://x/alt.csv": b"code_insee,altitude_moyenne\n"})
    assert telecharger(cfg_for(tmp_path), ["altitude"], session=sess, log=lambda *_: None) == []
    assert sess.calls == []
    assert telecharger(cfg_for(tmp_path), ["altitude"], force=True, session=sess, log=lambda *_: None)
    assert (tmp_path / "alt.csv").read_text().startswith("code_insee")


def test_download_rejects_html_error_page_and_http_failure(tmp_path):
    sess = FakeSession({"https://x/alt.csv": b"<!DOCTYPE html><html>acces refuse</html>"})
    with pytest.raises(RuntimeError, match="page web"):
        telecharger(cfg_for(tmp_path), ["altitude"], session=sess, log=lambda *_: None)
    assert not (tmp_path / "alt.csv").exists() and not list(tmp_path.glob("*.part"))
    with pytest.raises(RuntimeError, match="HTTP 404"):
        telecharger(cfg_for(tmp_path), ["sdes"], session=FakeSession({}), log=lambda *_: None)


def test_download_refuses_non_https_and_ambiguous_zip(tmp_path):
    cfg = cfg_for(tmp_path)
    cfg["sources"]["altitude"]["url"] = "http://x/alt.csv"
    with pytest.raises(ConfigError, match="HTTPS"):
        telecharger(cfg, ["altitude"], session=FakeSession({}), log=lambda *_: None)
    z = make_zip({"a.csv": "x\n", "b.csv": "y\n"})
    with pytest.raises(RuntimeError, match="un seul CSV"):
        telecharger(
            cfg_for(tmp_path), ["insee"], session=FakeSession({"https://x/insee.zip": z}), log=lambda *_: None
        )


def test_insee_loader_explains_missing_column(tmp_path):
    f = tmp_path / "i.csv"
    f.write_text("CODGEO;P23_RP;P23_RP_CFIOUL\n31555;10;2\n", encoding="utf-8")
    cfg = {"fichier": str(f), "colonnes": {"code": "CODGEO", "rp_fioul": "P22_RP_CFIOUL"}}
    with pytest.raises(ConfigError, match="P23_RP_CFIOUL"):
        load_insee_logement(cfg, ["31"])


def test_insee_loader_warns_on_missing_optional(tmp_path):
    f = tmp_path / "i.csv"
    f.write_text("CODGEO;P22_RP_CFIOUL\n31555;2\n", encoding="utf-8")
    cfg = {
        "fichier": str(f),
        "colonnes": {"code": "CODGEO", "rp_fioul": "P22_RP_CFIOUL", "rp_autre": "P22_RP_CAUT"},
    }
    with pytest.warns(UserWarning, match="P22_RP_CAUT"):
        df = load_insee_logement(cfg, ["31"])
    assert df["rp_autre"].isna().all() and df.loc[0, "rp_fioul"] == 2


def test_altitude_loader(tmp_path):
    f = tmp_path / "alt.csv"
    f.write_text("code_insee,nom,altitude_moyenne\n9001,A,640.4\n31555,T,150\n75056,P,35\n09002,B,\n")
    cfg = {
        "fichier": str(f),
        "separateur": ",",
        "colonnes": {"code": "code_insee", "altitude": "altitude_moyenne"},
    }
    df = load_altitude(cfg, ["09", "31"]).set_index("code")
    assert set(df.index) == {"09001", "09002", "31555"}
    assert df.loc["09001", "altitude_m"] == 640 and pd.isna(df.loc["09002", "altitude_m"])


def test_repo_config_sdes_matches_real_file_format(tmp_path):
    """La config livrée doit fonctionner sur un fichier au format réel relevé le 08/10/2026."""
    import yaml

    from atlas_hympyr.etl.sdes_parc import load_sdes_parc

    cfg = yaml.safe_load(open("config/settings.yaml", encoding="utf-8"))["sources"]["sdes_parc"]
    header = "COMMUNE_CODE;COMMUNE_NOM;CARBURANT;CRIT_AIR;STATUT_UTILISATEUR;GROUPE;CATEGORIE;" + ";".join(
        f"PARC_{y}" for y in range(2011, 2027)
    )

    def row(code, carb, crit, statut, groupe, cat, n):
        return f"{code};X;{carb};{crit};{statut};{groupe};{cat};" + ";".join([str(n)] * 16)

    rows = [
        row("31555", "Diesel", "Crit'Air 2", "Professionel", "PL", "CAMION", 10),
        row("31555", "Diesel", "Crit'Air 4", "Professionel", "PL", "CAMION", 3),
        row("31555", "Essence", "Crit'Air 1", "Professionel", "PL", "CAMION", 99),  # exclu : pas diesel
        row("31555", "Diesel", "Crit'Air 2", "Particulier", "VP", "VP", 500),  # exclu : voiture
        row("09001", "Diesel HR", "Crit'Air 3", "Professionel", "PL", "AUTREPL", 2),
        row("75056", "Diesel", "Crit'Air 2", "Professionel", "PL", "CAMION", 7),  # hors périmètre
    ]
    f = tmp_path / "sdes.csv"
    f.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    cfg["fichier"] = str(f)
    df, stats = load_sdes_parc(cfg, ["09", "31"])
    out = df.set_index("code")
    assert out.loc["31555", "pl_entreprises"] == 13 and out.loc["31555", "pl_diesel_recents"] == 10
    assert out.loc["09001", "pl_entreprises"] == 2 and out.loc["09001", "pl_diesel_recents"] == 2
    assert "75056" not in out.index


def test_geocode_and_resolve_depots():
    from atlas_hympyr.etl.geocodage import resolve_depots

    calls = []

    def fake(url, params):
        calls.append(url)
        if "geopf" in url and "introuvable" in params["q"]:
            return {"features": []}
        score = 0.2 if "flou" in params["q"] else 0.93
        return {
            "features": [
                {
                    "geometry": {"type": "Point", "coordinates": [1.5, 43.8]},
                    "properties": {"label": params["q"].upper(), "score": score},
                }
            ]
        }

    logs: list[str] = []
    deps = resolve_depots(
        [{"nom": "Dépôt Été", "adresse": "1 rue A"}, {"id": "x", "nom": "Fixe", "lat": 43.0, "lon": 1.0}],
        fake,
        logs.append,
    )
    assert deps[0]["id"] == "depot-ete" and deps[0]["lat"] == 43.8 and deps[0]["lon"] == 1.5
    assert deps[1]["lat"] == 43.0 and len(calls) == 1 and "score 0.93" in logs[0]
    # repli sur le second service quand le premier ne trouve rien
    deps = resolve_depots([{"nom": "B", "adresse": "introuvable ici"}], fake, logs.append)
    assert deps[0]["lat"] == 43.8 and calls[-1].startswith("https://api-adresse")
    with pytest.raises(ConfigError, match="score"):
        resolve_depots([{"nom": "C", "adresse": "flou"}], fake, logs.append)
    with pytest.raises(ConfigError, match="double"):
        resolve_depots([{"id": "a", "lat": 1, "lon": 1}, {"id": "a", "lat": 2, "lon": 2}], fake)
    with pytest.raises(ConfigError, match="adresse"):
        resolve_depots([{"nom": "D"}], fake)


def test_assemble_absence_means_zero_for_sdes():
    from atlas_hympyr.etl.build import assemble

    communes = pd.DataFrame({"code": ["31001", "31002", "31003", "31004"]})
    sdes = pd.DataFrame({"code": ["31001", "31002"], "pl_entreprises": [5.0, 2.0]})
    insee = pd.DataFrame({"code": ["31001"], "rp_fioul": [9.0]})
    out, rep = assemble(communes, {"sdes": sdes, "insee": insee}, zero_si_absent={"sdes"})
    out = out.set_index("code")
    assert out.loc["31004", "pl_entreprises"] == 0.0  # absent du parc = aucun poids lourd
    assert pd.isna(out.loc["31002", "rp_fioul"])  # Insee : absent = inconnu, pas zéro
    assert rep["sdes"]["alerte"] is False and rep["sdes"]["absence_vaut_zero"] is True
    assert rep["insee"]["alerte"] is True  # 25 % de couverture seulement
    # codes de la source inconnus de la liste des communes : vrai signal d'alerte
    bad = pd.DataFrame({"code": ["99001", "99002", "31001"], "pl_entreprises": [1.0, 1.0, 1.0]})
    _, rep = assemble(communes, {"sdes": bad}, zero_si_absent={"sdes"})
    assert rep["sdes"]["alerte"] is True
