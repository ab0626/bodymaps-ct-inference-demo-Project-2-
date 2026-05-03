from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def test_env(monkeypatch, tmp_path):
    wd = tmp_path / "suprem_work"
    wd.mkdir()
    monkeypatch.setenv("SUPREM_WORK_DIR", str(wd))
    monkeypatch.setenv("SUPREM_INFERENCE_MODE", "mock")
    monkeypatch.delenv("SUPREM_SIF_PATH", raising=False)


@pytest.fixture(autouse=True)
def reset_job_registry():
    yield
    from app import main as main_module

    main_module._jobs.clear()
    main_module._tasks.clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)
