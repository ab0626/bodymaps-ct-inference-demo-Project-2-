# Demo runbook (screen recording)

Use this for a **polished ~90 second** take; stretch to **~2 minutes** only if you add Explorer unzip + label pan.

## Before you hit record

1. Close clutter (extra tabs, notifications).
2. Browser **full screen** (F11) or maximize.
3. Start the app in **mock** mode (amber banner = good for fast, reliable demo).  
   **Full instructions** (venv, first-time install): README **§ How to run smoothly**. Minimal copy-paste from **repo root**:

```powershell
$env:SUPREM_INFERENCE_MODE = "mock"
$env:SUPREM_WORK_DIR      = "$(Resolve-Path .\data)"
New-Item -ItemType Directory -Force -Path $env:SUPREM_WORK_DIR | Out-Null
Set-Location .\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

4. Open **http://127.0.0.1:8000/** and confirm the top banner says **MOCK**.

**Reference clips in repo (after you record):** save or replace **`media/demo-ui.mp4`** (browser) and **`media/demo-explorer.mp4`** (Explorer / BDMAP)—see **README** demo section.

**Files you need on disk**

- `BDMAP_00000338 (1).zip` (or any BodyMaps-style zip with `…/ct.nii.gz`).

---

## On-camera flow (~90s)

| Time | Do | Say (loose script) |
|------|----|--------------------|
| 0:00 | Point at **MOCK** banner | “This is a research prototype: upload CT, run segmentation, download masks. I’m in **mock** mode so the UI is fast and deterministic for the demo.” |
| 0:10 | **Model** stays **Mock** (or briefly show Docker option); optionally attach **reference masks ZIP** (same grid as preds for real Dice) | “Runs are **model-specific** via the registry—I’m on mock for speed; with real SuPreM on a GPU I’d pick **SuPreM (Docker)**. Reference ZIP enables quantitative **Dice** if shapes align.” |
| 0:20 | Optional case name `BDMAP_00000338` | “Optional case folder name matches the dataset layout.” |
| 0:30 | Pick `BDMAP_…zip` in CT drop zone → **Upload & run** | “I’m uploading the provided BDMAP CT bundle as a zip.” |
| 0:45 | **Status / polling** | “The server stages `case/ct.nii.gz`, then runs the chosen backend; production uses the HF `predict.sh` path.” |
| 1:00 | **Download** | “I download zipped `combined_labels` and per-structure masks.” |
| 1:10 | Scroll **Outputs in ZIP** + **Evaluation vs reference** (if you attached reference on the **same voxel grid**) | “I can verify filenames and—in a full study—Dice versus held-out atlas masks.” |
| 1:20 | One line closing | “See `README.md` for **`GET /api/models`**, Dice fields, and `scripts/suprem-docker-once.ps1` on GPU.” |

**Stop here** if you want a tight ~90s cut.

---

## Stretch ending (~2:00 total)

1. Open **File Explorer** → show the downloaded zip.
2. **Extract all…** to a folder.
3. Expand:

   - `{case}/segmentations/`
   - point at filenames: `aorta.nii.gz`, `liver.nii.gz`, …
   - optionally open `combined_labels.nii.gz` in your viewer if you use one.

**Say:** “After unzip, the mask names match the SuPreM output layout from the model card—`combined_labels` plus one NIfTI per structure under `segmentations/`.”

---

## If something goes wrong (keep recording)

- **Upload error / 413:** mention upload cap (`SUPREM_MAX_UPLOAD_MB` in `README.md`).
- **Docker on your machine:** if you don’t have working GPU passthrough, **do not** force live Docker in the video—stay on **mock** and verbally point to **`README.md` + GPU host**.

---

## One clean reset between takes

Refresh the page; optional: restart uvicorn so job IDs restart (not required).

---

## Optional voiceover cheat sheet (one breath)

“We upload anonymized abdominal CT—here as a BDMAP zip. The demo server stages `ct.nii.gz`, runs segmentation, polls status, then offers a downloadable zip listing every label file. Mock mode proves the UX; switching to Docker and SuPreM on a GPU workstation runs the real model exactly as documented on Hugging Face.”
