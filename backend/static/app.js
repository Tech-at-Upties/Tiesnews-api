const state = {
  selectedCandidate: null,
  sources: [],
  output: { items: [], events: [] },
  selectedOutputSourceId: "",
  timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
};

const els = {
  adminKey: document.querySelector("#adminKey"),
  toggleKey: document.querySelector("#toggleKey"),
  feedUrl: document.querySelector("#feedUrl"),
  sourceName: document.querySelector("#sourceName"),
  interval: document.querySelector("#interval"),
  reliability: document.querySelector("#reliability"),
  categories: document.querySelector("#categories"),
  detectForm: document.querySelector("#detectForm"),
  saveSource: document.querySelector("#saveSource"),
  clearForm: document.querySelector("#clearForm"),
  detectionResult: document.querySelector("#detectionResult"),
  sourceList: document.querySelector("#sourceList"),
  sourceSearch: document.querySelector("#sourceSearch"),
  sourceStatus: document.querySelector("#sourceStatus"),
  outputSource: document.querySelector("#outputSource"),
  outputPreview: document.querySelector("#outputPreview"),
  outputSummary: document.querySelector("#outputSummary"),
  healthStatus: document.querySelector("#healthStatus"),
  timeZoneStatus: document.querySelector("#timeZoneStatus"),
  messageBar: document.querySelector("#messageBar"),
  refreshSources: document.querySelector("#refreshSources"),
  refreshOutput: document.querySelector("#refreshOutput"),
  copyOutput: document.querySelector("#copyOutput"),
};

const savedKey = localStorage.getItem("geoAtlasAdminKey");
if (savedKey) {
  els.adminKey.value = savedKey;
}

els.timeZoneStatus.textContent = `Time zone: ${state.timeZone}`;

function adminHeaders() {
  const key = els.adminKey.value.trim();
  if (key) {
    localStorage.setItem("geoAtlasAdminKey", key);
  }
  return {
    "Content-Type": "application/json",
    "X-Admin-Key": key,
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || `Request failed with ${response.status}`);
  }
  return body;
}

function showMessage(message, type = "good") {
  els.messageBar.hidden = false;
  els.messageBar.className = `notice ${type}`;
  els.messageBar.textContent = message;
  window.clearTimeout(showMessage.timer);
  showMessage.timer = window.setTimeout(() => {
    els.messageBar.hidden = true;
  }, 5000);
}

function renderPanelError(target, error) {
  target.innerHTML = `<div class="empty">${escapeHtml(error.message || String(error))}</div>`;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatDate(value) {
  if (!value) return "never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    timeZone: state.timeZone,
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

function isTimestampKey(key) {
  return /(^|_)(at|time|date)$/.test(key) || key.endsWith("_at") || key.endsWith("_time") || key.endsWith("_date");
}

function localizeTimestamps(value, key = "") {
  if (Array.isArray(value)) {
    return value.map((item) => localizeTimestamps(item));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([entryKey, entryValue]) => [entryKey, localizeTimestamps(entryValue, entryKey)])
    );
  }
  if (typeof value === "string" && isTimestampKey(key)) {
    return formatDate(value);
  }
  return value;
}

function setBusy(button, busyText) {
  const originalText = button.textContent;
  button.textContent = busyText;
  button.disabled = true;
  return () => {
    button.textContent = originalText;
    button.disabled = false;
  };
}

async function checkHealth() {
  try {
    const data = await api("/health");
    const dbLabel = data.database === "ok" ? "DB ok" : "DB degraded";
    els.healthStatus.textContent = `${data.service}: ${dbLabel}`;
    els.healthStatus.className = `status ${data.database === "ok" ? "ok" : "warn"}`;
  } catch {
    els.healthStatus.textContent = "API unavailable";
    els.healthStatus.className = "status bad";
  }
}

els.toggleKey.addEventListener("click", () => {
  const showing = els.adminKey.type === "text";
  els.adminKey.type = showing ? "password" : "text";
  els.toggleKey.textContent = showing ? "Show" : "Hide";
  els.toggleKey.setAttribute("aria-label", showing ? "Show admin key" : "Hide admin key");
});

