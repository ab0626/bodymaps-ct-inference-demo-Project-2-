from __future__ import annotations

import pytest

from app.model_registry import default_model_id, get_spec, list_models_public


def test_list_models_contains_core_runners(monkeypatch):
    monkeypatch.delenv("SUPREM_DEFAULT_MODEL_ID", raising=False)
    monkeypatch.delenv("SUPREM_SIF_PATH", raising=False)
    models = list_models_public()
    ids = {m["id"] for m in models}
    assert "mock" in ids
    assert "suprem_docker" in ids
    assert "suprem_singularity" in ids
    sig = next(m for m in models if m["id"] == "suprem_singularity")
    assert sig["available"] is False


def test_default_follows_inference_mode(monkeypatch):
    monkeypatch.setenv("SUPREM_INFERENCE_MODE", "mock")
    monkeypatch.delenv("SUPREM_DEFAULT_MODEL_ID", raising=False)
    assert default_model_id() == "mock"


def test_get_spec_missing():
    with pytest.raises(KeyError):
        get_spec("not_a_real_model")
