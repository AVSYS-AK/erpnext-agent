/* global frappe, $ */

frappe.provide("ai_agent");

(function () {
  // ---------- helpers ----------
  const el = (tag, attrs = {}, children = null) => {
    const $e = $(`<${tag}>`);
    Object.entries(attrs || {}).forEach(([k, v]) => $e.attr(k, v));
    if (children != null) {
      if (Array.isArray(children)) children.forEach((c) => $e.append(c));
      else $e.append(children);
    }
    return $e;
  };
  const btn = (label, cls = "", onClick = null) => {
    const $b = el("button", { type: "button", class: `ai-btn ${cls}` }, label);
    if (onClick) $b.on("click", onClick);
    return $b;
  };
  const call = async (method, args = {}) => {
    const r = await frappe.call({ method, args });
    return r.message;
  };
  const numIN = (n) =>
    new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(n || 0);
  const moneyIN = (n) =>
    new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(typeof n === "number" ? n : 0);

  // ---------- styles ----------
  const injectStyles = () => {
    if ($("#ai-agent-console-css").length) return;
    $("head").append(`
    <style id="ai-agent-console-css">
      .ai-wrap{padding:10px 0 28px}
      .ai-topbar{display:flex;align-items:center;gap:10px;margin-bottom:10px}
      .ai-tabs{display:flex;gap:8px;margin-bottom:10px}
      .ai-tab{border:1px solid #e5e7eb;border-radius:999px;padding:6px 12px;background:#f3f4f6;color:#111827;font-weight:600;cursor:pointer}
      .ai-tab.active{background:#111827;color:#fff}
      .ai-two-col{display:grid;grid-template-columns:0.40fr 0.60fr;gap:16px}
      .ai-card{background:#fff;border:1px solid #eef0f2;border-radius:12px;padding:14px 14px;box-shadow:0 1px 0 rgba(16,24,40,.02)}
      .ai-title{font-weight:700;margin:0 0 8px 0}
      .ai-sub{color:#6b7280;font-size:12px;margin:0 0 10px}
      .ai-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
      .ai-kpi h3{margin:0 0 4px 0;font-size:13px;color:#374151}
      .ai-kpi .v{font-size:20px;font-weight:700;margin:2px 0 6px}
      .ai-kpi .win{font-size:11px;color:#6b7280}
      .ai-input,.ai-select,.ai-textarea{width:100%;border:1px solid #e5e7eb;border-radius:10px;padding:9px 10px;background:#fafafa}
      .ai-textarea{min-height:90px;resize:vertical}
      .ai-btn{border:1px solid #e5e7eb;border-radius:10px;padding:8px 12px;background:#111827;color:#fff;font-weight:700}
      .ai-btn.secondary{background:#f3f4f6;color:#111827}
      .ai-badges{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
      .ai-badge{background:#f3f4f6;border:1px solid #e5e7eb;border-radius:999px;padding:3px 9px;font-size:11px;color:#374151}
      .ai-left-stack{display:flex;flex-direction:column;gap:12px}
      .ai-pill-toolbar{display:flex;gap:8px;flex-wrap:wrap}
      .ai-preset-list{display:flex;flex-direction:column;gap:8px;max-height:420px;overflow:auto}
      .ai-pres-item{padding:10px;border:1px solid #eef0f2;border-radius:10px;background:#fff;cursor:pointer}
      .ai-pres-item:hover{background:#f7f7f7}
      .ai-pres-cat{font-size:11px;color:#6b7280;margin-bottom:2px}
      .ai-output .html{padding:8px;border:1px solid #eef0f2;border-radius:10px;background:#fff}
      .ai-toolbar{display:flex;gap:8px;align-items:center;margin:8px 0}
      .ai-table{width:100%;border-collapse:collapse;margin-top:6px}
      .ai-table th{background:#fafafa;border:1px solid #eee;padding:6px;text-align:left}
      .ai-table td{border:1px solid #f0f0f0;padding:6px}
      @media (max-width:1200px){.ai-two-col{grid-template-columns:1fr}.ai-kpis{grid-template-columns:repeat(2,1fr)}}
    </style>`);
  };

  // ---------- growth dashboard ----------
  const metricCalls = [
    ["Sales (MTD)", "ai_agent.presets_api.metric_sales_mtd"],
    ["Purchases (MTD)", "ai_agent.presets_api.metric_purchases_mtd"],
    ["AR Overdue", "ai_agent.presets_api.metric_ar_overdue"],
    ["Stockout Risk (14d)", "ai_agent.presets_api.metric_stockout_14d"],
  ];

  const renderGrowth = async ($panel, company) => {
    $panel.empty();
    const $kpis = el("div", { class: "ai-kpis" });
    $panel.append($kpis);
    for (const [label, method] of metricCalls) {
      try {
        const m = await call(method, { company });
        const val =
          m && m.unit === "count" ? numIN(m.value) : moneyIN(m.value || 0);
        $kpis.append(
          el("div", { class: "ai-card ai-kpi" }, [
            el("h3", {}, label),
            el("div", { class: "v" }, val),
            el("div", { class: "win" }, m?.window || ""),
            el("div", { class: "win" }, m?.explain || ""),
          ])
        );
      } catch {
        $kpis.append(
          el("div", { class: "ai-card ai-kpi" }, [
            el("h3", {}, label),
            el("div", { class: "v" }, "—"),
            el("div", { class: "win" }, "Failed to load"),
          ])
        );
      }
    }
  };

  // ---------- grouping logic ----------
  const GROUP_SETS = {
    default: [
      ["none", "no grouping"],
      ["month", "month"],
      ["customer", "customer"],
      ["item", "item"],
      ["region", "region"],
    ],
    sales: [
      ["none", "no grouping"],
      ["month", "month"],
      ["customer", "customer"],
      ["item", "item"],
      ["region", "region"],
      ["owner", "owner"],
    ],
    purchasing: [
      ["none", "no grouping"],
      ["month", "month"],
      ["supplier", "supplier (vendor)"],
      ["item", "item"],
      ["region", "region"],
    ],
    inventory: [
      ["none", "no grouping"],
      ["month", "month"],
      ["item", "item"],
      ["region", "region"],
    ],
  };

  const inferDomain = (txt) => {
    const t = String(txt || "").toLowerCase();
    if (/(purchase|supplier|vendor|po\b)/.test(t)) return "purchasing";
    if (/(sale|customer|si\b|revenue|invoice)/.test(t)) return "sales";
    if (/(stock|inventory|warehouse|item)/.test(t)) return "inventory";
    return "default";
  };

  const refillGrouping = ($sel, domain) => {
    const prev = $sel.val();
    $sel.empty();
    (GROUP_SETS[domain] || GROUP_SETS.default).forEach(([v, l]) =>
      $sel.append(el("option", { value: v }, `by ${l}`))
    );
    if (prev && $sel.find(`option[value="${prev}"]`).length) $sel.val(prev);
  };

  // ---------- output helpers ----------
  const renderTable = (spec) => {
    const $t = el("table", { class: "ai-table" });
    const $thead = el("thead").append(
      el("tr", {}, (spec.columns || []).map((c) => el("th", {}, c)))
    );
    const $tbody = el("tbody");
    (spec.rows || []).forEach((r) =>
      $tbody.append(el("tr", {}, r.map((v) => el("td", {}, v))))
    );
    return $t.append($thead, $tbody);
  };

  const toCSV = (spec) => {
    const rows = [spec.columns, ...(spec.rows || [])];
    return rows
      .map((r) =>
        r.map((x) => `"${String(x ?? "").replace(/"/g, '""')}"`).join(",")
      )
      .join("\n");
  };

  const runPrompt = async (
    { text, company, windowToken, customFrom, customTo, groupBy, dryRun },
    $out
  ) => {
    let suffix = [];
    if (company && company !== "All Companies") suffix.push(`for ${company}`);
    if (windowToken === "CUSTOM") {
      if (customFrom && customTo) suffix.push(`from ${customFrom} to ${customTo}`);
    } else if (windowToken) {
      suffix.push(windowToken);
    }
    if (groupBy && groupBy !== "none") suffix.push(`by ${groupBy}`);
    const prompt = [String(text || "").trim(), suffix.join(" ")]
      .filter(Boolean)
      .join(" ");

    $out.empty().append(el("div", { class: "ai-sub" }, "Running…"));

    try {
      const res = await call("ai_agent.api.run_rich", {
        command_text: prompt,
        dry_run: dryRun ? 1 : 0,
      });

      $out.empty();

      const crumbs = el("div", { class: "ai-badges" });
      if (company) crumbs.append(el("span", { class: "ai-badge" }, company));
      if (windowToken === "CUSTOM" && customFrom && customTo)
        crumbs.append(el("span", { class: "ai-badge" }, `${customFrom} → ${customTo}`));
      else if (windowToken)
        crumbs.append(el("span", { class: "ai-badge" }, windowToken));
      if (groupBy && groupBy !== "none")
        crumbs.append(el("span", { class: "ai-badge" }, `by ${groupBy}`));
      $out.append(crumbs);

      if (res.html) $out.append($("<div class='html'></div>").html(res.html));

      if (res.table && res.table.columns && res.table.rows) {
        const $toolbar = el("div", { class: "ai-toolbar" }, [
          el("span", { class: "ai-sub" }, "Table"),
          btn("Export CSV", "secondary", () => {
            const csv = toCSV(res.table);
            const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "result.csv";
            a.click();
            URL.revokeObjectURL(url);
          }),
        ]);
        $out.append($toolbar, renderTable(res.table));
      }

      if (!res.html && !res.table) {
        $out.append(
          el("pre", { class: "ai-card" }, JSON.stringify(res.raw || res, null, 2))
        );
      }
    } catch (e) {
      $out.empty().append(el("pre", { class: "ai-card" }, e?.message || "Failed"));
    }
  };

  // ---------- page ----------
  frappe.pages["ai_agent_console"].on_page_load = async function (wrapper) {
    injectStyles();

    const page = frappe.ui.make_app_page({
      parent: wrapper,
      title: "AI Agent Console",
      single_column: true,
    });

    const $body = $(page.body).empty();
    const $wrap = el("div", { class: "ai-wrap" });
    $body.append($wrap);

    // Header
    const $companySel = el("select", {
      class: "ai-select",
      style: "max-width:220px;display:inline-block",
    });
    const $hdr = el("div", { class: "ai-topbar" }, [
      el("h2", { style: "margin:0 6px 0 0" }, "AI Agent Console"),
      el("span", { class: "ai-sub" }, "Live analytics and agent tools."),
      $companySel,
    ]);
    $wrap.append($hdr);

    // Tabs
    const $tabs = el("div", { class: "ai-tabs" });
    const $tabConsole = el("div", { class: "ai-tab active" }, "Console");
    const $tabGrowth  = el("div", { class: "ai-tab" }, "Growth Dashboard");
    $tabs.append($tabConsole, $tabGrowth);
    $wrap.append($tabs);

    // Sections
    const $sectionConsole = el("div");
    const $sectionGrowth  = el("div").hide();
    $wrap.append($sectionConsole, $sectionGrowth);

    // Companies
    let companies = await call("ai_agent.presets_api.list_companies").catch(() => []);
    if (!Array.isArray(companies) || !companies.length) companies = ["All Companies"];
    companies = ["All Companies", ...companies.filter((c) => c !== "All Companies")];
    companies.forEach((c) => $companySel.append(el("option", { value: c }, c)));

    // -------- Console (40/60) --------
    const $grid = el("div", { class: "ai-two-col" });
    const $left = el("div", { class: "ai-left-stack" });
    const $right = el("div", { class: "ai-card ai-output" });
    $grid.append($left, $right);
    $sectionConsole.append($grid);

    // Ask block (no inline company selector – uses top one)
    const $askCard = el("div", { class: "ai-card" });
    $askCard.append(el("div", { class: "ai-title" }, "Ask Anything"));
    $askCard.append(
      el("div", { class: "ai-sub" }, 'Example: “top 10 customers by revenue this year vs target”')
    );

    const $prompt = el("textarea", {
      class: "ai-textarea",
      placeholder: "Type a question or click a preset below…",
    });

    // window + custom dates
    const $windowSel = el("select", { class: "ai-select", style: "max-width:140px" }, [
      "MTD","QTD","YTD","L3M","L6M","L12M","This month","Last month","This year","Last year","Custom…"
    ].map((t) => el("option", { value: t === "Custom…" ? "CUSTOM" : t }, t)));

    const $from = el("input", { type: "date", class: "ai-input", style: "max-width:140px; display:none" });
    const $to   = el("input", { type: "date", class: "ai-input", style: "max-width:140px; display:none" });

    const toggleCustomDates = () => {
      if ($windowSel.val() === "CUSTOM") {
        $from.show(); $to.show();
      } else {
        $from.hide().val(""); $to.hide().val("");
      }
    };
    $windowSel.on("change", toggleCustomDates);
    toggleCustomDates();

    // dynamic grouping
    const $groupSel = el("select", { class: "ai-select", style: "max-width:170px" });
    const refreshGrouping = () => refillGrouping($groupSel, inferDomain($prompt.val()));
    refreshGrouping();
    $prompt.on("input", refreshGrouping);

    const $run = btn("Run", "", async () => {
      await runPrompt({
        text: $prompt.val(),
        company: $companySel.val(),
        windowToken: $windowSel.val(),
        customFrom: $from.val(),
        customTo: $to.val(),
        groupBy: $groupSel.val(),
        dryRun: false,
      }, $right);
    });
    const $dry = btn("Dry Run", "secondary", async () => {
      await runPrompt({
        text: $prompt.val(),
        company: $companySel.val(),
        windowToken: $windowSel.val(),
        customFrom: $from.val(),
        customTo: $to.val(),
        groupBy: $groupSel.val(),
        dryRun: true,
      }, $right);
    });

    const $tips = el("div", { class: "ai-pill-toolbar" }, [
      el("span", { class: "ai-badge" }, "include company & dates"),
      el("span", { class: "ai-badge" }, "MTD / QTD / YTD / L12M / Custom"),
      el("span", { class: "ai-badge" }, "by month / customer / item / region / owner / supplier"),
      el("span", { class: "ai-badge" }, "“vs target”, “YoY”"),
    ]);

    const $controls = el("div", { class: "ai-pill-toolbar" }, [
      $windowSel, $from, $to, $groupSel, $run, $dry,
    ]);

    $askCard.append($prompt, $tips, $controls);
    $left.append($askCard);

    // Presets block
    const $presCard = el("div", { class: "ai-card" });
    $presCard.append(el("div", { class: "ai-title" }, "Presets"));
    const $search = el("input", { class: "ai-input", placeholder: "Search presets (pipeline, …)" });
    const $catSel = el("select", { class: "ai-select", style: "margin-top:6px" }, [
      el("option", { value: "All" }, "All categories"),
    ]);
    const $list = el("div", { class: "ai-preset-list", style: "margin-top:8px" });
    const $hint = el("div", { class: "ai-badges" }).hide();
    $presCard.append($search, $catSel, $hint, $list);
    $left.append($presCard);

    const allPresets = (await call("ai_agent.presets_api.list_presets")) || [];
    const presetCat = (p) => (p.cat || "Other").trim();
    const match = (p, q) =>
      !q ||
      (p.label + " " + p.prompt + " " + (p.cat || "")).toLowerCase().includes(q.toLowerCase());
    const renderPresets = (all, $list, cat, q, onPick) => {
      $list.empty();
      const items = all.filter(
        (p) => (cat === "All" || presetCat(p) === cat) && match(p, q)
      );
      if (!items.length) { $list.append(el("div", { class: "ai-sub" }, "No presets found.")); return; }
      items.forEach((p) => {
        $list.append(
          el("div", { class: "ai-pres-item" })
            .append(el("div", { class: "ai-pres-cat" }, presetCat(p)))
            .append(el("div", { style: "font-weight:600" }, p.label))
            .on("click", () => onPick(p))
        );
      });
    };
    const cats = Array.from(new Set(allPresets.map(presetCat))).sort();
    cats.forEach((c) => $catSel.append(el("option", { value: c }, c)));
    const pickPreset = (p) => { $prompt.val(p.prompt || p.label || ""); refreshGrouping(); $prompt.focus(); };
    const redrawList = () => {
      renderPresets(allPresets, $list, $catSel.val() || "All", $search.val() || "", pickPreset);
      const q = ($search.val() || "").trim().toLowerCase();
      const sugg = q ? allPresets.filter((p) => match(p, q)).slice(0,6) : [];
      $hint.empty();
      if (!sugg.length) return $hint.hide();
      sugg.forEach((p) => {
        $hint.append(
          el("span", { class: "ai-badge", style: "cursor:pointer" }, p.label)
            .on("click", () => pickPreset(p))
        );
      });
      $hint.show();
    };
    $search.on("input", redrawList);
    $catSel.on("change", redrawList);
    redrawList();

    // Output
    $right.append(el("div", { class: "ai-title" }, "Output"));
    $right.append(
      el("div", { class: "ai-sub" }, "Tables/HTML will render here. CSV export appears when a table is returned.")
    );

    // -------- Growth section --------
    const $growthCard = el("div", { class: "ai-card" });
    $growthCard.append(el("div", { class: "ai-title" }, "Growth Dashboard"));
    const $growthPanel = el("div");
    $growthCard.append($growthPanel);
    $sectionGrowth.append($growthCard);

    await renderGrowth($growthPanel, $companySel.val());
    $companySel.on("change", async () => { await renderGrowth($growthPanel, $companySel.val()); });

    // Tabs
    const activate = (which) => {
      if (which === "console") {
        $tabConsole.addClass("active"); $tabGrowth.removeClass("active");
        $sectionConsole.show(); $sectionGrowth.hide();
      } else {
        $tabGrowth.addClass("active"); $tabConsole.removeClass("active");
        $sectionGrowth.show(); $sectionConsole.hide();
        renderGrowth($growthPanel, $companySel.val());
      }
    };
    $tabConsole.on("click", () => activate("console"));
    $tabGrowth.on("click",  () => activate("growth"));
  };
})();
