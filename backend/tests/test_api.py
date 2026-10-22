import pytest
from fastapi.testclient import TestClient

from api import routes
from main import app
from services.projects import ProjectStore


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "_store", ProjectStore(tmp_path))
    return TestClient(app)


RECT = {"kind": "rectangular", "b": 300, "h": 500}


def test_health_and_info(client):
    assert client.get("/api/health").json()["status"] == "ok"
    info = client.get("/api/info").json()
    assert "Anejo 19" in info["norm"]["name"]
    assert all(m["status"] in ("verificado", "pendiente_validacion", "no_disponible") for m in info["modules"])
    assert not any(m["status"] == "verificado" for m in info["modules"])  # sin validación bibliográfica aún


def test_parameters(client):
    r = client.get("/api/norma/parametros").json()
    assert any(p["key"] == "alpha_cc" for p in r["parameters"])
    r = client.post("/api/norma/parametros", json={"alpha_cc": 0.9})
    assert r.status_code == 200 and r.json()["overrides"] == {"alpha_cc": 0.9}
    r = client.post("/api/norma/parametros", json={"alpha_cc": 2})
    assert r.status_code == 422


def test_materials(client):
    r = client.post("/api/materiales", json={"concrete_class": "C30/37"})
    assert r.status_code == 200
    assert r.json()["concrete"]["fcd"] == pytest.approx(20.0)
    assert client.post("/api/materiales", json={"concrete_class": "C31"}).status_code == 422


def test_section_properties(client):
    r = client.post("/api/secciones/propiedades", json={
        "shape": RECT, "layers": [{"face": "inferior", "n": 3, "diameter": 16}]})
    assert r.status_code == 200
    assert r.json()["d_inferior"] == pytest.approx(500 - 30 - 8 - 8)
    r = client.post("/api/secciones/propiedades", json={"shape": {"kind": "T", "h": 500}})
    assert r.status_code == 422


def test_flexure_design_and_check(client):
    r = client.post("/api/vigas/flexion", json={"shape": RECT, "M_Ed_kNm": 150})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["proposal"]["text_tension"]
    r = client.post("/api/vigas/flexion", json={
        "mode": "check", "shape": RECT, "M_Ed_kNm": 150,
        "layers": [{"face": "inferior", "n": 3, "diameter": 20}]})
    assert r.status_code == 200
    assert r.json()["trace"]["checks"]


def test_flexure_invalid_input(client):
    r = client.post("/api/vigas/flexion", json={"shape": {"kind": "rectangular", "b": -1, "h": 500},
                                                "M_Ed_kNm": 10})
    assert r.status_code == 422
    r = client.post("/api/vigas/flexion", json={"shape": RECT, "M_Ed_kNm": 0})
    assert r.status_code == 422
    r = client.post("/api/vigas/flexion", json={"shape": RECT, "M_Ed_kNm": 100,
                                                "parameter_overrides": {"gamma_c_persistente": 0.5}})
    assert r.status_code == 422


def test_pdf_report(client):
    r = client.post("/api/informes/vigas/flexion", json={
        "project_name": "Prueba", "request": {"shape": RECT, "M_Ed_kNm": 150, "element_name": "V-1"}})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    r = client.post("/api/informes/vigas/flexion", json={
        "request": {"mode": "check", "shape": {"kind": "T", "bf": 800, "hf": 120, "bw": 300, "h": 600},
                    "M_Ed_kNm": 200, "layers": [{"face": "inferior", "n": 3, "diameter": 20}]}})
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"


def test_projects_crud(client):
    el = {"type": "viga_flexion", "name": "V-1", "input": {"shape": RECT, "M_Ed_kNm": 100}}
    r = client.post("/api/proyectos", json={"name": "Edificio A", "elements": [el]})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["format_version"] == 1
    assert client.get("/api/proyectos").json()[0]["id"] == pid
    r = client.put(f"/api/proyectos/{pid}", json={"name": "Edificio B", "elements": []})
    assert r.json()["name"] == "Edificio B"
    exported = client.get(f"/api/proyectos/{pid}").json()
    r = client.post("/api/proyectos/importar", json=exported)
    assert r.status_code == 201 and r.json()["id"] != pid
    assert client.delete(f"/api/proyectos/{pid}").status_code == 204
    assert client.get(f"/api/proyectos/{pid}").status_code == 404
    assert client.get("/api/proyectos/..%2F..%2Fetc").status_code == 404
    assert client.get("/api/proyectos/%2E%2E").status_code == 404


def test_project_validation(client):
    r = client.post("/api/proyectos", json={"name": "X", "elements": [{"type": "otro", "input": {}}]})
    assert r.status_code == 422
    r = client.post("/api/proyectos/importar", json={"format": "x", "format_version": 1})
    assert r.status_code == 422
    r = client.post("/api/proyectos/importar", json={"format": "ha-anejo19-project", "format_version": 99})
    assert r.status_code == 422


