/** Alpine + HTMX lab dashboard — two-tier nav, URL sync, filters. */
function labApp() {
  const STORAGE_KEY = "llmLabFilters";
  const FILTERS_OPEN_KEY = "llmLabFiltersOpen";
  const VIEW_MAP = {
    overview: { primary: "overview", partial: "overview", sub: null },
    report: { primary: "compare", partial: "report", sub: "report" },
    performance: { primary: "compare", partial: "performance", sub: "performance" },
    deepeval: { primary: "analyze", partial: "deepeval", sub: "deepeval" },
    ragas: { primary: "analyze", partial: "ragas", sub: "ragas" },
    failures: { primary: "analyze", partial: "failures", sub: "failures" },
    promptfoo: { primary: "tools", partial: "promptfoo", sub: "ui" },
    "promptfoo-ui": { primary: "tools", partial: "promptfoo", sub: "ui" },
    "promptfoo-summaries": { primary: "tools", partial: "promptfoo", sub: "summaries" },
  };

  return {
    primary: "overview",
    sub: null,
    contentPanel: null,
    catalog: null,
    filtersOpen: false,
    filters: { models: [], temps: [], dataset: "all", frameworks: [] },
    primaryTabs: [
      { id: "overview", label: "Overview" },
      { id: "compare", label: "Compare" },
      { id: "analyze", label: "Analyze" },
      { id: "tools", label: "Tools" },
    ],
    subTabs: {
      compare: [
        { id: "report", label: "Report", partial: "report" },
        { id: "performance", label: "Performance", partial: "performance" },
      ],
      analyze: [
        { id: "deepeval", label: "DeepEval", partial: "deepeval" },
        { id: "ragas", label: "RAGAS", partial: "ragas" },
        { id: "failures", label: "Failures", partial: "failures" },
      ],
      tools: [
        { id: "ui", label: "Promptfoo UI", partial: "promptfoo", panel: "ui" },
        { id: "summaries", label: "Summaries", partial: "promptfoo", panel: "summaries" },
      ],
    },

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
          const respUrl = e.detail.xhr?.responseURL;
          if (respUrl && window.Alpine) {
            const panel = new URL(respUrl).searchParams.get("panel");
            const root = Alpine.$data(document.body);
            if (root && panel) root.contentPanel = panel;
          }
          window.scrollTo(0, 0);
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

    currentSubs() {
      return this.subTabs[this.primary] || [];
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

    viewKey() {
      if (this.primary === "overview") return "overview";
      if (this.primary === "tools") return this.sub === "summaries" ? "promptfoo-summaries" : "promptfoo-ui";
      return this.sub || this.primary;
    },

    partialName() {
      if (this.primary === "overview") return "overview";
      const subs = this.currentSubs();
      const found = subs.find((s) => s.id === this.sub);
      return found?.partial || "overview";
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
      p.set("view", this.viewKey());
      if (this.contentPanel) p.set("panel", this.contentPanel);
      const qs = p.toString();
      const next = `${location.pathname}?${qs}`;
      if (location.search !== `?${qs}`) {
        history.pushState(null, "", next);
      }
    },

    readUrl() {
      const p = new URLSearchParams(location.search);
      const view = p.get("view") || "overview";
      const mapped = VIEW_MAP[view] || VIEW_MAP.overview;
      this.primary = mapped.primary;
      this.sub = mapped.sub;
      if (mapped.primary !== "overview" && !this.sub) {
        this.sub = this.currentSubs()[0]?.id || null;
      }
      this.contentPanel = p.get("panel") || null;
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
      if (this.primary === "tools") {
        p.set("panel", this.sub === "summaries" ? "summaries" : "ui");
      } else if (this.contentPanel && this.primary === "compare" && this.sub === "report") {
        p.set("panel", this.contentPanel);
      } else if (this.contentPanel && this.primary === "compare" && this.sub === "performance") {
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

    setPrimary(id) {
      this.primary = id;
      const subs = this.currentSubs();
      this.sub = subs.length ? subs[0].id : null;
      this.contentPanel = null;
      this.reloadMain();
    },

    setSub(id) {
      this.sub = id;
      this.contentPanel = null;
      this.reloadMain();
    },

    setTab(id) {
      const mapped = VIEW_MAP[id] || VIEW_MAP.overview;
      this.primary = mapped.primary;
      this.sub = mapped.sub;
      if (mapped.primary !== "overview" && !this.sub) {
        this.sub = this.currentSubs()[0]?.id || null;
      }
      this.contentPanel = null;
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
      const status = document.getElementById("profile-download-status");
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
  };
}
