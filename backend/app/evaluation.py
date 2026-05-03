"""Dice / overlap metrics between predicted and reference segmentations (same grid)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np


def _binarize(data: np.ndarray) -> np.ndarray:
    return np.asarray(data, dtype=np.float64) > 0.5


def dice_binary(pred: np.ndarray, ref: np.ndarray, eps: float = 1e-8) -> float:
    p = pred.astype(bool).ravel()
    r = ref.astype(bool).ravel()
    inter = np.logical_and(p, r).sum(dtype=np.float64)
    return float((2.0 * inter + eps) / (p.sum() + r.sum() + eps))


def _seg_files_under(root: Path) -> dict[str, Path]:
    """Map basename (e.g. liver.nii.gz) -> path for files under any .../segmentations/ tree."""
    out: dict[str, Path] = {}
    for p in root.rglob("*.nii.gz"):
        if "__MACOSX" in p.parts or p.name.startswith("._"):
            continue
        parts_lower = [x.lower() for x in p.parts]
        if "segmentations" not in parts_lower:
            continue
        key = p.name.lower()
        if key not in out:
            out[key] = p
    return out


def evaluate_case(
    *,
    pred_case_dir: Path,
    reference_root: Path,
) -> dict[str, Any]:
    """
    Compare prediction `pred_case_dir/segmentations/*.nii.gz` to reference tree
    (BodyMaps-style zips: `{case}/segmentations/*.nii.gz`).
    """
    pred_seg_dir = pred_case_dir / "segmentations"
    if not pred_seg_dir.is_dir():
        return {"status": "error", "detail": f"No prediction segmentations dir: {pred_seg_dir}"}

    pred_map = _seg_files_under(pred_case_dir)
    ref_map = _seg_files_under(reference_root)

    names = sorted(set(pred_map.keys()) & set(ref_map.keys()))
    if not names:
        return {
            "status": "error",
            "detail": "No overlapping segmentations/*.nii.gz names between prediction and reference.",
        }

    rows: list[dict[str, Any]] = []
    dices: list[float] = []

    for name in names:
        pp = pred_map[name]
        rp = ref_map[name]
        try:
            p_img = nib.load(pp)
            r_img = nib.load(rp)
        except Exception as exc:  # noqa: BLE001
            rows.append({"structure": name, "dice": None, "note": f"load error: {exc}"})
            continue

        p_shape = tuple(p_img.shape)
        r_shape = tuple(r_img.shape)
        if p_shape != r_shape:
            rows.append(
                {
                    "structure": name,
                    "dice": None,
                    "note": f"shape mismatch pred{p_shape} vs ref{r_shape}",
                }
            )
            continue

        pred_b = _binarize(np.asarray(p_img.dataobj))
        ref_b = _binarize(np.asarray(r_img.dataobj))
        d = dice_binary(pred_b, ref_b)
        dices.append(d)
        rows.append({"structure": name, "dice": d, "note": None})

    mean_dice = float(np.mean(dices)) if dices else None
    return {
        "status": "ok",
        "metric": "dice",
        "compared_structures": len(rows),
        "mean_dice": mean_dice,
        "structures": rows,
    }
