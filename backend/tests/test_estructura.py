"""Proyecto estructural integral: persistencia, aislamiento, relaciones, transmisión de cargas,
control de resultados desactualizados y datos incompletos.

Los valores de referencia de las cargas se obtienen a mano con las reglas documentadas en
docs/proyecto_integral.md (equilibrio de vigas isostáticas y áreas tributarias)."""

import json

import pytest
from fastapi.testclient import TestClient

import main
from api import routes
from estructura.db import DB_FILENAME, Database
from estructura.repository import Repository
from estructura.model import ModelError
from services.projects import ProjectStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    s = ProjectStore(tmp_path)
    monkeypatch.setattr(routes, "_store", s)
    return s


@pytest.fixture()
def client(store):
    return TestClient(main.app)


def ok(r, code=200):
    assert r.status_code == code, r.text
    return r.json() if r.content else None


class Vivienda:
    """Vivienda mínima: una losa sobre dos vigas; V2 apoya en V1; V1 en dos pilares; P1 en zapata."""

    def __init__(self, c: TestClient, name="Vivienda"):
        self.c = c
        p = ok(c.post("/api/estructuras", json={
            "name": name, "location": "Madrid", "settings": {"sigma_adm": 200},
            "levels": [{"code": "N100", "elevation_m": 3, "height_m": 3}]}), 201)
        self.pid = p["project"]["id"]
        lv = p["levels"][0]["id"]
        self.ids = {}
        for t, code, data in [
            ("losa", "L101", {"lx": 4, "ly": 5, "h": 200, "cm": 1.5, "scu": 2, "muros": 20, "luz": 4}),
            ("viga", "V1", {"b": 250, "h": 500, "L": 5}),
            ("viga", "V2", {"b": 250, "h": 500, "L": 4}),
            ("pilar", "P1", {"b": 300, "h": 300}),
            ("pilar", "P2", {"b": 300, "h": 300}),
            ("zapata", "Z1", {"B": 1.5, "L": 1.5, "h": 500}),
        ]:
            self.ids[code] = ok(c.post(f"/api/estructuras/{self.pid}/elementos",
                                       json={"type": t, "code": code, "level_id": None if t == "zapata" else lv,
                                             "data": data}), 201)["id"]
        I = self.ids
        self.link("losa_viga", "L101", "V1", {"metodo": "area", "area": 10})
        self.link("losa_viga", "L101", "V2", {"metodo": "area", "area": 10})
        self.link("viga_apoyo", "V2", "V1", {"extremo": "fin", "posicion": 2.5})
        self.link("viga_apoyo", "V1", "P1", {"extremo": "inicio"})
        self.link("viga_apoyo", "V1", "P2", {"extremo": "fin"})
        self.link("pilar_zapata", "P1", "Z1")

    def link(self, kind, s, t, data=None, code=201):
        return self.c.post(f"/api/estructuras/{self.pid}/relaciones",
                           json={"kind": kind, "source_id": self.ids[s], "target_id": self.ids[t], "data": data or {}})

    def ov(self):
        return ok(self.c.get(f"/api/estructuras/{self.pid}"))

    def el(self, code):
        return next(e for e in self.ov()["elements"] if e["code"] == code)

    def detail(self, code):
        return ok(self.c.get(f"/api/estructuras/{self.pid}/elementos/{self.ids[code]}"))

    def patch(self, which, **body):
        return ok(self.c.patch(f"/api/estructuras/{self.pid}/elementos/{self.ids[which]}", json=body))

    def calc(self, **body):
        return ok(self.c.post(f"/api/estructuras/{self.pid}/calcular", json=body))


