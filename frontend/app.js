const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const uploadForm = document.getElementById("upload-form");
const statusPanel = document.getElementById("status-panel");
const statusText = document.getElementById("status-text");
const downloadLink = document.getElementById("download-link");
const submitBtn = document.getElementById("submit-btn");
const meter = document.querySelector(".meter");
const modeBanner = document.getElementById("mode-banner");
const outputManifest = document.getElementById("output-manifest");
const outputList = document.getElementById("output-list");
const jobIdEl = document.getElementById("job-id");
const modelSelect = document.getElementById("model-select");
const referenceInput = document.getElementById("reference-input");
const evaluationPanel = document.getElementById("evaluation-panel");
const evaluationBody = document.getElementById("evaluation-body");
const lateEvalPanel = document.getElementById("late-eval-panel");
const evalZipInput = document.getElementById("eval-zip");
const evalBtn = document.getElementById("eval-btn");
const evalMsg = document.getElementById("eval-msg");

let lastJobId = null;

const setStatusVisible = (visible) => {
  statusPanel.classList.toggle("hidden", !visible);
};

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(2)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

async function hydrateModels() {
  if (!modelSelect) return;
  try {
    const res = await fetch("/api/models");
    if (!res.ok) return;
    const data = await res.json();
    modelSelect.innerHTML = "";

    const models = data.models || [];
    for (const m of models) {
      const opt = document.createElement("option");
      opt.value = m.id;
      const tag = m.available ? "" : " (setup required)";
      opt.textContent = `${m.name}${tag}`;
      opt.disabled = !m.available;
      modelSelect.appendChild(opt);
    }

    const fallback = models.find((m) => m.available);
    if (data.default_model_id) {
      const defOpt = [...modelSelect.options].find((o) => o.value === data.default_model_id && !o.disabled);
      if (defOpt) modelSelect.value = data.default_model_id;
      else if (fallback) modelSelect.value = fallback.id;
    } else if (fallback) modelSelect.value = fallback.id;
  } catch (_) {
    /* offline */
  }
}

async function hydrateBanner() {
  if (!modeBanner) return;
  try {
    const res = await fetch("/api/meta");
    if (!res.ok) return;
    const m = await res.json();
    const mode = String(m.inference_mode || "").toLowerCase();

    modeBanner.classList.remove("hidden", "mode-mock", "mode-live", "mode-other");

    let label = "";
    if (mode === "mock") {
      modeBanner.classList.add("mode-mock");
      label = `Server default: MOCK · ${m.suprem_docker_image}. Per-job model choice can still select SuPreM (Docker) if GPU works. Upload cap ${m.max_upload_mb} MB.`;
    } else if (mode === "docker") {
      modeBanner.classList.add("mode-live");
      label = `Server default: Docker · ${m.suprem_docker_image} · GPU ${m.gpu_device}. Default runner id “${m.default_model_id || "—"}”. Upload cap ${m.max_upload_mb} MB.`;
    } else if (mode === "singularity") {
      modeBanner.classList.add("mode-other");
      label = `Server default: Singularity (.sif) · GPU ${m.gpu_device}. Default runner “${m.default_model_id || "—"}”. Upload cap ${m.max_upload_mb} MB.`;
    } else {
      modeBanner.classList.add("mode-other");
      label = `Inference default: ${mode || "unknown"}`;
    }

    modeBanner.textContent = label;
  } catch (_) {
    /* ignore */
  }
}

function resetManifest() {
  outputManifest?.classList.add("hidden");
  outputList.innerHTML = "";
  jobIdEl?.classList.add("hidden");
  if (jobIdEl) jobIdEl.textContent = "";
  evaluationPanel?.classList.add("hidden");
  if (evaluationBody) evaluationBody.innerHTML = "";
  lateEvalPanel?.classList.add("hidden");
  if (evalMsg) {
    evalMsg.classList.add("hidden");
    evalMsg.textContent = "";
  }
  if (evalZipInput) evalZipInput.value = "";
}