els.detectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  state.selectedCandidate = null;
  els.saveSource.disabled = true;
  els.detectionResult.innerHTML = `<div class="empty">Detecting feed metadata...</div>`;
  const done = setBusy(event.submitter || els.detectForm.querySelector("button[type='submit']"), "Detecting...");
  try {
    const result = await api("/api/v1/sources/detect", {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify({ url: els.feedUrl.value.trim(), fetch_sample_items: true }),
    });
    renderDetection(result);
    showMessage(`Detected ${result.candidates.length} feed candidate${result.candidates.length === 1 ? "" : "s"}.`);
  } catch (error) {
    renderPanelError(els.detectionResult, error);
    showMessage(error.message, "bad");
  } finally {
    done();
  }
});

function renderDetection(result) {
  if (!result.candidates.length) {
    els.detectionResult.innerHTML = `<div class="empty">No feed candidates found.</div>`;
    return;
  }
  state.selectedCandidate = result.candidates[0];
  els.saveSource.disabled = false;
  els.detectionResult.innerHTML = result.candidates
    .map((candidate, index) => renderCandidate(candidate, index))
    .join("");
}

function renderCandidate(candidate, index) {
  const items = candidate.latest_items
    .map((item) => `<li>${escapeHtml(item.title || "Untitled")} <span class="meta">${escapeHtml(formatDate(item.published_at))}</span></li>`)
    .join("");
  const active = state.selectedCandidate?.feed_url === candidate.feed_url || (!state.selectedCandidate && index === 0);
  return `
    <article class="candidate ${active ? "active" : ""}" data-feed-url="${escapeHtml(candidate.feed_url)}">
      <header>
        <div>
          <strong>${escapeHtml(candidate.title || candidate.feed_url)}</strong>
          <p class="meta">${escapeHtml(candidate.feed_type)} - score ${candidate.score} - ${escapeHtml(candidate.feed_url)}</p>
          <p class="meta">Site: ${escapeHtml(candidate.site_url || "unknown")} | Language: ${escapeHtml(candidate.language || "unknown")}</p>
        </div>
        <span class="pill ${active ? "good" : ""}">${active ? "Selected" : "Candidate"}</span>
      </header>
      ${items ? `<ol class="sample-list">${items}</ol>` : `<p class="meta">No sample items found.</p>`}
    </article>
  `;
}

els.detectionResult.addEventListener("click", (event) => {
  const candidateEl = event.target.closest(".candidate");
  if (!candidateEl) return;
  const feedUrl = candidateEl.dataset.feedUrl;
  const candidates = [...els.detectionResult.querySelectorAll(".candidate")].map((node) => node.dataset.feedUrl);
  const index = candidates.indexOf(feedUrl);
  const detectedCards = [...els.detectionResult.querySelectorAll(".candidate")];
  detectedCards.forEach((node) => node.classList.remove("active"));
  candidateEl.classList.add("active");
  const title = candidateEl.querySelector("strong")?.textContent || feedUrl;
  state.selectedCandidate = {
    feed_url: feedUrl,
    title,
  };
  els.saveSource.disabled = index === -1;
});

els.saveSource.addEventListener("click", async () => {
  if (!state.selectedCandidate) return;
  const done = setBusy(els.saveSource, "Saving...");
  try {
    const categories = els.categories.value
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    const source = await api("/api/v1/sources/rss", {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify({
        name: els.sourceName.value.trim() || state.selectedCandidate.title,
        feed_url: state.selectedCandidate.feed_url,
        fetch_interval_minutes: Number(els.interval.value || 30),
        reliability_score: Number(els.reliability.value || 0.7),
        enabled: true,
        category_scope: categories.length ? categories : null,
      }),
    });
    showMessage(`Saved source: ${source.name}`);
    await loadSources();
    selectOutputSource(source.id);
    await loadOutput(source.id);
  } catch (error) {
    renderPanelError(els.detectionResult, error);
    showMessage(error.message, "bad");
  } finally {
    done();
  }
});

els.clearForm.addEventListener("click", () => {
  state.selectedCandidate = null;
  els.feedUrl.value = "";
  els.sourceName.value = "";
  els.categories.value = "";
  els.detectionResult.innerHTML = `<div class="empty">No feed detected yet.</div>`;
  els.saveSource.disabled = true;
});

async function loadSources() {
  if (!els.adminKey.value.trim()) {
    els.sourceList.innerHTML = `<div class="empty">Enter a generated admin key to load sources.</div>`;
    return;
  }
  els.sourceList.innerHTML = `<div class="empty">Loading sources...</div>`;
  try {
    state.sources = await api("/api/v1/sources?include_archived=true", { headers: adminHeaders() });
    renderSources();
    updateOutputSourceOptions();
  } catch (error) {
    renderPanelError(els.sourceList, error);
    showMessage(error.message, "bad");
  }
}