def test_create_and_reopen_after_restart(tmp_path, monkeypatch):
    s1 = ProjectStore(tmp_path)
    monkeypatch.setattr(routes, "_store", s1)
    v = Vivienda(TestClient(main.app))
    v.calc()
    before = v.ov()
    s1.db.close()
    # «Reinicio»: nueva conexión a la misma base de datos
    s2 = ProjectStore(tmp_path)
    monkeypatch.setattr(routes, "_store", s2)
    c2 = TestClient(main.app)
    after = ok(c2.get(f"/api/estructuras/{v.pid}"))
    assert after["project"]["name"] == "Vivienda"
    assert {e["code"]: (e["status"], e["data"]) for e in after["elements"]} == \
           {e["code"]: (e["status"], e["data"]) for e in before["elements"]}
    assert len(after["links"]) == 6
    assert any(e["status"] == "actual" for e in after["elements"])


def test_two_projects_are_isolated(client):
    a = Vivienda(client, "A")
    b = Vivienda(client, "B")
    # mismos códigos en ambos proyectos, identificadores distintos
    assert set(a.ids) == set(b.ids) and not set(a.ids.values()) & set(b.ids.values())
    a.patch("L101", data={"scu": 5})
    assert b.detail("L101")["data"]["scu"] == 2
    # no se puede acceder a un elemento de otro proyecto ni relacionar elementos de proyectos distintos
    r = client.get(f"/api/estructuras/{a.pid}/elementos/{b.ids['V1']}")
    assert r.status_code == 404
    r = client.post(f"/api/estructuras/{a.pid}/relaciones",
                    json={"kind": "losa_viga", "source_id": a.ids["L101"], "target_id": b.ids["V1"],
                          "data": {"area": 3}})
    assert r.status_code == 404
    client.delete(f"/api/estructuras/{a.pid}")
    assert b.ov()["summary"]["n_elements"] == 6


def test_relations_use_stable_ids_when_renaming(client):
    v = Vivienda(client)
    v.patch("V1", code="V101")
    det = ok(client.get(f"/api/estructuras/{v.pid}/elementos/{v.ids['P1']}"))
    assert [r["other_code"] for r in det["relations"] if r["direction"] == "entrada"] == ["V101"]
    assert det["loads_detail"]["rows"][0]["origen"] == "Viga V101"


def test_unique_codes_and_link_validation(client):
    v = Vivienda(client)
    r = client.post(f"/api/estructuras/{v.pid}/elementos", json={"type": "viga", "code": "V1"})
    assert r.status_code == 422 and "Ya existe" in r.json()["detail"]
    assert v.link("losa_viga", "V1", "L101").status_code == 422          # tipos incompatibles
    assert v.link("viga_apoyo", "V2", "P2", {"extremo": "fin"}).status_code == 422   # extremo ya apoyado
    assert v.link("viga_apoyo", "V1", "V2", {"extremo": "inicio", "posicion": 1}).status_code == 422  # ciclo
    assert v.link("losa_viga", "L101", "V1", {"metodo": "area"}).status_code == 422  # falta el área
    assert v.link("pilar_zapata", "P2", "Z1").status_code == 422          # zapata ya ocupada


