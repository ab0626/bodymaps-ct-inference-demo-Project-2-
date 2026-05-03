from __future__ import annotations

import asyncio
import gzip
import io
import os
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .evaluation import evaluate_case
from .inference_runner import inference_mode, run_suprem_async
from .model_registry import default_model_id, get_spec, list_models_public

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
MAX_UPLOAD_BYTES = int(float(os.environ.get("SUPREM_MAX_UPLOAD_MB", "320")) * 1024 * 1024)


def _work_root() -> Path:
    """Resolve live so tests can `monkeypatch.setenv` before importing/routing."""
    return Path(os.environ.get("SUPREM_WORK_DIR", str(BASE_DIR / "data"))).resolve()

app = FastAPI(title="SuPreM Web Demo")

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


class Job:
    def __init__(self, job_id: str, case_name: str, model_id: str) -> None:
        self.id = job_id
        self.case_name = case_name
        self.model_id = model_id
        self.status = "queued"
        self.message = ""
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: str | None = None
        self.error: str | None = None
        self.evaluation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "case_name": self.case_name,
            "model_id": self.model_id,
            "status": self.status,
            "message": self.message,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }
        if self.evaluation is not None:
            d["evaluation"] = self.evaluation
        return d


_jobs: dict[str, Job] = {}
_tasks: set[asyncio.Task] = set()


def _job_paths(job_id: str) -> tuple[Path, Path, Path]:
    root = _work_root() / "jobs" / job_id
    return root, root / "inputs", root / "outputs"


def _safe_name(name: str) -> str:
    base = Path(name).name
    out = "".join(c for c in base if c.isalnum() or c in "._-")[:120]
    return out or "upload"


def _copy_stream_limited(src: UploadFile, dest: Path, max_bytes: int) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with dest.open("wb") as f:
        while True:
            chunk = src.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(413, f"Upload exceeds limit of {max_bytes // (1024 * 1024)} MB.")
            f.write(chunk)
    return total


def _extract_zip_to_temp(zip_path: Path) -> Path:
    tmp = zip_path.parent / f"{zip_path.stem}_extracted"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(tmp)
    return tmp


def _find_ct_volume(root: Path) -> Path:
    cands: list[Path] = []
    for p in list(root.rglob("*.nii.gz")) + list(root.rglob("*.nii")):
        if "__MACOSX" in p.parts or p.name.startswith("._"):
            continue
        name = p.name.lower()
        if name in ("ct.nii.gz", "ct.nii"):
            cands.append(p)
    if not cands:
        for p in list(root.rglob("*.nii.gz")) + list(root.rglob("*.nii")):
            if "__MACOSX" in p.parts or p.name.startswith("._"):
                continue
            cands.append(p)
    if not cands:
        raise HTTPException(400, "No NIfTI volume found in upload. Expected ct.nii.gz or a .nii/.nii.gz file.")
    return min(cands, key=lambda x: len(x.parts))


def _write_ct_as_nii_gz(src: Path, dest_ct_nii_gz: Path) -> None:
    """SuPreM expects ct.nii.gz under each case folder (see HF model card)."""
    dest_ct_nii_gz.parent.mkdir(parents=True, exist_ok=True)
    name = src.name.lower()
    if name.endswith(".nii.gz"):
        shutil.copy2(src, dest_ct_nii_gz)
        return
    if name.endswith(".nii"):
        with src.open("rb") as raw:
            data = raw.read()
        with gzip.open(dest_ct_nii_gz, "wb", compresslevel=6) as gz:
            gz.write(data)
        return
    shutil.copy2(src, dest_ct_nii_gz)


def _stage_upload_to_inputs(staged_path: Path, inputs_dir: Path, suggested_case: str) -> str:
    if zipfile.is_zipfile(staged_path):
        extracted = _extract_zip_to_temp(staged_path)
        ct = _find_ct_volume(extracted)
        rel = ct.relative_to(extracted).parts
        rel_parent = rel[0] if len(rel) > 1 else None
        case_name = rel_parent if rel_parent and rel_parent != ct.name else suggested_case
        case_name = _safe_name(case_name)
        case_dir = inputs_dir / case_name
        _write_ct_as_nii_gz(ct, case_dir / "ct.nii.gz")
        shutil.rmtree(extracted, ignore_errors=True)
        return case_name

    suf = staged_path.suffix.lower()
    if suf == ".gz" and staged_path.name.lower().endswith(".nii.gz"):
        case_name = _safe_name(suggested_case)
        case_dir = inputs_dir / case_name
        _write_ct_as_nii_gz(staged_path, case_dir / "ct.nii.gz")
        return case_name
    if suf == ".nii":
        case_name = _safe_name(suggested_case)
        case_dir = inputs_dir / case_name
        _write_ct_as_nii_gz(staged_path, case_dir / "ct.nii.gz")
        return case_name
    raise HTTPException(400, "Unsupported file type. Upload a .nii, .nii.gz, or .zip (NIfTI or BodyMaps layout).")


