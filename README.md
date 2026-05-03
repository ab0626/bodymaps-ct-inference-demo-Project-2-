# SuPreM web demo · BodyMaps (Project 2)

Web app: upload abdominal **CT** (`zip` / `.nii.gz`), pick a **model runner** (mock or **SuPreM** via Docker/Singularity — [Hugging Face: qicq1c/SuPreM](https://huggingface.co/qicq1c/SuPreM)), optionally compare to **reference masks** with **Dice**. Similar in spirit to [TotalSegmentator’s web demo](https://totalsegmentator.com/); GPU path uses SuPreM’s **`predict.sh`**.

**Disclaimer:** Research prototype only — not for diagnosis, clinical use, or PHI. Use **anonymized** data only.

---

## Contents

- [How to run smoothly](#how-to-run-smoothly) — **start here**
- [Demo videos](#demo-videos-submission-assets)
- [Repository layout](#repository-layout)
- [Configuration (environment variables)](#configuration-environment-variables)
- [Docker & Singularity (real inference)](#docker--singularity-real-inference)
- [Models, evaluation, API](#models--evaluation-api)
- [Screen recording checklist](#screen-recording-checklist)
- [Troubleshooting](#troubleshooting)
- [Citation & compliance](#citation--compliance)

---

## How to run smoothly

### 0 · One-time setup

1. Open **PowerShell**.
2. Go to the repo root (the folder that contains `backend`, `frontend`, `media`):

   ```powershell
   cd "C:\path\to\Web based application for AI inference"
   ```

3. **Recommended:** use a virtual environment so installs don’t clash with other Python tools:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install Python dependencies (from repo root, still in the venv):

   ```powershell
   python -m pip install -U pip
   python -m pip install -r backend\requirements.txt
   ```

### 1 · Run in **mock mode** (fast, no GPU — best for demos & local dev)

Mock mode writes small placeholder segmentations so the **full UI flow** works without Docker or a GPU.

```powershell
# Still at repo root; venv activated
$env:SUPREM_INFERENCE_MODE = "mock"
$env:SUPREM_WORK_DIR      = "$(Resolve-Path .\data)"
New-Item -ItemType Directory -Force -Path $env:SUPREM_WORK_DIR | Out-Null

Set-Location .\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Then:**

1. Open a browser: **http://127.0.0.1:8000**
2. Confirm the **amber banner** mentions **MOCK**.
3. Upload a BodyMaps-style ZIP (e.g. `BDMAP_…zip` with `…/ct.nii.gz`) or a `.nii.gz` CT.
4. Click **Upload & run** → wait for completion → **Download** the ZIP.

**Stop the server:** press `Ctrl+C` in the terminal.

**Port 8000 already in use:** use another port:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Then open **http://127.0.0.1:8010** instead.

### 2 · Run with **Docker / SuPreM** (real model, needs GPU passthrough)

Only after **Docker Desktop** is running and **`docker version`** shows **Server**, and you can run GPU containers (e.g. **`nvidia-smi`** inside a CUDA test container). See [§ Docker & Singularity](#docker--singularity-real-inference) below.

Set `SUPREM_INFERENCE_MODE=docker` (this is also the default if you omit it), same `SUPREM_WORK_DIR` pattern, then `uvicorn` as in step 1.

### 3 · Run automated **tests**

From **`backend`** (venv on):

```powershell
Set-Location .\backend
powershell -ExecutionPolicy Bypass -File .\scripts\run_tests.ps1
```

Or manually (avoids broken **global** pytest plugins on some machines):

```powershell
Set-Location .\backend
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -m pytest tests -v
```

---

## Demo videos (submission assets)

### Files in `media/`

| File | What it shows |
|------|----------------|
| [`demo-ui.mp4`](./media/demo-ui.mp4) | Browser: upload → status → download |
| [`demo-explorer.mp4`](./media/demo-explorer.mp4) | File Explorer: `BDMAP…`, `combined_labels`, `segmentations` |

**Open in browser / editor**

- [Browser workflow (MP4)](./media/demo-ui.mp4)
- [Explorer — masks (MP4)](./media/demo-explorer.mp4)

**Inline playback** (if your Markdown host allows `<video>`):

<video src="./media/demo-ui.mp4" controls width="720"></video>

<video src="./media/demo-explorer.mp4" controls width="720"></video>

Replace these files under **`media/`** if you re-record. Very large files may be better on [Git LFS](https://git-lfs.com/) or an external host.

**Presenter script:** see **`DEMO_SCRIPT.md`**.

**Optional stills** (not required if you keep the Explorer clip): `media/screenshot-upload.png`, `media/screenshot-results.png`.

---

## Repository layout

| Path | Purpose |
|------|---------|
| `media/` | `demo-ui.mp4`, `demo-explorer.mp4` |
| `backend/app/main.py` | FastAPI app (jobs, models, evaluation) |
| `backend/app/model_registry.py` | Registered runners |
| `backend/app/evaluation.py` | Dice vs reference masks |
| `backend/app/inference_runner.py` | Mock / Docker / Singularity execution |
| `backend/tests/` | Pytest suite |
| `frontend/` | Static UI (`/static`) |
| `scripts/suprem-docker-once.ps1` | One-off SuPreM container run (HF-aligned) |
| `scripts/check-environment.ps1` | Quick Docker / Python smoke check |
| `backend/scripts/run_tests.ps1` | Pytest runner |
| `data/` | Writable job data (gitignored) |
| `DEMO_SCRIPT.md` | Recording timings & voiceover |

Output layout matches SuPreM / BodyMaps: **`{case}/combined_labels.nii.gz`** and **`{case}/segmentations/*.nii.gz`**.

---

## Configuration (environment variables)

| Variable | Default | When to change |
|----------|---------|----------------|
| `SUPREM_INFERENCE_MODE` | `docker` | Use **`mock`** for smooth local demos (no GPU). |
| `SUPREM_WORK_DIR` | `<repo>/data` | Must be a folder Docker can mount on your OS (Windows + Docker Desktop). |
| `SUPREM_DEFAULT_MODEL_ID` | derived from mode | Default **Model** in UI if not sent; e.g. `mock`, `suprem_docker`. |
| `SUPREM_GPU_DEVICE` | `0` | Second GPU → `1`, etc. |
| `SUPREM_DOCKER_IMAGE` | `qchen99/suprem:v1` | Override only if you mirror another tag. |
| `SUPREM_DOCKER_MEMORY` | `128G` | Lower if your Docker engine cap is smaller. |
| `SUPREM_INFERENCE_TIMEOUT_S` | `1800` | Fail jobs that hang (no GPU, stuck container). |
| `SUPREM_SIF_PATH` | *(empty)* | Linux Singularity: path to `suprem_final.sif`. |
| `SUPREM_MAX_UPLOAD_MB` | `320` | Max size per uploaded file field. |

---

## Docker & Singularity (real inference)

### Prerequisites

- **Python 3.9+** (3.10+ recommended).
- **Mock:** no Docker, no GPU.
- **Docker path:** Docker Desktop **Linux** engine, **NVIDIA** available **inside** containers (WSL2 + drivers — see NVIDIA + Docker docs).
- **Singularity:** Linux + `SUPREM_SIF_PATH` pointing at a valid `.sif`.

### Web UI with Docker

```powershell
cd "…\repo\backend"
$dataDir = Join-Path (Resolve-Path "..") "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$env:SUPREM_INFERENCE_MODE = "docker"
$env:SUPREM_WORK_DIR      = "$dataDir"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Uploads are staged under `data/jobs/<id>/…` and mounted as `/workspace/inputs` and `/workspace/outputs` in the container ([HF layout](https://huggingface.co/qicq1c/SuPreM)). Runs can take **long** and need **VRAM**.

### One-shot CLI (prove the container before demoing the site)

Prepare **`inputs\{Case}\ct.nii.gz`** and an empty **`outputs`** directory, then from **repo root**:

```powershell
.\scripts\suprem-docker-once.ps1 `
  -InputsRoot "C:\path\to\inputs" `
  -OutputsRoot "C:\path\to\outputs"
```

Add **`-SkipPull`** if the image is already local.

### Singularity (Linux)

```bash
export SUPREM_INFERENCE_MODE=singularity
export SUPREM_SIF_PATH=/path/to/suprem_final.sif
export SUPREM_WORK_DIR=/path/to/repo/data
mkdir -p "$SUPREM_WORK_DIR"
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Models · evaluation · API

- **`GET /api/models`** — list runners (mock, SuPreM Docker, SuPreM Singularity if `.sif` exists).
- **`POST /api/jobs`** — form fields: **`file`** (required), optional **`model_id`**, **`case_name`**, **`reference`** (ZIP of `**/segmentations/*.nii.gz`). Per-job **`model_id`** overrides server `SUPREM_INFERENCE_MODE` for that request.
- **`POST /api/jobs/{id}/evaluate`** — attach reference ZIP later; fills **`evaluation`** (Dice) when pred/ref **share the same voxel grid** (mock vs full-res BodyMaps masks → expect shape warnings).
- **`GET /api/jobs/{id}`** — status, `model_id`, optional `evaluation`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| GET | `/api/meta` | Mode, defaults, limits, `work_dir` |
| GET | `/api/models` | Registry |
| POST | `/api/jobs` | Create job (multipart) |
| POST | `/api/jobs/{id}/evaluate` | Reference ZIP → Dice |
| GET | `/api/jobs/{id}` | Job JSON |
| GET | `/api/jobs/{id}/outputs` | File list + sizes |
| GET | `/api/jobs/{id}/download` | ZIP (`{model_id}_{case}_….zip`) |

---

## Screen recording checklist (~2 min)

| Step | Show |
|------|------|
| 1 | Full-screen browser, **MOCK** banner |
| 2 | **Model** = Mock · optional case name · BDMAP zip · **Upload & run** |
| 3 | Status / polling |
| 4 | **Download** · extract ZIP |
| 5 | Explorer: `{case}/segmentations/` + **`combined_labels`** |
| 6 | Say: real inference = **Docker + SuPreM** on a GPU host (or `suprem-docker-once.ps1`) |

**Windows nuance:** extracted `combined_labels.nii.gz` may look like **`combined_labels.nii`** with a “compressed” icon — still valid gzip+NIfTI for demos that only show filenames.

---

## Troubleshooting

| Problem | What to do |
|---------|------------|
| **`dockerDesktopLinuxEngine` / pipe errors** | Start **Docker Desktop**; wait until **`docker version`** shows **Server**. |
| **Port 8000 in use** | Use `--port 8010` (or any free port) and open that URL. |
| **`pip` / `numpy` conflicts** | Use the **venv** steps in [§ How to run](#how-to-run-smoothly); avoid mixing with Conda/global ML stacks. |
| **Job times out (Docker)** | No GPU or wrong drivers — use **mock** for UI proof; fix GPU, or raise `SUPREM_INFERENCE_TIMEOUT_S` for long runs. |
| **Dice “shape mismatch” everywhere** | Expected for **mock** vs full-res reference; use **SuPreM** predictions on the **same grid** as reference masks. |
| **Pytest crashes on import** | Run `run_tests.ps1` or set **`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`**. |
| **Explore host health** | `.\scripts\check-environment.ps1` |

---

## Citation & compliance

BodyMaps / developer interest: align with program expectations and contact **Prof. Zongwei Zhou** — [`zzhou82@jh.edu`](mailto:zzhou82@jh.edu). Cite **SuPreM** and follow licensing on [Hugging Face](https://huggingface.co/qicq1c/SuPreM).