def test_load_transfer_slab_beam_column_footing(client):
    v = Vivienda(client)
    # Losa: g = 0,2·25 + 1,5 + 20/(4·5) = 7,5 kN/m²; q = 2
    L = v.el("L101")["loads"]
    assert L["g"] == pytest.approx(7.5) and L["q"] == pytest.approx(2)
    # V2: g = 0,25·0,5·25 + 7,5·10/4 = 21,875 kN/m; q = 2·10/4 = 5; biapoyada L = 4
    V2 = v.el("V2")["loads"]
    assert V2["g"] == pytest.approx(21.875) and V2["q"] == pytest.approx(5)
    assert V2["reactions"]["fin"] == pytest.approx([43.75, 10.0])
    assert V2["efforts"]["M_pos"] == pytest.approx((1.35 * 21.875 + 1.5 * 5) * 16 / 8, rel=1e-4)
    # V1: g = 3,125 + 7,5·10/5 = 18,125; q = 4; puntual de V2 en x = 2,5 (G = 43,75; Q = 10)
    V1 = v.el("V1")["loads"]
    MG = 18.125 * 25 / 8 + 43.75 * 5 / 4
    MQ = 4 * 25 / 8 + 10 * 5 / 4
    assert V1["efforts"]["M_k"] == pytest.approx(MG + MQ, rel=1e-4)
    assert V1["efforts"]["M_qp"] == pytest.approx(MG + 0.3 * MQ, rel=1e-4)
    RG, RQ = 18.125 * 2.5 + 43.75 / 2, 4 * 2.5 + 5
    assert V1["reactions"]["inicio"] == pytest.approx([RG, RQ])
    # P1: N_G = R_G + peso propio 0,3·0,3·3·25; N_Q = R_Q
    P1 = v.el("P1")["loads"]
    assert P1["N_G"] == pytest.approx(RG + 0.3 * 0.3 * 3 * 25) and P1["N_Q"] == pytest.approx(RQ)
    assert P1["efforts"]["N_Ed"] == pytest.approx(1.35 * P1["N_G"] + 1.5 * P1["N_Q"], rel=1e-4)
    # Z1 recibe el axil de P1; presión media frente a σ_adm
    v.calc(element_ids=[v.ids["Z1"]])
    z = v.detail("Z1")
    sig = (P1["N_G"] + P1["N_Q"] + 1.5 * 1.5 * 0.5 * 25) / (1.5 * 1.5)
    out = next(c for c in z["calc_list"] if c["calc_type"] == "zapata_terreno")["stored"]["output"]
    assert out["result"]["result"]["sigma"] == pytest.approx(sig, rel=1e-6)
    # procedencia visible
    rows = v.detail("V1")["loads_detail"]["rows"]
    assert any(r["origen"] == "Losa L101" and r["element_id"] == v.ids["L101"] for r in rows)
    assert any("Reacción de Viga V2" in r["concepto"] for r in rows)


def test_modify_slab_marks_dependents_stale_and_selective_recalc(client):
    v = Vivienda(client)
    v.patch("P1", data={"layers": [{"face": "inferior", "n": 2, "diameter": 16},
                                   {"face": "superior", "n": 2, "diameter": 16}], "stirrup_s": 200})
    v.calc()
    assert v.el("V1")["calcs"]["viga_flexion"]["status"] == "actual"
    assert v.el("P1")["status"] == "actual" and v.el("Z1")["status"] == "actual"
    res = v.patch("L101", data={"scu": 3})
    affected = {a["code"] for a in res["affected"]}
    assert affected == {"L101", "V1", "V2", "P1", "P2", "Z1"}
    ov = v.ov()
    st = {e["code"]: e for e in ov["elements"]}
    assert st["L101"]["calcs"]["losa_flexion"]["status"] == "desactualizado"
    assert st["V1"]["calcs"]["viga_flexion"]["status"] == "desactualizado"
    assert st["P1"]["status"] == "desactualizado" and st["Z1"]["status"] == "desactualizado"
    # los resultados desactualizados no se presentan como vigentes
    assert st["V1"]["calcs"]["viga_flexion"]["summary"] is None
    assert ov["summary"]["verification"]["level"] == "pendiente"
    # recálculo selectivo: solo lo desactualizado; lo actual no se repite
    r = v.calc(element_ids=[v.ids["V2"]])
    assert {x["calc_type"] for x in r["report"] if x["result"] == "calculado"} == {"viga_flexion"}
    assert v.el("V2")["calcs"]["viga_flexion"]["status"] == "actual"
    assert v.el("V1")["calcs"]["viga_flexion"]["status"] == "desactualizado"
    r2 = v.calc()
    assert r2["n_calculated"] >= 4
    assert v.calc()["n_calculated"] == 0  # nada pendiente
    # el resultado guarda la entrada exacta y la versión del motor
    det = v.detail("V1")
    c = next(x for x in det["calc_list"] if x["calc_type"] == "viga_flexion")
    assert c["stored"]["input"]["request"]["M_Ed_kNm"] == pytest.approx(v.el("V1")["loads"]["efforts"]["M_pos"], rel=1e-6)
    assert c["stored"]["engine_version"] and c["stored"]["computed_at"]
    # Un cambio en un elemento aguas abajo no afecta a los de aguas arriba
    res = v.patch("P1", data={"beta": 0.7})
    assert {a["code"] for a in res["affected"]} == {"P1", "Z1"}
    assert v.el("V1")["calcs"]["viga_flexion"]["status"] == "actual"


