"""Pruebas: los datos de un bebé nunca se mezclan con los de otro. Correr con: pytest"""
import os
import sqlite3
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_app(tmp_path, monkeypatch):
    monkeypatch.setenv("TETI_DB", str(tmp_path / "t.db"))
    for m in ("db", "main", "ratelimit"):
        sys.modules.pop(m, None)
    import main
    return TestClient(main.app)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    return load_app(tmp_path, monkeypatch)


def new_baby(c, name="X"):
    r = c.post("/api/babies", json={"name": name})
    assert r.status_code == 201
    return r.json()["code"]


H = lambda code: {"X-Baby-Code": code}
TOMA = {"id": "t1", "date": "2026-11-18", "type": "formula", "start": "10:00", "ml": 90}


def test_sin_codigo_o_con_codigo_invalido_no_hay_acceso(client):
    assert client.get("/api/feedings").status_code == 401
    assert client.get("/api/feedings", headers=H("AAAA-BBBB-CCCC-DDDD")).status_code == 401
    assert client.post("/api/feedings", json=TOMA).status_code == 401


def test_cada_bebe_ve_solo_lo_suyo(client):
    a, b = new_baby(client, "A"), new_baby(client, "B")
    assert client.post("/api/feedings", json=TOMA, headers=H(a)).status_code == 201
    assert len(client.get("/api/feedings", headers=H(a)).json()) == 1
    assert client.get("/api/feedings", headers=H(b)).json() == []


def test_no_se_pueden_editar_ni_borrar_tomas_ajenas(client):
    a, b = new_baby(client, "A"), new_baby(client, "B")
    client.post("/api/feedings", json=TOMA, headers=H(a))
    r = client.put("/api/feedings/t1", json={**TOMA, "ml": 1}, headers=H(b))
    assert r.status_code == 404
    client.delete("/api/feedings/t1", headers=H(b))
    assert client.get("/api/feedings", headers=H(a)).json()[0]["ml"] == 90


def test_el_mismo_id_en_dos_bebes_no_choca(client):
    a, b = new_baby(client, "A"), new_baby(client, "B")
    assert client.post("/api/feedings", json=TOMA, headers=H(a)).status_code == 201
    assert client.post("/api/feedings", json=TOMA, headers=H(b)).status_code == 201
    assert client.post("/api/feedings", json=TOMA, headers=H(a)).status_code == 409


def test_importar_va_solo_al_bebe_indicado(client):
    a, b = new_baby(client, "A"), new_baby(client, "B")
    client.post("/api/feedings/bulk", json=[TOMA], headers=H(a))
    assert client.get("/api/feedings", headers=H(b)).json() == []
    assert len(client.get("/api/feedings", headers=H(a)).json()) == 1


def test_el_codigo_tolera_minusculas_y_sin_guiones(client):
    a = new_baby(client, "A")
    assert client.get("/api/baby", headers=H(a.lower().replace("-", ""))).json()["name"] == "A"


def test_migracion_de_la_base_anterior(tmp_path, monkeypatch):
    con = sqlite3.connect(tmp_path / "t.db")
    con.execute("CREATE TABLE feedings (id TEXT PRIMARY KEY, date TEXT NOT NULL, type TEXT NOT NULL, "
                "start TEXT NOT NULL, end TEXT, ml INTEGER, laps TEXT)")
    con.execute("INSERT INTO feedings VALUES ('v1','2026-11-17','teti','23:50','00:20',NULL,'[600,1200]')")
    con.execute("INSERT INTO feedings VALUES ('v2','2026-11-17','formula','21:00',NULL,80,NULL)")
    con.commit(); con.close()
    client = load_app(tmp_path, monkeypatch)
    code = sqlite3.connect(tmp_path / "t.db").execute("SELECT code FROM babies").fetchone()[0]
    rows = client.get("/api/feedings", headers=H(code)).json()
    assert {r["id"] for r in rows} == {"v1", "v2"}
    assert next(r for r in rows if r["id"] == "v1")["laps"] == [600, 1200]
    assert client.get("/api/feedings", headers=H(new_baby(client))).json() == []


def test_los_codigos_nuevos_son_cortos_y_los_largos_siguen_valiendo(client):
    code = new_baby(client, "A")
    assert len(code.replace("-", "")) == 8
    import db
    with db.db() as c:
        c.execute("INSERT INTO babies (id, name, code) VALUES ('old', 'Viejo', 'ABCDEFGHJKMNPQRS')")
    assert client.get("/api/baby", headers=H("ABCD-EFGH-JKMN-PQRS")).json()["name"] == "Viejo"


def test_demasiados_intentos_fallidos_bloquean(client):
    for _ in range(10):
        assert client.get("/api/feedings", headers=H("ZZZZ-ZZZZ")).status_code == 401
    assert client.get("/api/feedings", headers=H("ZZZZ-ZZZZ")).status_code == 429