function renderSources() {
  const query = els.sourceSearch.value.trim().toLowerCase();
  const status = els.sourceStatus.value;
  const sources = state.sources.filter((source) => {
    const haystack = `${source.name} ${source.feed_url} ${source.status}`.toLowerCase();
    return (!query || haystack.includes(query)) && (status === "all" || source.status === status);
  });
  if (!sources.length) {
    els.sourceList.innerHTML = `<div class="empty">No matching sources.</div>`;
    return;
  }
  els.sourceList.innerHTML = sources.map(renderSource).join("");
}

function renderSource(source) {
  return `
    <article class="source-card" data-source-id="${source.id}">
      <header>
        <div>
          <h3>${escapeHtml(source.name)}</h3>
          <p class="meta">${escapeHtml(source.feed_url)}</p>
        </div>
        <span class="pill ${source.status === "active" ? "good" : "warn"}">${escapeHtml(source.status)}</span>
      </header>
      <p class="meta">Last success: ${escapeHtml(formatDate(source.last_success_at))} | Reliability: ${source.reliability_score}</p>
      ${source.last_error ? `<p class="meta">Last error: ${escapeHtml(source.last_error)}</p>` : ""}
      <div class="controls">
        <button type="button" data-action="ingest">Run ingest</button>
        <button type="button" data-action="view">View output</button>
        <button type="button" data-action="archive" class="danger">Archive</button>
      </div>
    </article>
  `;
}

els.sourceList.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  const card = event.target.closest(".source-card");
  if (!button || !card) return;
  const sourceId = card.dataset.sourceId;
  try {
    if (button.dataset.action === "ingest") {
      const done = setBusy(button, "Running...");
      const result = await api(`/api/v1/sources/${sourceId}/ingest`, { method: "POST", headers: adminHeaders() });
      done();
      showMessage(`Ingestion ${result.job.status}: ${result.job.normalized_count} normalized items.`);
      await loadSources();
      selectOutputSource(sourceId);
      await loadOutput(sourceId);
    }
    if (button.dataset.action === "view") {
      selectOutputSource(sourceId);
      await loadOutput(sourceId);
    }
    if (button.dataset.action === "archive") {
      const done = setBusy(button, "Archiving...");
      await api(`/api/v1/sources/${sourceId}`, { method: "DELETE", headers: adminHeaders() });
      done();
      showMessage("Source archived.");
      if (state.selectedOutputSourceId === sourceId) {
        selectOutputSource("");
      }
      await loadSources();
      await loadOutput(state.selectedOutputSourceId);
    }
  } catch (error) {
    button.disabled = false;
    showMessage(error.message, "bad");
  }
});

function updateOutputSourceOptions() {
  const current = state.selectedOutputSourceId;
  els.outputSource.innerHTML = `<option value="">All sources</option>` + state.sources
    .map((source) => `<option value="${escapeHtml(source.id)}">${escapeHtml(source.name)}</option>`)
    .join("");
  els.outputSource.value = current;
}

function selectOutputSource(sourceId) {
  state.selectedOutputSourceId = sourceId || "";
  els.outputSource.value = state.selectedOutputSourceId;
}

async function loadOutput(sourceId = state.selectedOutputSourceId) {
  try {
    const suffix = sourceId ? `?source_id=${encodeURIComponent(sourceId)}` : "";
    state.output = await api(`/api/v1/public/export.json${suffix}`);
    els.outputPreview.textContent = JSON.stringify(localizeTimestamps(state.output), null, 2);
    els.outputSummary.textContent = `${state.output.items.length} items, ${state.output.events.length} events`;
  } catch (error) {
    state.output = { items: [], events: [] };
    els.outputPreview.textContent = JSON.stringify({ error: error.message }, null, 2);
    els.outputSummary.textContent = "Output failed to load.";
  }
}

els.sourceSearch.addEventListener("input", renderSources);
els.sourceStatus.addEventListener("change", renderSources);
els.outputSource.addEventListener("change", async () => {
  selectOutputSource(els.outputSource.value);
  await loadOutput(state.selectedOutputSourceId);
});
els.refreshSources.addEventListener("click", loadSources);
els.refreshOutput.addEventListener("click", () => loadOutput());
els.copyOutput.addEventListener("click", async () => {
  await navigator.clipboard.writeText(els.outputPreview.textContent);
  showMessage("Output JSON copied.");
});
els.adminKey.addEventListener("change", loadSources);

checkHealth();
loadSources();
loadOutput();
