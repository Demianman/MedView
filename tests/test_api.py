from __future__ import annotations

from fastapi.testclient import TestClient

from medview.app import app, store

client = TestClient(app)


def test_empty_and_invalid_states():
    store.volume = None
    assert client.get("/api/status").json()["state"] == "empty"
    response = client.post("/api/load-nifti", files={"file": ("bad.txt", b"not an image")})
    assert response.status_code == 422
    assert response.json()["state"] == "invalid-file"


def test_demo_inference_edit_export_flow():
    loaded = client.post("/api/load-demo")
    assert loaded.status_code == 200
    assert loaded.json()["metadata"]["source_type"] == "NIfTI"
    assert client.get("/api/slice/axial/40").headers["content-type"] == "image/png"
    inferred = client.post("/api/infer").json()
    assert inferred["clinical_model"] is False
    assert inferred["mask"]["voxel_count"] > 0
    painted = client.post(
        "/api/paint",
        json={"plane": "axial", "index": 40, "u": 0.5, "v": 0.5, "radius": 3, "value": 0},
    )
    assert painted.status_code == 200
    assert painted.json()["history"]["can_undo"] is True
    undone = client.post("/api/undo")
    assert undone.status_code == 200
    assert undone.json()["history"]["can_redo"] is True
    redone = client.post("/api/redo")
    assert redone.status_code == 200
    assert redone.json()["history"]["can_undo"] is True
    exported = client.get("/api/export")
    assert exported.status_code == 200
    assert exported.content.startswith(b"PK")