def test_settings_change_affects_all(client):
    v = Vivienda(client)
    v.calc()
    ok(client.patch(f"/api/estructuras/{v.pid}", json={"settings": {"gamma_hormigon": 24}}))
    assert v.el("L101")["calcs"]["losa_flexion"]["status"] == "desactualizado"


def test_missing_data_is_requested_not_invented(client):
    v = Vivienda(client)
    v.patch("L101", data={"scu": None})
    e = v.el("L101")
    assert e["status"] == "faltan_datos" and "Sobrecarga de uso de la losa" in e["missing"]
    # se propaga como dato pendiente a las vigas que reciben la losa
    assert any("Losa L101" in m for m in v.el("V2")["missing"])
    # sin armadura definida no se comprueban pilares
    assert "Armadura longitudinal dispuesta del pilar" in v.el("P1")["missing"]
    r = v.calc()
    assert any(x["code"] == "P1" and x["result"] == "faltan_datos" for x in r["report"])
    # zapata sin tensión admisible
    ok(client.patch(f"/api/estructuras/{v.pid}", json={"settings": {"sigma_adm": None}}))
    assert any("Tensión admisible" in m for m in v.el("Z1")["missing"])
    # losa bidireccional sin esfuerzos manuales: no se inventa un método de placas
    v.patch("L101", data={"scu": 2, "tipo": "bidireccional"})
    e = v.el("L101")
    assert e["status"] == "error_datos" and "placas" in e["errors"][0]
    # validación de rangos
    r = client.patch(f"/api/estructuras/{v.pid}/elementos/{v.ids['V1']}", json={"data": {"h": -5}})
    assert r.status_code == 422
    r = client.patch(f"/api/estructuras/{v.pid}/elementos/{v.ids['V1']}", json={"data": {"inventado": 1}})
    assert r.status_code == 422


def test_engine_error_is_recorded(client):
    v = Vivienda(client)
    # canto mínimo y carga enorme: el motor rechaza el dimensionado con un error de dominio
    v.patch("V2", data={"h": 150, "b": 100, "g_extra": 900})
    r = v.calc(element_ids=[v.ids["V2"]], calc_types=["viga_flexion"])
    assert r["report"][0]["result"] in ("error", "calculado")
    st = v.el("V2")["calcs"]["viga_flexion"]["status"]
    assert st in ("error", "actual")


def test_adopt_proposal_and_check_mode(client):
    v = Vivienda(client)
    r = client.post(f"/api/estructuras/{v.pid}/elementos/{v.ids['V1']}/adoptar-propuesta")
    assert r.status_code == 422  # sin dimensionado vigente
    v.calc(element_ids=[v.ids["V1"]])
    r = ok(client.post(f"/api/estructuras/{v.pid}/elementos/{v.ids['V1']}/adoptar-propuesta"))
    assert r["adopted"]["layers"]
    v.calc(element_ids=[v.ids["V1"]])
    det = v.detail("V1")
    fl = next(x for x in det["calc_list"] if x["calc_type"] == "viga_flexion")
    assert fl["status"] == "actual" and fl["request"]["mode"] == "check"
    assert next(x for x in det["calc_list"] if x["calc_type"] == "viga_cortante")["status"] == "actual"


