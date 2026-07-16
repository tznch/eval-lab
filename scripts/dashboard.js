/** Unified lab filters — model, temperature, dataset, framework. */
(function () {
  const STORAGE_KEY = "llmLabFilters";
  let catalog = null;

  function defaultFilters() {
    return {
      models: catalog?.models?.slice() || [],
      temps: catalog?.temps?.slice() || [],
      dataset: "all",
      frameworks: catalog?.frameworks?.slice() || [],
    };
  }

  function loadFilters() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return defaultFilters();
      const saved = JSON.parse(raw);
      const d = defaultFilters();
      return {
        models: Array.isArray(saved.models) ? saved.models.filter((m) => d.models.includes(m)) : d.models,
        temps: Array.isArray(saved.temps) ? saved.temps.filter((t) => d.temps.includes(t)) : d.temps,
        dataset: saved.dataset === "all" || d.datasets.includes(saved.dataset) ? saved.dataset : "all",
        frameworks: Array.isArray(saved.frameworks)
          ? saved.frameworks.filter((f) => d.frameworks.includes(f))
          : d.frameworks,
      };
    } catch {
      return defaultFilters();
    }
  }

  function saveFilters(filters) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
  }

  function renderControls(filters) {
    const root = document.getElementById("lab-controls");
    if (!root || !catalog) return;

    const modelPills = catalog.models
      .map(
        (m) =>
          `<button type="button" class="pill${filters.models.includes(m) ? " active" : ""}" data-kind="model" data-value="${m}">${m}</button>`
      )
      .join("");

    const tempPills = catalog.temps
      .map((t) => {
        const label = t.replace(/^t/, "t=");
        return `<button type="button" class="pill${filters.temps.includes(t) ? " active" : ""}" data-kind="temp" data-value="${t}">${label}</button>`;
      })
      .join("");

    const fwPills = catalog.frameworks
      .map(
        (f) =>
          `<button type="button" class="pill${filters.frameworks.includes(f) ? " active" : ""}" data-kind="framework" data-value="${f}">${f}</button>`
      )
      .join("");

    const dsOptions = ['<option value="all">All tracks</option>']
      .concat(catalog.datasets.map((d) => `<option value="${d}"${filters.dataset === d ? " selected" : ""}>${d}</option>`))
      .join("");

    root.innerHTML = `
      <div class="lab-controls-inner">
        <div class="ctrl-row">
          <span class="ctrl-label">Model</span>
          <div class="pill-group" id="pills-model">${modelPills}</div>
        </div>
        <div class="ctrl-row">
          <span class="ctrl-label">Temp</span>
          <div class="pill-group" id="pills-temp">${tempPills}</div>
        </div>
        <div class="ctrl-row">
          <span class="ctrl-label">Track</span>
          <select id="filter-dataset" class="ctrl-select">${dsOptions}</select>
        </div>
        <div class="ctrl-row">
          <span class="ctrl-label">Framework</span>
          <div class="pill-group" id="pills-framework">${fwPills}</div>
        </div>
        <div class="ctrl-actions">
          <button type="button" class="ctrl-btn" id="filter-reset">Reset</button>
          <span class="ctrl-summary" id="filter-summary"></span>
        </div>
      </div>`;
  }

  function togglePill(filters, kind, value) {
    const key = kind === "model" ? "models" : kind === "temp" ? "temps" : "frameworks";
    const list = filters[key];
    const idx = list.indexOf(value);
    if (idx >= 0) {
      if (list.length > 1) list.splice(idx, 1);
    } else {
      list.push(value);
    }
  }

  function runVisible(filters, el) {
    const model = el.dataset.model;
    const temp = el.dataset.temp;
    const run = el.dataset.run;
    const dataset = el.dataset.dataset;
    const framework = el.dataset.framework;

    if (run) {
      const [m, t] = run.split(":");
      if (m && !filters.models.includes(m)) return false;
      if (t && !filters.temps.includes(t)) return false;
    } else {
      if (model && !filters.models.includes(model)) return false;
      if (temp && !filters.temps.includes(temp)) return false;
    }
    if (dataset && filters.dataset !== "all" && dataset !== filters.dataset) return false;
    if (framework && !filters.frameworks.includes(framework)) return false;
    return true;
  }

  function applyFilters(filters) {
    document.querySelectorAll("[data-run], [data-model], [data-dataset], [data-framework]").forEach((el) => {
      if (!el.dataset.run && !el.dataset.model && !el.dataset.dataset && !el.dataset.framework) return;
      el.classList.toggle("filtered-out", !runVisible(filters, el));
    });

    document.querySelectorAll("tr[data-dataset]").forEach((row) => {
      row.classList.toggle(
        "filtered-out",
        filters.dataset !== "all" && row.dataset.dataset !== filters.dataset
      );
    });

    const summary = document.getElementById("filter-summary");
    if (summary) {
      const parts = [
        filters.models.join(", ") || "—",
        filters.temps.map((t) => t.replace(/^t/, "t=")).join(", ") || "—",
        filters.dataset === "all" ? "all tracks" : filters.dataset,
      ];
      summary.textContent = `Showing: ${parts.join(" · ")}`;
    }
  }

  function bindEvents(filters) {
    document.getElementById("lab-controls")?.addEventListener("click", (e) => {
      const btn = e.target.closest(".pill");
      if (!btn) return;
      togglePill(filters, btn.dataset.kind, btn.dataset.value);
      saveFilters(filters);
      renderControls(filters);
      applyFilters(filters);
    });

    document.getElementById("filter-dataset")?.addEventListener("change", (e) => {
      filters.dataset = e.target.value;
      saveFilters(filters);
      applyFilters(filters);
    });

    document.getElementById("filter-reset")?.addEventListener("click", () => {
      Object.assign(filters, defaultFilters());
      saveFilters(filters);
      renderControls(filters);
      applyFilters(filters);
    });
  }

  async function init() {
    try {
      const resp = await fetch("dashboard_catalog.json");
      if (!resp.ok) return;
      catalog = await resp.json();
    } catch {
      return;
    }
    const filters = loadFilters();
    renderControls(filters);
    applyFilters(filters);
    bindEvents(filters);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
