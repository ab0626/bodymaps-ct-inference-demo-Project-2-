"""Run SuPreM inference via Docker, Singularity, or a mock pipeline for demos."""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .model_registry import Backend

Mode = Literal["docker", "singularity", "mock"]


def inference_mode() -> Mode:
    raw = os.environ.get("SUPREM_INFERENCE_MODE", "docker").strip().lower()
    if raw in ("docker", "singularity", "mock"):
        return raw  # type: ignore[return-value]
    return "docker"


@dataclass(frozen=True)
class RunResult:
    ok: bool
    message: str
    elapsed_s: float


def _ensure_case_layout(inputs_root: Path) -> tuple[Path, str]:
    """Return (path_to_case_dir, casename). Expects ct.nii or ct.nii.gz under inputs_root."""
    candidates: list[Path] = []
    for p in list(inputs_root.rglob("ct.nii.gz")) + list(inputs_root.rglob("ct.nii")):
        if "__MACOSX" in p.parts or p.name.startswith("._"):
            continue
        candidates.append(p)
    if not candidates:
        raise FileNotFoundError("No ct.nii or ct.nii.gz found under extracted upload.")
    p = min(candidates, key=lambda x: len(x.parts))
    return p.parent, p.parent.name


def _mock_write_outputs(case_dir: Path, outputs_root: Path) -> None:
    """Write tiny valid NIfTI placeholders that mirror SuPreM output filenames (for UI/testing)."""
    import numpy as np
    import nibabel as nib

    out_case = outputs_root / case_dir.name
    seg_dir = out_case / "segmentations"
    seg_dir.mkdir(parents=True, exist_ok=True)
    organs = (
        "aorta",
        "gall_bladder",
        "kidney_left",
        "kidney_right",
        "liver",
        "pancreas",
        "postcava",
        "spleen",
        "stomach",
    )
    affine = np.eye(4, dtype=np.float32)
    labels = np.zeros((64, 64, 64), dtype=np.uint16)
    for idx, _ in enumerate(organs, start=1):
        labels[idx * 4 : idx * 4 + 2, idx * 4 : idx * 4 + 2, idx * 4 : idx * 4 + 2] = idx
    combo = out_case / "combined_labels.nii.gz"
    nib.save(nib.Nifti1Image(labels, affine), combo)
    for idx, o in enumerate(organs, start=1):
        mask = (labels == idx).astype(np.uint8)
        nib.save(nib.Nifti1Image(mask, affine), seg_dir / f"{o}.nii.gz")


def run_suprem_sync(
    *,
    inputs_dir: Path,
    outputs_dir: Path,
    gpu_device: str = "0",
    backend: Backend | None = None,
    docker_image_override: str | None = None,
) -> RunResult:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    mode: Backend = backend if backend is not None else inference_mode()  # type: ignore[assignment]
    timeout_s = int(float(os.environ.get("SUPREM_INFERENCE_TIMEOUT_S", "1800")))

    if mode == "mock":
        case_dir, _ = _ensure_case_layout(inputs_dir)
        _mock_write_outputs(case_dir, outputs_dir)
        return RunResult(True, "Mock inference wrote placeholder segmentations.", time.perf_counter() - t0)

    inp = inputs_dir.resolve()
    out = outputs_dir.resolve()

    if mode == "docker":
        image = docker_image_override or os.environ.get("SUPREM_DOCKER_IMAGE", "qchen99/suprem:v1")
        argv = [
            "docker",
            "run",
            "--gpus",
            f"device={gpu_device}",
            "-m",
            os.environ.get("SUPREM_DOCKER_MEMORY", "128G"),
            "--rm",
            "-v",
            f"{inp}:/workspace/inputs",
            "-v",
            f"{out}:/workspace/outputs",
            image,
            "/bin/bash",
            "-c",
            "sh predict.sh",
        ]
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - t0
            return RunResult(
                False,
                f"Docker inference timed out after {timeout_s}s. Check GPU/container setup and retry.",
                elapsed,
            )
    elif mode == "singularity":
        sif = os.environ.get("SUPREM_SIF_PATH", "").strip()
        if not sif or not Path(sif).exists():
            return RunResult(
                False,
                "SUPREM_SIF_PATH must point to an existing suprem_final.sif when using Singularity.",
                time.perf_counter() - t0,
            )
        argv = [
            "singularity",
            "run",
            "--nv",
            "-B",
            f"{inp}:/workspace/inputs",
            "-B",
            f"{out}:/workspace/outputs",
            sif,
        ]
        env = os.environ.copy()
        env.setdefault("SINGULARITYENV_CUDA_VISIBLE_DEVICES", gpu_device)
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - t0
            return RunResult(
                False,
                f"Singularity inference timed out after {timeout_s}s. Check GPU/container setup and retry.",
                elapsed,
            )
    else:
        return RunResult(False, "Unknown inference backend.", time.perf_counter() - t0)

    elapsed = time.perf_counter() - t0
    tail = ""
    if proc.stderr:
        tail = proc.stderr[-4000:]
    elif proc.stdout:
        tail = proc.stdout[-4000:]
    label = "Docker" if mode == "docker" else "Singularity"
    if proc.returncode != 0:
        return RunResult(False, f"{label} exited with {proc.returncode}. Last output:\n{tail}", elapsed)
    return RunResult(True, "SuPreM inference finished.", elapsed)


async def run_suprem_async(
    *,
    inputs_dir: Path,
    outputs_dir: Path,
    gpu_device: str = "0",
    backend: Backend | None = None,
    docker_image_override: str | None = None,
) -> RunResult:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: run_suprem_sync(
            inputs_dir=inputs_dir,
            outputs_dir=outputs_dir,
            gpu_device=gpu_device,
            backend=backend,
            docker_image_override=docker_image_override,
        ),
    )
