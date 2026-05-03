"""Registered inference backends (SuPreM variants + mock) for model comparison workflows."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Backend = Literal["mock", "docker", "singularity"]


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    description: str
    requires_gpu: bool
    backend: Backend
    docker_image: str | None = None


def _sif_path() -> str:
    return os.environ.get("SUPREM_SIF_PATH", "").strip()


def singularity_available() -> bool:
    p = _sif_path()
    return bool(p and Path(p).is_file())


def default_model_id() -> str:
    raw = os.environ.get("SUPREM_DEFAULT_MODEL_ID", "").strip()
    if raw:
        return raw
    # Mirror server inference_mode when unset
    mode = os.environ.get("SUPREM_INFERENCE_MODE", "docker").strip().lower()
    if mode == "mock":
        return "mock"
    if mode == "singularity":
        return "suprem_singularity" if singularity_available() else "suprem_docker"
    return "suprem_docker"


def all_specs() -> list[ModelSpec]:
    img = os.environ.get("SUPREM_DOCKER_IMAGE", "qchen99/suprem:v1")
    return [
        ModelSpec(
            id="mock",
            name="Mock segmentation",
            description="Fast deterministic NIfTI placeholders for UX / recording (no GPU).",
            requires_gpu=False,
            backend="mock",
        ),
        ModelSpec(
            id="suprem_docker",
            name="SuPreM (Docker)",
            description=f"SuPreM via Docker — image {img} (`predict.sh`, HF layout).",
            requires_gpu=True,
            backend="docker",
            docker_image=img,
        ),
        ModelSpec(
            id="suprem_singularity",
            name="SuPreM (Singularity)",
            description="SuPreM container (.sif) with GPU; set SUPREM_SIF_PATH.",
            requires_gpu=True,
            backend="singularity",
            docker_image=None,
        ),
    ]


def get_spec(model_id: str) -> ModelSpec:
    for s in all_specs():
        if s.id == model_id:
            return s
    raise KeyError(model_id)


def list_models_public() -> list[dict[str, Any]]:
    """UI + API listing with availability hints."""
    out: list[dict[str, Any]] = []
    for s in all_specs():
        available = True
        reason: str | None = None
        if s.backend == "singularity" and not singularity_available():
            available = False
            reason = "Set SUPREM_SIF_PATH to a valid suprem_final.sif on the server."

        row: dict[str, Any] = {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "requires_gpu": s.requires_gpu,
            "backend": s.backend,
            "available": available,
            "docker_image": s.docker_image,
        }
        if reason:
            row["unavailable_reason"] = reason
        out.append(row)
    return out