function renderEvaluation(job) {
  if (!evaluationPanel || !evaluationBody) return;
  const ev = job.evaluation;
  if (!ev) {
    evaluationPanel.classList.add("hidden");
    return;
  }

  evaluationPanel.classList.remove("hidden");

  if (ev.status === "error") {
    evaluationBody.innerHTML = `<p class="muted small"><strong>Evaluation error:</strong> ${escapeHtml(String(ev.detail || "unknown"))}</p>`;
    return;
  }

  if (ev.status !== "ok") {
    evaluationBody.innerHTML = `<p class="muted small">${escapeHtml(JSON.stringify(ev))}</p>`;
    return;
  }

  const mean = ev.mean_dice != null ? Number(ev.mean_dice).toFixed(4) : "—";
  const rows = (ev.structures || [])
    .map((r) => {
      const d = r.dice == null ? "—" : Number(r.dice).toFixed(4);
      const note = r.note ? escapeHtml(String(r.note)) : "";
      return `<tr><td>${escapeHtml(String(r.structure))}</td><td>${d}</td><td class="muted small">${note}</td></tr>`;
    })
    .join("");

  evaluationBody.innerHTML = `
    <p class="evaluation-meta">Mean Dice (overlapping structures): ${mean}</p>
    <table>
      <thead><tr><th>Structure</th><th>Dice</th><th>Note</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

async function fillOutputManifest(jobId) {
  if (!outputManifest || !outputList) return;
  const res = await fetch(`/api/jobs/${jobId}/outputs`);
  if (!res.ok) return;
  const data = await res.json();
  outputList.innerHTML = "";
  for (const row of data.files || []) {
    const li = document.createElement("li");
    const path = typeof row.path === "string" ? row.path : "";
    const sz = typeof row.size_bytes === "number" ? formatBytes(row.size_bytes) : "?";
    li.textContent = `${path}  ·  ${sz}`;
    outputList.appendChild(li);
  }
  outputManifest.classList.remove("hidden");
}

hydrateModels().then(() => hydrateBanner());

dropZone?.addEventListener("click", () => fileInput?.click());

["dragenter", "dragover"].forEach((evt) => {
  dropZone?.addEventListener(evt, (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
});

["dragleave", "dragend"].forEach((evt) => {
  dropZone?.addEventListener(evt, () => dropZone.classList.remove("dragover"));
});

dropZone?.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  if (e.dataTransfer?.files?.length) {
    fileInput.files = e.dataTransfer.files;
    refreshDropHint();
  }
});

fileInput?.addEventListener("change", refreshDropHint);

function refreshDropHint() {
  const file = fileInput?.files?.[0];
  if (!file || !dropZone) return;
  const hint = dropZone.querySelector(".drop-title");
  if (hint) {
    hint.textContent = file.name;
  }
}

uploadForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = fileInput?.files?.[0];
  if (!file) {
    alert("Choose a ZIP or NIfTI volume first.");
    return;
  }
  resetManifest();
  const fd = new FormData();
  fd.append("file", file);
  if (modelSelect?.value) fd.append("model_id", modelSelect.value);
  const caseNameEl = document.getElementById("case-name");
  if (caseNameEl?.value?.trim()) {
    fd.append("case_name", caseNameEl.value.trim());
  }
  const ref = referenceInput?.files?.[0];
  if (ref) fd.append("reference", ref);

  submitBtn.disabled = true;
  downloadLink.classList.add("hidden");
  downloadLink.removeAttribute("href");
  setStatusVisible(true);
  statusText.textContent = "Uploading…";
  meter.classList.remove("hidden");

  try {
    const res = await fetch("/api/jobs", { method: "POST", body: fd });
    if (!res.ok) {
      throw new Error(await res.text());
    }
    const payload = await res.json();
    lastJobId = payload.id;
    if (jobIdEl) {
      jobIdEl.textContent = `Job id · ${payload.id} · model · ${payload.model_id || "—"}`;
      jobIdEl.classList.remove("hidden");
    }
    const done = await pollJob(payload.id);
    renderEvaluation(done);
    lateEvalPanel?.classList.remove("hidden");
  } catch (err) {
    statusText.textContent = `Could not start job: ${err.message || err}`;
    meter.classList.add("hidden");
  } finally {
    submitBtn.disabled = false;
  }
});

evalBtn?.addEventListener("click", async () => {
  if (!lastJobId) return;
  const z = evalZipInput?.files?.[0];
  if (!z) {
    alert("Choose a reference .zip first.");
    return;
  }
  evalBtn.disabled = true;
  if (evalMsg) {
    evalMsg.classList.remove("hidden");
    evalMsg.textContent = "Computing…";
  }
  try {
    const fd = new FormData();
    fd.append("reference", z);
    const res = await fetch(`/api/jobs/${lastJobId}/evaluate`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    const job = await res.json();
    renderEvaluation(job);
    if (evalMsg) evalMsg.textContent = "Updated.";
  } catch (err) {
    if (evalMsg) evalMsg.textContent = `Failed: ${err.message || err}`;
  } finally {
    evalBtn.disabled = false;
  }
});

async function pollJob(jobId) {
  statusText.textContent = "Queued — segmentation will start shortly…";
  meter.classList.remove("hidden");

  await new Promise((resolve) => setTimeout(resolve, 250));

  /** @type {Record<string, unknown> | null} */
  let finished = null;

  while (true) {
    const res = await fetch(`/api/jobs/${jobId}`);
    if (!res.ok) throw new Error("Lost job handle.");
    const job = await res.json();
    const label = `${job.case_name ? `${job.case_name} · ` : ""}${job.status}`;
    statusText.textContent = job.message ? `${label} — ${job.message}` : `${label} — updating…`;

    if (job.status === "completed") {
      finished = job;
      break;
    }
    if (job.status === "failed") {
      meter.classList.add("hidden");
      throw new Error(job.error || job.message || "Inference failed.");
    }
    await new Promise((resolve) => setTimeout(resolve, 700));
  }

  meter.classList.add("hidden");
  const cn = /** @type {{ case_name?: string }} */ (finished).case_name || "case";
  statusText.textContent = `Complete (${cn}) — download the ZIP, then inspect masks (and Dice table if reference was provided).`;

  downloadLink.classList.remove("hidden");
  downloadLink.href = `/api/jobs/${jobId}/download`;
  downloadLink.download = `${jobId}.zip`;

  try {
    await fillOutputManifest(jobId);
  } catch (_) {
    /* optional */
  }

  return /** @type {Record<string, unknown>} */ (finished);
}