def _extract_reference_zip(reference_staged: Path, extract_root: Path) -> None:
    if not reference_staged.exists():
        return
    if not zipfile.is_zipfile(reference_staged):
        raise HTTPException(
            400,
            "Reference uploads must be a .zip containing segmentations/**/*.nii.gz (BodyMaps-style masks).",
        )
    if extract_root.exists():
        shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True)
    with zipfile.ZipFile(reference_staged, "r") as zf:
        zf.extractall(extract_root)


def _run_evaluation_for_job(job: Job, outputs_dir: Path, reference_root: Path) -> None:
    pred_case_dir = outputs_dir / job.case_name
    try:
        job.evaluation = evaluate_case(pred_case_dir=pred_case_dir, reference_root=reference_root)
    except Exception as exc:  # noqa: BLE001
        job.evaluation = {"status": "error", "detail": str(exc)}


async def _run_job(job_id: str) -> None:
    job = _jobs.get(job_id)
    if not job:
        return
    root, inputs_dir, outputs_dir = _job_paths(job_id)
    job.status = "running"
    gpu = os.environ.get("SUPREM_GPU_DEVICE", "0")
    try:
        spec = get_spec(job.model_id)
        pretty = spec.name
        job.message = f"Running model “{pretty}” (this may take minutes on GPU backends)…"
        result = await run_suprem_async(
            inputs_dir=inputs_dir,
            outputs_dir=outputs_dir,
            gpu_device=gpu,
            backend=spec.backend,
            docker_image_override=spec.docker_image,
        )
        if not result.ok:
            job.status = "failed"
            job.error = result.message
            job.message = "Inference failed."
        else:
            job.status = "completed"
            job.message = f"{pretty} · done in {result.elapsed_s:.1f}s. Download segmentations below."
            ref_root = root / "reference_extracted"
            if ref_root.exists() and any(ref_root.iterdir()):
                _run_evaluation_for_job(job, outputs_dir, ref_root)
                if isinstance(job.evaluation, dict) and job.evaluation.get("status") == "ok":
                    md = job.evaluation.get("mean_dice")
                    job.message += f" Mean Dice vs reference: {md:.4f}." if isinstance(md, (float, int)) else ""
                elif isinstance(job.evaluation, dict):
                    job.message += " Reference comparison finished with warnings—see evaluation details."
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error = str(exc)
        job.message = "Inference failed."
    job.finished_at = datetime.now(timezone.utc).isoformat()


def _schedule_job(job_id: str) -> None:
    task = asyncio.create_task(_run_job(job_id))

    def _done(t: asyncio.Task) -> None:
        _tasks.discard(t)
        if err := t.exception():
            j = _jobs.get(job_id)
            if j and j.status == "running":
                j.status = "failed"
                j.error = str(err)
                j.finished_at = datetime.now(timezone.utc).isoformat()

    task.add_done_callback(_done)
    _tasks.add(task)


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    path = FRONTEND_DIR / "index.html"
    if not path.exists():
        return HTMLResponse("<p>Frontend missing.</p>")
    return FileResponse(path)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/meta")
def api_meta() -> dict[str, Any]:
    """Server mode and limits (useful when recording demos or debugging Docker binds)."""
    return {
        "inference_mode": inference_mode(),
        "default_model_id": default_model_id(),
        "suprem_docker_image": os.environ.get("SUPREM_DOCKER_IMAGE", "qchen99/suprem:v1"),
        "gpu_device": os.environ.get("SUPREM_GPU_DEVICE", "0"),
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
        "work_dir": str(_work_root()),
        "supports_per_job_model": True,
    }


@app.get("/api/models")
def api_models() -> dict[str, Any]:
    """Registered inference backends; UI can let users compare runners (mock vs SuPreM, etc.)."""
    return {"default_model_id": default_model_id(), "models": list_models_public()}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> JSONResponse:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return JSONResponse(job.to_dict())


