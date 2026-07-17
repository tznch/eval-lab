/** Alpine + HTMX lab dashboard — flat destination nav, URL sync, filters. */
function labApp() {
  const STORAGE_KEY = "llmLabFilters";
  const FILTERS_OPEN_KEY = "llmLabFiltersOpen";
  const KNOWN_VIEWS = new Set([
    "overview",
    "report",
    "performance",
    "deepeval",
    "ragas",
    "failures",
    "promptfoo",
  ]);
  /** Legacy URL aliases → canonical view (+ optional panel). */
  const LEGACY_VIEWS = {
    "promptfoo-ui": { view: "promptfoo", panel: "ui" },
    "promptfoo-summaries": { view: "promptfoo", panel: "summaries" },
    compare: { view: "report" },
    analyze: { view: "deepeval" },
    tools: { view: "promptfoo" },
  };

  return {
    view: "overview",
    contentPanel: null,
    catalog: null,
    filtersOpen: false,
    filters: { models: [], temps: [], dataset: "all", frameworks: [] },

    setupHasProfile: false,
    setupOptions: null,
    setupReadiness: null,
    setupModelId: "",
    setupDatasetIds: [],
    setupTemperature: 0.7,
    setupFrameworks: ["promptfoo", "deepeval", "ragas"],
    setupCanRun: false,
    setupRunning: false,
    setupRunMessage: "",
    _readinessTimer: null,

    async init() {
      this.filtersOpen = localStorage.getItem(FILTERS_OPEN_KEY) === "1";
      this.readUrl();
      window.addEventListener("popstate", () => {
        this.readUrl();
        this.reloadMain({ skipUrl: true });
      });
      document.body.addEventListener("htmx:afterSwap", (e) => {
        if (e.detail?.target?.id === "main-content") {
          if (window.Alpine) Alpine.initTree(e.detail.target);
          const root = Alpine.$data(document.body);
          if (root && document.getElementById("run-eval-card") && !document.getElementById("run-eval-card").hidden) {
            root.loadSetupPanel();
          }
          const respUrl = e.detail.xhr?.responseURL;
          if (respUrl && window.Alpine) {
            const panel = new URL(respUrl).searchParams.get("panel");
            const root = Alpine.$data(document.body);
            if (root && panel) root.contentPanel = panel;
          }
          window.scrollTo(0, 0);
        }
        if (e.detail?.target?.id === "progress-panel" && window.Alpine) {
          Alpine.initTree(e.detail.target);
          const root = Alpine.$data(document.body);
          const runStatus = e.detail.xhr?.responseText || "";
          if (root) {
            root.setupRunning = runStatus.includes("Stop eval") || runStatus.includes("Stopping");
          }
        }
      });
      try {
        const resp = await fetch("/api/catalog");
        if (resp.ok) {
          this.catalog = await resp.json();
          this.filters = this.loadFilters();
        }
      } catch (err) {
        console.warn("catalog load failed", err);
      }
      this.reloadMain();
    },

    defaultFilters() {
      return {
        models: this.catalog?.models?.slice() || [],
        temps: this.catalog?.temps?.slice() || [],
        dataset: "all",
        frameworks: this.catalog?.frameworks?.slice() || [],
      };
    },

    loadFilters() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return this.defaultFilters();
        const saved = JSON.parse(raw);
        const d = this.defaultFilters();
        const datasets = this.catalog?.datasets || [];
        return {
          models: Array.isArray(saved.models) ? saved.models.filter((m) => d.models.includes(m)) : d.models,
          temps: Array.isArray(saved.temps) ? saved.temps.filter((t) => d.temps.includes(t)) : d.temps,
          dataset:
            saved.dataset === "all" || datasets.includes(saved.dataset) ? saved.dataset || "all" : "all",
          frameworks: Array.isArray(saved.frameworks)
            ? saved.frameworks.filter((f) => d.frameworks.includes(f))
            : d.frameworks,
        };
      } catch {
        return this.defaultFilters();
      }
    },

    saveFilters() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.filters));
    },

    toggleFilters() {
      this.filtersOpen = !this.filtersOpen;
      localStorage.setItem(FILTERS_OPEN_KEY, this.filtersOpen ? "1" : "0");
    },

    partialName() {
      return KNOWN_VIEWS.has(this.view) ? this.view : "overview";
    },

    filterQuery() {
      const p = new URLSearchParams();
      if (this.filters.models.length) p.set("models", this.filters.models.join(","));
      if (this.filters.temps.length) p.set("temps", this.filters.temps.join(","));
      if (this.filters.dataset !== "all") p.set("dataset", this.filters.dataset);
      if (this.filters.frameworks.length) p.set("frameworks", this.filters.frameworks.join(","));
      return p;
    },

    filterSummary() {
      const temps = this.filters.temps.map((t) => t.replace(/^t/, "t=")).join(", ");
      const ds = this.filters.dataset === "all" ? "all tracks" : this.filters.dataset;
      return `${this.filters.models.join(", ") || "—"} · ${temps || "—"} · ${ds}`;
    },

    syncUrl() {
      const p = this.filterQuery();
      p.set("view", this.view);
      if (this.contentPanel) p.set("panel", this.contentPanel);
      const qs = p.toString();
      const next = `${location.pathname}?${qs}`;
      if (location.search !== `?${qs}`) {
        history.pushState(null, "", next);
      }
    },

    readUrl() {
      const p = new URLSearchParams(location.search);
      const raw = p.get("view") || "overview";
      const legacy = LEGACY_VIEWS[raw];
      if (legacy) {
        this.view = legacy.view;
        this.contentPanel = p.get("panel") || legacy.panel || null;
      } else {
        this.view = KNOWN_VIEWS.has(raw) ? raw : "overview";
        this.contentPanel = p.get("panel") || null;
      }
      if (this.view === "promptfoo" && !this.contentPanel) {
        this.contentPanel = "ui";
      }
      if (p.has("models") || p.has("temps") || p.has("dataset") || p.has("frameworks")) {
        this._urlFilterParams = p;
      }
    },

    applyUrlFiltersIfAny() {
      if (!this._urlFilterParams || !this.catalog) return;
      const p = this._urlFilterParams;
      const d = this.defaultFilters();
      if (p.has("models")) {
        this.filters.models = p.get("models").split(",").filter((m) => d.models.includes(m));
      }
      if (p.has("temps")) {
        this.filters.temps = p.get("temps").split(",").filter((t) => d.temps.includes(t));
      }
      if (p.has("dataset")) {
        const ds = p.get("dataset");
        this.filters.dataset = ds === "all" || (this.catalog.datasets || []).includes(ds) ? ds : "all";
      }
      if (p.has("frameworks")) {
        this.filters.frameworks = p.get("frameworks").split(",").filter((f) => d.frameworks.includes(f));
      }
      this._urlFilterParams = null;
    },

    reloadMain({ skipUrl = false } = {}) {
      this.applyUrlFiltersIfAny();
      const partial = this.partialName();
      const p = this.filterQuery();
      if (this.view === "promptfoo") {
        p.set("panel", this.contentPanel === "summaries" ? "summaries" : "ui");
      } else if (this.contentPanel && (this.view === "report" || this.view === "performance")) {
        p.set("panel", this.contentPanel);
      }
      const qs = p.toString();
      const url = `/partials/${partial}${qs ? "?" + qs : ""}`;
      if (!skipUrl) this.syncUrl();
      if (typeof htmx === "undefined") {
        console.error("htmx missing");
        return;
      }
      htmx.ajax("GET", url, { target: "#main-content", swap: "innerHTML" });
    },

    setView(id) {
      this.view = KNOWN_VIEWS.has(id) ? id : "overview";
      this.contentPanel = this.view === "promptfoo" ? "ui" : null;
      this.reloadMain();
    },

    toggle(key, value) {
      const list = this.filters[key];
      const idx = list.indexOf(value);
      if (idx >= 0) {
        if (list.length > 1) list.splice(idx, 1);
      } else {
        list.push(value);
      }
      this.saveAndReload();
    },

    saveAndReload() {
      this.saveFilters();
      this.reloadMain();
    },

    resetFilters() {
      this.filters = this.defaultFilters();
      this.saveAndReload();
    },

    async downloadProfileModel(event) {
      const button = event.currentTarget;
      const status = document.getElementById("profile-action-status");
      if (!status) return;

      button.disabled = true;
      status.textContent = "Downloading…";
      try {
        const response = await fetch("/api/models/download", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            profile: button.dataset.profile,
            model_id: button.dataset.modelId || null,
          }),
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.message || "Download failed");
        }
        status.textContent = data.path ? `${data.message}: ${data.path}` : data.message;
      } catch (error) {
        status.textContent = error instanceof Error ? error.message : "Download failed";
      } finally {
        button.disabled = false;
      }
    },

    async exportRunProfile(event) {
      const button = event.currentTarget;
      const status =
        button.parentElement?.querySelector("[data-run-export-status]") ||
        document.getElementById("profile-action-status");
      const model = button.dataset.model;
      const temperature = Number.parseFloat(button.dataset.temperature);
      if (!status || !model || Number.isNaN(temperature)) return;

      const dataset =
        this.filters.dataset && this.filters.dataset !== "all"
          ? this.filters.dataset
          : null;
      const stamp = new Date().toISOString().slice(0, 10);
      const name = [model, `t${temperature}`, dataset, stamp].filter(Boolean).join("-");

      button.disabled = true;
      status.textContent = "Exporting…";
      try {
        const response = await fetch("/api/profiles/export", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            models: [model],
            temperature,
            dataset,
          }),
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.message || "Export failed");
        }
        const blob = new Blob([data.yaml], { type: "text/yaml;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = data.filename || `${name}.yaml`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        status.textContent = data.message || "Exported";
      } catch (error) {
        status.textContent = error instanceof Error ? error.message : "Export failed";
      } finally {
        button.disabled = false;
      }
    },

    async importProfileFile(event) {
      const input = event.currentTarget;
      const status = document.getElementById("profile-action-status");
      const file = input.files && input.files[0];
      if (!status || !file) return;

      status.textContent = `Importing ${file.name}…`;
      try {
        const yamlText = await file.text();
        const response = await fetch("/api/profiles/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ yaml: yamlText }),
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.message || "Import failed");
        }
        status.textContent = data.message || "Imported";
        this.setupHasProfile = true;
        if (this.view === "overview") {
          this.reloadMain({ skipUrl: true });
        } else {
          await this.loadSetupPanel();
        }
      } catch (error) {
        status.textContent = error instanceof Error ? error.message : "Import failed";
      } finally {
        input.value = "";
      }
    },

    initSetupPanel(hasProfile) {
      if (hasProfile) {
        this.setupHasProfile = true;
        this.loadSetupPanel();
      }
    },

    async loadSetupPanel() {
      try {
        const resp = await fetch("/api/setup/options");
        if (!resp.ok) return;
        const options = await resp.json();
        this.setupOptions = options;
        this.setupHasProfile = Boolean(options.has_profile);
        this.setupModelId = options.default_model || options.models?.[0] || "bonsai";
        const catalogIds = (options.dataset_catalog || []).map((d) => d.id);
        const known = catalogIds.length ? catalogIds : options.datasets || [];
        const defaults = options.default_datasets?.length
          ? options.default_datasets
          : [options.default_dataset || known[0] || "sciq"];
        this.setupDatasetIds = defaults.filter((d) => known.includes(d));
        if (!this.setupDatasetIds.length && known.length) {
          this.setupDatasetIds = [known[0]];
        }
        this.setupTemperature = options.default_temperature ?? 0.7;
        this.setupFrameworks = options.frameworks?.slice() || ["promptfoo", "deepeval", "ragas"];
        await this.fetchReadiness();
      } catch (err) {
        console.warn("setup panel load failed", err);
      }
    },

    fetchReadiness() {
      if (this._readinessTimer) clearTimeout(this._readinessTimer);
      return new Promise((resolve) => {
        this._readinessTimer = setTimeout(async () => {
          await this._fetchReadinessNow();
          resolve();
        }, 200);
      });
    },

    async _fetchReadinessNow() {
      if (!this.setupModelId || !this.setupDatasetIds.length) {
        this.setupCanRun = false;
        return;
      }
      const params = new URLSearchParams({
        model: this.setupModelId,
        datasets: this.setupDatasetIds.join(","),
        frameworks: this.setupFrameworks.join(","),
      });
      try {
        const resp = await fetch(`/api/setup/readiness?${params}`);
        if (!resp.ok) return;
        const data = await resp.json();
        this.setupReadiness = data;
        this.setupCanRun = Boolean(data.can_run);
        const status = await fetch("/api/run-status");
        if (status.ok) {
          const run = await status.json();
          this.setupRunning = run.status === "running" || run.status === "cancelling";
        }
      } catch (err) {
        console.warn("readiness fetch failed", err);
      }
    },

    toggleSetupDataset(ds) {
      const list = this.setupDatasetIds;
      const idx = list.indexOf(ds);
      if (idx >= 0) {
        if (list.length > 1) list.splice(idx, 1);
      } else {
        list.push(ds);
      }
      this.fetchReadiness();
    },

    toggleSetupFramework(fw) {
      const list = this.setupFrameworks;
      const idx = list.indexOf(fw);
      if (idx >= 0) {
        if (list.length > 1) list.splice(idx, 1);
      } else {
        list.push(fw);
      }
      this.fetchReadiness();
    },

    async runEval() {
      if (!this.setupCanRun || this.setupRunning) return;
      this.setupRunning = true;
      this.setupRunMessage = "Starting eval…";
      try {
        const resp = await fetch("/api/evals/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model_id: this.setupModelId,
            dataset_ids: this.setupDatasetIds,
            temperature: this.setupTemperature,
            frameworks: this.setupFrameworks,
          }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
          const blockers = data.blocking?.length ? ` (${data.blocking.join("; ")})` : "";
          throw new Error((data.message || "Run failed") + blockers);
        }
        this.setupRunMessage = data.message || "Eval started";
        const progress = document.getElementById("progress-panel");
        if (progress && typeof htmx !== "undefined") {
          htmx.trigger(progress, "load");
        }
      } catch (error) {
        this.setupRunMessage = error instanceof Error ? error.message : "Run failed";
        this.setupRunning = false;
      }
    },

    async stopEval() {
      const statusEl = document.getElementById("stop-eval-status");
      const button = document.getElementById("btn-stop-eval");
      if (button) button.disabled = true;
      if (statusEl) statusEl.textContent = "Stopping…";
      try {
        const resp = await fetch("/api/evals/stop", { method: "POST" });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
          throw new Error(data.message || "Stop failed");
        }
        if (statusEl) statusEl.textContent = data.message || "Stopped";
        this.setupRunning = false;
        this.setupRunMessage = "Eval stopped";
        const progress = document.getElementById("progress-panel");
        if (progress && typeof htmx !== "undefined") {
          htmx.trigger(progress, "load");
        }
      } catch (error) {
        if (statusEl) {
          statusEl.textContent = error instanceof Error ? error.message : "Stop failed";
        }
        if (button) button.disabled = false;
      }
    },
  };
}
