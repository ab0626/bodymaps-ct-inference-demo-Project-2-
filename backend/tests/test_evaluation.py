from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np

from app.evaluation import dice_binary, evaluate_case


def test_dice_identical_overlap():
    rng = np.random.default_rng(0)
    x = rng.random((5, 6, 7)) > 0.7
    d = dice_binary(x, x)
    assert d > 0.999


def test_dice_disjoint():
    a = np.zeros((4, 4, 4), dtype=bool)
    b = np.zeros((4, 4, 4), dtype=bool)
    a[0, 0, 0] = True
    b[-1, -1, -1] = True
    d = dice_binary(a, b)
    assert d < 0.01


def test_evaluate_case_matching_masks(tmp_path: Path):
    aff = np.eye(4, dtype=np.float32)
    vol = np.zeros((12, 12, 12), dtype=np.float32)
    vol[4:10, 4:10, 4:10] = 1.0

    pred_case = tmp_path / "case_a" / "segmentations"
    pred_case.mkdir(parents=True)
    nib.save(nib.Nifti1Image(vol, aff), pred_case / "liver.nii.gz")

    ref_root = tmp_path / "ref_bundle" / "any_case" / "segmentations"
    ref_root.mkdir(parents=True)
    nib.save(nib.Nifti1Image(vol.copy(), aff), ref_root / "liver.nii.gz")

    out = evaluate_case(pred_case_dir=pred_case.parent, reference_root=tmp_path / "ref_bundle")
    assert out["status"] == "ok"
    assert out["mean_dice"] is not None and out["mean_dice"] > 0.999
    assert len(out["structures"]) == 1
    assert out["structures"][0]["structure"] == "liver.nii.gz"