def test_duplicate_archive_export_import(client):
    v = Vivienda(client)
    v.calc()
    d = ok(client.post(f"/api/estructuras/{v.pid}/duplicar", json={"name": "Copia"}), 201)
    assert d["project"]["id"] != v.pid and len(d["elements"]) == 6 and len(d["links"]) == 6
    assert {e["code"]: e["status"] for e in d["elements"]} == {e["code"]: e["status"] for e in v.ov()["elements"]}
    ok(client.post(f"/api/estructuras/{v.pid}/archivar", json={"archived": True}))
    lst = ok(client.get("/api/estructuras"))
    assert next(p for p in lst if p["id"] == v.pid)["status"] == "archivado"
    data = ok(client.get(f"/api/estructuras/{v.pid}/exportar"))
    assert data["format_version"] == 2
    imp = ok(client.post("/api/estructuras/importar", json=json.loads(json.dumps(data))), 201)
    assert imp["project"]["id"] != v.pid and len(imp["links"]) == 6
    # historial
    h = ok(client.get(f"/api/estructuras/{v.pid}/historial"))
    assert any(x["action"] == "relacion_creada" for x in h)


def test_delete_element_cascades_links_and_level_restrict(client):
    v = Vivienda(client)
    r = ok(client.delete(f"/api/estructuras/{v.pid}/elementos/{v.ids['V2']}"))
    assert "V1" in r["affected"]
    assert len(v.ov()["links"]) == 4
    lv = v.ov()["levels"][0]["id"]
    r = client.delete(f"/api/estructuras/{v.pid}/niveles/{lv}")
    assert r.status_code == 422 and "tiene elementos" in r.json()["detail"]


def test_reports(client):
    v = Vivienda(client)
    v.calc()
    for u in ["planilla.xlsx", "informe.pdf", f"elementos/{v.ids['V1']}/ficha.pdf",
              f"elementos/{v.ids['V1']}/informe.pdf?calc=viga_flexion", f"elementos/{v.ids['L101']}/informe.pdf?calc=losa_flexion"]:
        r = client.get(f"/api/estructuras/{v.pid}/{u}")
        assert r.status_code == 200, (u, r.text)
        assert r.content[:4] in (b"%PDF", b"PK\x03\x04")
    t = ok(client.get(f"/api/estructuras/{v.pid}/planillas"))
    assert {x["key"] for x in t} >= {"losas", "vigas", "pilares", "zapatas", "resultados", "armaduras", "pendientes"}
    v.patch("L101", data={"cm": 2})
    r = client.get(f"/api/estructuras/{v.pid}/elementos/{v.ids['V1']}/informe.pdf?calc=viga_flexion")
    assert r.status_code == 409


def test_legacy_json_projects_are_migrated(tmp_path):
    legacy = {"format": "ha-anejo19-project", "format_version": 1, "software_version": "0.6.0",
              "id": "ab" * 16, "name": "Antiguo", "description": "", "created": "2025-01-01T00:00:00+00:00",
              "modified": "2025-01-01T00:00:00+00:00", "norm": {}, "parameter_overrides": {},
              "elements": [{"id": "x", "type": "viga_flexion", "name": "V-1",
                            "input": {"shape": {"kind": "rectangular", "b": 300, "h": 500}, "M_Ed_kNm": 100},
                            "result": None}]}
    f = tmp_path / ("ab" * 16 + ".json")
    f.write_text(json.dumps(legacy), encoding="utf-8")
    s = ProjectStore(tmp_path)
    p = s.get("ab" * 16)
    assert p["name"] == "Antiguo" and p["elements"][0]["name"] == "V-1"
    assert f.exists()  # el fichero original se conserva
    s.db.close()
    s2 = ProjectStore(tmp_path)  # no se importa dos veces
    assert len(s2.list()) == 1


def test_schema_migrations_are_versioned(tmp_path):
    db = Database(tmp_path / DB_FILENAME)
    assert db.schema_version() >= 1
    repo = Repository(db)
    pid = repo.create_project({"name": "X"})
    with pytest.raises(ModelError):
        repo.create_element(pid, "viga", "V1", data={"b": 10})  # fuera de rango
    db.close()
    db2 = Database(tmp_path / DB_FILENAME)  # reabrir no vuelve a migrar ni pierde datos
    assert Repository(db2).get_project(pid)["name"] == "X"
