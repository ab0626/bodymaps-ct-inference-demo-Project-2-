from __future__ import annotations

import os
import shutil
from pathlib import Path

import nibabel as nib
import numpy as np

from app.inference_runner import run_suprem_sync


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_api_models(client):
    r = client.get("/api/models")
    assert r.status_code == 200
    data = r.json()
    assert "models" in data and "default_model_id" in data
    ids = {m["id"] for m in data["models"]}
    assert {"mock", "suprem_docker", "suprem_singularity"}.issubset(ids)


def test_api_meta(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    j = r.json()
    assert j["inference_mode"] == "mock"
    assert "default_model_id" in j
    assert "max_upload_mb" in j


def test_mock_inference_writes_expected_masks():
    """Starlette TestClient can cancel orphaned asyncio tasks; keep an end-to-end sync check via the runner."""
    work = Path(os.environ["SUPREM_WORK_DIR"])
    base = work / "_pytest_direct"
    shutil.rmtree(base, ignore_errors=True)
    inp = base / "inputs"
    out = base / "outputs"
    inp.mkdir(parents=True)
    out.mkdir(parents=True)

    aff = np.eye(4, dtype=np.float32)
    ct = inp / "unit_case"
    ct.mkdir()
    nib.save(nib.Nifti1Image(np.zeros((6, 6, 6), dtype=np.float32), aff), ct / "ct.nii.gz")

    result = run_suprem_sync(inputs_dir=inp, outputs_dir=out, backend="mock")
    assert result.ok
    seg_dir = out / "unit_case" / "segmentations"
    assert seg_dir.is_dir()
    names = sorted(p.name for p in seg_dir.glob("*.nii.gz"))
    assert "liver.nii.gz" in names
    assert "aorta.nii.gz" in names
