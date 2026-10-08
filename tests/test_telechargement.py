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