SHEAR = {"shape": RECT, "V_Ed_kN": 150, "layers": [{"face": "inferior", "n": 3, "diameter": 20}]}


def test_shear_endpoint_and_report(client):
    r = client.post("/api/vigas/cortante", json=SHEAR)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["result"]["proposal"]["spacing"] > 0
    r = client.post("/api/vigas/cortante", json={**SHEAR, "mode": "check", "stirrup_spacing": 200})
    assert r.status_code == 200
    r = client.post("/api/informes/vigas/cortante", json={"request": SHEAR})
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    r = client.post("/api/informes/vigas/cortante", json={"request": {**SHEAR, "mode": "check", "stirrup_spacing": 200}})
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"


def test_shear_invalid(client):
    assert client.post("/api/vigas/cortante", json={**SHEAR, "mode": "check"}).status_code == 422
    assert client.post("/api/vigas/cortante", json={**SHEAR, "alpha_deg": 30}).status_code == 422
    assert client.post("/api/vigas/cortante", json={**SHEAR, "cot_theta": 2.5}).status_code == 422
    assert client.post("/api/vigas/cortante", json={**SHEAR, "layers": []}).status_code == 422


def test_project_with_shear_element(client):
    el = {"type": "viga_cortante", "name": "V-1 cortante", "input": SHEAR}
    r = client.post("/api/proyectos", json={"name": "P", "elements": [el]})
    assert r.status_code == 201


COLUMN = {"b": 400, "h": 400, "cover": 35, "N_Ed_kN": 1500, "M01_kNm": 20, "M02_kNm": 40, "length": 3000,
          "phi_ef": 1.0, "stirrup_spacing": 200,
          "layers": [{"face": "inferior", "n": 3, "diameter": 16}, {"face": "superior", "n": 3, "diameter": 16},
                     {"face": "lateral", "n": 1, "diameter": 16}]}


def test_column_endpoint_and_report(client):
    r = client.post("/api/pilares", json=COLUMN)
    assert r.status_code == 200, r.text
    assert r.json()["result"]["diagram"]
    r = client.post("/api/informes/pilares", json={"request": COLUMN})
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    assert client.post("/api/pilares", json={**COLUMN, "N_Ed_kN": 0}).status_code == 422
    assert client.post("/api/pilares", json={**COLUMN, "b": 100, "h": 500}).status_code == 422
    r = client.post("/api/proyectos", json={"name": "P", "elements": [{"type": "pilar", "name": "P-1", "input": COLUMN}]})
    assert r.status_code == 201


LAY = [{"face": "inferior", "n": 3, "diameter": 20}, {"face": "superior", "n": 2, "diameter": 12}]


def test_els_endpoints_and_reports(client):
    crack = {"shape": RECT, "layers": LAY, "M_qp_kNm": 100, "exposure": "XC3"}
    r = client.post("/api/els/fisuracion", json=crack)
    assert r.status_code == 200, r.text
    assert r.json()["result"]["w_k"] > 0
    defl = {"shape": RECT, "layers": LAY, "span": 6000, "M_qp_kNm": 90, "As_req": 800}
    r = client.post("/api/els/deformaciones", json=defl)
    assert r.status_code == 200, r.text
    for path, body in (("fisuracion", crack), ("deformaciones", defl)):
        r = client.post(f"/api/informes/els/{path}", json={"request": body})
        assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    assert client.get("/api/els/catalogo").json()["exposure_wmax"]["XC1"] == 0.4
    assert client.post("/api/els/fisuracion", json={**crack, "exposure": "XX"}).status_code == 422
    assert client.post("/api/els/deformaciones", json={**defl, "RH": 30}).status_code == 422


def test_slab_endpoint_and_report(client):
    body = {"h": 200, "m_Ed_kNm": 30, "v_Ed_kN": 50, "span": 5000}
    r = client.post("/api/losas", json=body)
    assert r.status_code == 200 and r.json()["result"]["proposal"]
    r = client.post("/api/informes/losas", json={"request": body})
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    assert client.post("/api/losas", json={**body, "m_Ed_kNm": 0}).status_code == 422


def test_spa_fallback(tmp_path):
    from main import SPAStaticFiles
    from starlette.applications import Starlette
    (tmp_path / "index.html").write_text("<title>HA</title>", encoding="utf-8")
    app2 = Starlette()
    app2.mount("/", SPAStaticFiles(directory=tmp_path, html=True))
    c = TestClient(app2)
    assert c.get("/pilares").status_code == 200
    assert "HA" in c.get("/els").text
    assert c.get("/api/no-existe").status_code == 404