@app.get("/api/jobs/{job_id}/outputs")
def job_output_manifest(job_id: str) -> JSONResponse:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    if job.status != "completed":
        raise HTTPException(409, "Outputs are ready only after the job completes.")

    _, _, outputs_dir = _job_paths(job_id)
    rows: list[dict[str, int | str]] = []
    for path in sorted(outputs_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(outputs_dir).as_posix()
            rows.append({"path": rel, "size_bytes": path.stat().st_size})

    return JSONResponse({"case_name": job.case_name, "files": rows})


@app.post("/api/jobs/{job_id}/evaluate")
async def evaluate_job_endpoint(job_id: str, reference: UploadFile = File(...)) -> JSONResponse:
    """Upload reference segmentations ZIP and compute Dice vs completed prediction masks."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    if job.status != "completed":
        raise HTTPException(409, "Wait for inference to finish before evaluation.")

    root, _, outputs_dir = _job_paths(job_id)
    ref_zip_path = root / "reference_upload" / "reference_from_client.zip"
    ref_extract = root / "reference_extracted"
    _copy_stream_limited(reference, ref_zip_path, MAX_UPLOAD_BYTES)
    _extract_reference_zip(ref_zip_path, ref_extract)
    _run_evaluation_for_job(job, outputs_dir, ref_extract)
    if isinstance(job.evaluation, dict) and job.evaluation.get("status") == "ok":
        md = job.evaluation.get("mean_dice")
        suffix = f" Mean Dice vs reference: {md:.4f}." if isinstance(md, (float, int)) else ""
        job.message = (job.message or "") + suffix
    return JSONResponse(job.to_dict())


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    case_name: str | None = Form(None),
    model_id: str | None = Form(None),
    reference: UploadFile | None = File(None),
) -> JSONResponse:
    job_id = uuid.uuid4().hex
    root, inputs_dir, outputs_dir = _job_paths(job_id)
    if root.exists():
        shutil.rmtree(root)
    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    chosen_model = (model_id or "").strip() or default_model_id()
    try:
        spec = get_spec(chosen_model)
    except KeyError:
        raise HTTPException(400, f"Unknown model_id: {chosen_model}. Use GET /api/models.")
    avail = next((m for m in list_models_public() if m["id"] == chosen_model), None)
    if avail and avail.get("available") is False:
        raise HTTPException(400, avail.get("unavailable_reason", "Selected model is not available on this server."))

    raw_name = file.filename or "ct.nii.gz"
    suggested = case_name.strip() if case_name and case_name.strip() else Path(raw_name).stem.replace(".nii", "")
    suggested = _safe_name(suggested) or "case"

    staged = root / "upload_staging" / _safe_name(raw_name)
    _copy_stream_limited(file, staged, MAX_UPLOAD_BYTES)

    ref_zip_path = root / "reference_upload" / "reference.zip"
    ref_extract = root / "reference_extracted"
    try:
        if reference and getattr(reference, "filename", None):
            _copy_stream_limited(reference, ref_zip_path, MAX_UPLOAD_BYTES)
            _extract_reference_zip(ref_zip_path, ref_extract)
        try:
            final_case = _stage_upload_to_inputs(staged, inputs_dir, suggested)
        finally:
            shutil.rmtree(staged.parent, ignore_errors=True)

        job = Job(job_id, final_case, spec.id)
        _jobs[job_id] = job
        _schedule_job(job_id)
        return JSONResponse(job.to_dict(), status_code=202)
    except HTTPException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


@app.get("/api/jobs/{job_id}/download")
def download_job(job_id: str) -> StreamingResponse:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    if job.status != "completed":
        raise HTTPException(409, "Job is not completed yet.")
    _, _, outputs_dir = _job_paths(job_id)
    if not outputs_dir.exists() or not any(outputs_dir.iterdir()):
        raise HTTPException(404, "No output files.")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in outputs_dir.rglob("*"):
            if path.is_file():
                arc = path.relative_to(outputs_dir).as_posix()
                zf.write(path, arcname=arc)
    buf.seek(0)
    filename = f"{job.model_id}_{job.case_name}_{job_id[:8]}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def main() -> None:
    """Entry point for `python -m app.main` development server."""
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("SUPREM_PORT", "8000")), reload=False)


if __name__ == "__main__":
    main()
