const PAGE_SIZE = 50;

const state = {
  tree: {},
  collectors: [],
  items: [],
  facets: { sources: [], categories: [] },
  pagination: { limit: PAGE_SIZE, offset: 0, returned: 0, total: 0, has_more: false },
  selectedDate: null,
  selectedSource: "",
  selectedCategory: "",
  minScore: "",
  query: "",
  selectedItem: null,
  openFilter: null,
  mode: "list",
};

const scoreOptions = [
  { value: "", label: "All scores" },
  { value: "3", label: "Score >= 3" },
  { value: "5", label: "Score >= 5" },
  { value: "7", label: "Score >= 7" },
  { value: "8", label: "Score >= 8" },
];

const els = {
  appShell: document.getElementById("appShell"),
  tree: document.getElementById("tree"),
  sources: document.getElementById("sources"),
  items: document.getElementById("items"),
  resultMeta: document.getElementById("resultMeta"),
  viewTitle: document.getElementById("viewTitle"),
  viewMeta: document.getElementById("viewMeta"),
  detailHeader: document.getElementById("detailHeader"),
  detailSub: document.getElementById("detailSub"),
  detailBody: document.getElementById("detailBody"),
  openBtn: document.getElementById("openBtn"),
  searchInput: document.getElementById("searchInput"),
  prevPage: document.getElementById("prevPage"),
  nextPage: document.getElementById("nextPage"),
};

document.getElementById("refreshAll").addEventListener("click", init);
document.getElementById("collectBtn").addEventListener("click", runCollect);
document.getElementById("analyzeBtn").addEventListener("click", runAnalyze);
document.getElementById("reportBtn").addEventListener("click", loadReport);
document.getElementById("clearBtn").addEventListener("click", clearFilters);
document.getElementById("backToList").addEventListener("click", () => setMode("list"));
els.prevPage.addEventListener("click", () => {
  state.pagination.offset = Math.max(0, state.pagination.offset - PAGE_SIZE);
  loadItems({ keepSelection: false });
});
els.nextPage.addEventListener("click", () => {
  state.pagination.offset += PAGE_SIZE;
  loadItems({ keepSelection: false });
});
els.searchInput.addEventListener("input", debounce(() => {
  state.query = els.searchInput.value.trim();
  state.pagination.offset = 0;
  loadItems({ keepSelection: false });
}, 260));
document.querySelectorAll(".modeBtn").forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});
document.addEventListener("click", (event) => {
  if (!event.target.closest(".filterMenu")) closeFilter();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeFilter();
});
els.openBtn.addEventListener("click", () => {
  if (state.selectedItem?.url) window.open(state.selectedItem.url, "_blank", "noopener");
});

async function init() {
  els.items.innerHTML = '<div class="loading">Loading items...</div>';
  await Promise.all([loadTree(), loadCollectors()]);
  renderFilters();
  await loadItems({ keepSelection: false });
}

async function loadTree() {
  try {
    const resp = await fetch("/api/tree");
    if (!resp.ok) throw new Error(await resp.text());
    state.tree = await resp.json();
    renderTree();
  } catch (error) {
    els.tree.innerHTML = `<div class="error">日期树加载失败: ${escapeHtml(error.message)}</div>`;
  }
}

async function loadCollectors() {
  try {
    const resp = await fetch("/api/collectors");
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    state.collectors = data.collectors || [];
    renderSources();
  } catch (error) {
    els.sources.innerHTML = `<div class="error">来源状态加载失败: ${escapeHtml(error.message)}</div>`;
  }
}

async function loadItems(options = {}) {
  const params = new URLSearchParams();
  if (state.selectedDate) params.set("date", state.selectedDate);
  if (state.selectedSource) params.set("source", state.selectedSource);
  if (state.selectedCategory) params.set("category", state.selectedCategory);
  if (state.minScore) params.set("min_score", state.minScore);
  if (state.query) params.set("q", state.query);
  params.set("limit", String(PAGE_SIZE));
  params.set("offset", String(state.pagination.offset));

  els.items.innerHTML = '<div class="loading">Loading items...</div>';
  try {
    const resp = await fetch(`/api/items?${params.toString()}`);
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    state.items = data.items || [];
    state.facets = data.facets || { sources: [], categories: [] };
    state.pagination = data.pagination || { limit: PAGE_SIZE, offset: 0, returned: state.items.length, total: state.items.length, has_more: false };
    if (options.keepSelection && state.selectedItem) {
      state.selectedItem = state.items.find((item) => item.id === state.selectedItem.id) || state.items[0] || null;
    } else {
      state.selectedItem = state.items[0] || null;
    }
    renderFilters();
    renderItems();
    renderDetail();
    updateHeader();
  } catch (error) {
    els.items.innerHTML = `<div class="error">信息列表加载失败: ${escapeHtml(error.message)}</div>`;
  }
}

async function loadReport() {
  if (!state.selectedDate) {
    setMode("detail");
    els.detailHeader.textContent = "Report";
    els.detailSub.textContent = "需要日期";
    els.detailBody.innerHTML = '<div class="empty">先选择左侧日期，再打开日报。</div>';
    return;
  }
  setMode("detail");
  els.detailHeader.textContent = "Report";
  els.detailSub.textContent = `${state.selectedDate} · 可能调用 LLM 生成`;
  els.openBtn.disabled = true;
  els.detailBody.innerHTML = '<div class="notice">正在加载日报。如果当天没有缓存，服务端可能会调用 LLM 生成，耗时取决于模型接口。</div>';
  try {
    const resp = await fetch(`/api/report/${state.selectedDate}`);
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    els.detailBody.innerHTML = data.content
      ? `<div class="markdown">${renderMarkdown(data.content)}</div>`
      : `<div class="empty">${state.selectedDate} 暂无可生成报告的分析结果。</div>`;
  } catch (error) {
    els.detailBody.innerHTML = `<div class="error">报告加载失败: ${escapeHtml(error.message)}</div>`;
  }
}

async function runCollect() {
  const selected = state.selectedSource;
  const enabledNames = state.collectors.filter((collector) => collector.enabled).map((collector) => collector.name);
  const names = selected ? [selected] : enabledNames;
  if (!names.length) {
    setRunMessage("No enabled collectors");
    return;
  }
  await runAction("collect", `/api/run/collect?collectors=${encodeURIComponent(names.join(","))}`, async (data) => {
    state.collectors = data.collectors || state.collectors;
    renderSources();
    await Promise.all([loadTree(), loadItems({ keepSelection: false })]);
    setRunMessage(`Collect finished: ${data.total_new || 0} new items · ${names.join(", ")}`);
  });
}

async function runAnalyze() {
  await runAction("analyze", "/api/run/analyze", async () => {
    await loadItems({ keepSelection: true });
    setRunMessage("Analyze finished");
  });
}

async function runAction(label, url, afterSuccess) {
  setActionButtons(true);
  setRunMessage(`${label} running...`);
  try {
    const resp = await fetch(url, { method: "POST" });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    await afterSuccess(data);
  } catch (error) {
    setRunMessage(`${label} failed: ${error.message}`);
    setMode("detail");
    els.detailHeader.textContent = "Run Error";
    els.detailSub.textContent = label;
    els.detailBody.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
  } finally {
    setActionButtons(false);
  }
}

function setActionButtons(disabled) {
  ["collectBtn", "analyzeBtn", "reportBtn", "clearBtn", "refreshAll", "prevPage", "nextPage"].forEach((id) => {
    document.getElementById(id).disabled = disabled;
  });
}

function clearFilters() {
  state.selectedSource = "";
  state.selectedCategory = "";
  state.minScore = "";
  state.query = "";
  state.pagination.offset = 0;
  els.searchInput.value = "";
  renderSources();
  loadItems({ keepSelection: false });
}

function setMode(mode) {
  state.mode = mode;
  els.appShell.dataset.mode = mode;
  document.querySelectorAll(".modeBtn").forEach((button) => {
    button.classList.toggle("selected", button.dataset.mode === mode);
  });
}

function renderTree() {
  const years = Object.keys(state.tree).sort().reverse();
  if (!years.length) {
    els.tree.innerHTML = '<div class="empty">暂无采集日期。运行 collect 后这里会出现日期树。</div>';
    return;
  }
  els.tree.innerHTML = "";
  years.forEach((year) => {
    const yearWrap = createTreeGroup(`${year}`, state.tree[year]._count || 0);
    const months = Object.keys(state.tree[year]).filter((key) => key !== "_count").sort((a, b) => b.localeCompare(a));
    months.forEach((month) => {
      const monthData = state.tree[year][month];
      const monthWrap = createTreeGroup(`${month}月`, monthData._count || 0);
      const days = Object.keys(monthData).filter((key) => key !== "_count").sort((a, b) => b.localeCompare(a));
      days.forEach((day) => {
        const date = `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
        const row = createTreeRow(`${day.padStart(2, "0")}日`, monthData[day], false);
        row.dataset.date = date;
        row.classList.toggle("selected", date === state.selectedDate);
        row.addEventListener("click", () => {
          state.selectedDate = date;
          state.pagination.offset = 0;
          renderTree();
          loadItems({ keepSelection: false });
        });
        monthWrap.childrenBox.appendChild(row);
      });
      yearWrap.childrenBox.appendChild(monthWrap.root);
    });
    els.tree.appendChild(yearWrap.root);
  });
}

function createTreeGroup(label, count) {
  const root = document.createElement("div");
  const row = createTreeRow(label, count, true);
  const childrenBox = document.createElement("div");
  childrenBox.className = "treeChildren open";
  row.querySelector(".arrow").classList.add("open");
  row.addEventListener("click", () => {
    childrenBox.classList.toggle("open");
    row.querySelector(".arrow").classList.toggle("open");
  });
  root.appendChild(row);
  root.appendChild(childrenBox);
  return { root, childrenBox };
}

function createTreeRow(label, count, expandable) {
  const row = document.createElement("button");
  row.className = "treeRow";
  row.type = "button";
  row.innerHTML = `
    <span class="arrow">${expandable ? ">" : ""}</span>
    <span class="treeLabel">${escapeHtml(label)}</span>
    <span class="treeCount">${count || ""}</span>
  `;
  return row;
}

function renderSources() {
  if (!state.collectors.length) {
    els.sources.innerHTML = '<div class="empty">没有 collector 配置。</div>';
    return;
  }
  els.sources.innerHTML = "";
  state.collectors.forEach((collector) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "sourceRow";
    row.classList.toggle("selected", state.selectedSource === collector.name);
    const run = collector.latest_run;
    const stateLabel = run ? (run.status === "error" ? "err" : `+${run.new_count || 0}`) : (collector.enabled ? "never" : "off");
    const stateClass = run?.status === "error" ? "run-error" : collector.enabled ? "enabled" : "disabled";
    row.title = run?.errors?.length ? run.errors.join(" | ") : `${collector.name} ${stateLabel}`;
    row.innerHTML = `
      <span></span>
      <span class="sourceName">${escapeHtml(collector.display_name || collector.name)}</span>
      <span class="sourceState ${stateClass}">${escapeHtml(stateLabel)}</span>
    `;
    row.addEventListener("click", () => {
      state.selectedSource = state.selectedSource === collector.name ? "" : collector.name;
      state.pagination.offset = 0;
      renderSources();
      loadItems({ keepSelection: false });
    });
    els.sources.appendChild(row);
  });
}

function renderFilters() {
  renderFilter("source", "Source", sourceLabel(),
    [{ value: "", label: "All sources" }, ...state.facets.sources.map((value) => ({ value, label: value }))],
    (value) => { state.selectedSource = value; state.pagination.offset = 0; renderSources(); loadItems({ keepSelection: false }); });
  renderFilter("category", "Category", state.selectedCategory || "All categories",
    [{ value: "", label: "All categories" }, ...state.facets.categories.map((value) => ({ value, label: value }))],
    (value) => { state.selectedCategory = value; state.pagination.offset = 0; loadItems({ keepSelection: false }); });
  renderFilter("minScore", "Score", scoreLabel(state.minScore),
    scoreOptions,
    (value) => { state.minScore = value; state.pagination.offset = 0; loadItems({ keepSelection: false }); });
}

function renderFilter(id, label, currentLabel, options, onSelect) {
  const root = document.querySelector(`.filterMenu[data-filter="${id}"]`);
  root.innerHTML = "";
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "filterTrigger";
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", state.openFilter === id ? "true" : "false");
  trigger.innerHTML = `
    <span>
      <span class="filterKicker">${escapeHtml(label)}</span>
      <span class="filterValue">${escapeHtml(currentLabel)}</span>
    </span>
    <span>⌄</span>
  `;
  const list = document.createElement("div");
  list.className = "filterList";
  list.classList.toggle("open", state.openFilter === id);
  list.setAttribute("role", "listbox");
  options.forEach((option) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "filterOption";
    item.classList.toggle("selected", option.value === filterValue(id));
    item.setAttribute("role", "option");
    item.setAttribute("aria-selected", option.value === filterValue(id) ? "true" : "false");
    item.textContent = option.label;
    item.addEventListener("click", (event) => {
      event.stopPropagation();
      closeFilter();
      onSelect(option.value);
    });
    list.appendChild(item);
  });
  trigger.addEventListener("click", (event) => {
    event.stopPropagation();
    state.openFilter = state.openFilter === id ? null : id;
    renderFilters();
  });
  root.appendChild(trigger);
  root.appendChild(list);
}

function renderItems() {
  if (!state.items.length) {
    const scope = state.selectedDate || "全部日期";
    els.items.innerHTML = `<div class="empty">${escapeHtml(scope)} 下没有匹配的信息。可以清空过滤器、换关键词，或先运行采集/分析。</div>`;
    return;
  }
  els.items.innerHTML = "";
  state.items.forEach((item) => {
    const coverUrl = extractCoverUrl(item);
    const row = document.createElement("button");
    row.type = "button";
    row.className = "itemRow";
    row.classList.toggle("hasCover", Boolean(coverUrl));
    row.classList.toggle("selected", state.selectedItem?.id === item.id);
    row.innerHTML = `
      ${coverUrl ? `<span class="itemCover"><img src="${escapeAttr(coverUrl)}" alt="" loading="lazy" onerror="this.closest('.itemRow').classList.remove('hasCover'); this.closest('.itemCover').remove();"></span>` : ""}
      <span class="minBlock">
        <span class="itemTitle">${escapeHtml(item.title)}</span>
        <span class="itemSummary">${escapeHtml(contentPreview(item) || "未分析")}</span>
        <span class="itemMeta">
          <span>${escapeHtml(item.source || "")}</span>
          <span>${escapeHtml(item.category || "未分析")}</span>
          <span>${formatTime(item.collected_at)}</span>
        </span>
      </span>
      <span class="scoreStack">
        <span class="scorePill" title="Preference score"><span>偏好</span><span class="scoreStrong">${formatScore(item.preference_score)}</span></span>
        <span class="scorePill" title="Relevance score"><span>相关</span><span>${formatScore(item.score)}</span></span>
      </span>
    `;
    row.addEventListener("click", () => {
      state.selectedItem = item;
      renderItems();
      renderDetail();
      setMode("detail");
    });
    els.items.appendChild(row);
  });
}

function renderDetail() {
  const item = state.selectedItem;
  if (!item) {
    els.detailHeader.textContent = "Detail";
    els.detailSub.textContent = "没有选中信息";
    els.openBtn.disabled = true;
    els.detailBody.innerHTML = '<div class="empty">当前过滤条件下没有信息。</div>';
    return;
  }
  els.detailHeader.textContent = item.source || "Item";
  els.detailSub.textContent = item.category || "未分析";
  els.openBtn.disabled = !item.url;
  const cleanedContent = item.clean_content || cleanContentText(item.content || "");
  const contentHtml = cleanedContent
    ? cleanedContent.split(/\n{2,}/).slice(0, 8).map((part) => `<p>${escapeHtml(part)}</p>`).join("")
    : "<p>暂无正文摘要。可以打开原文查看完整上下文。</p>";
  els.detailBody.innerHTML = `
    <h2 class="detailTitle">${escapeHtml(item.title)}</h2>
    <a class="detailUrl" href="${escapeAttr(item.url || "#")}" target="_blank" rel="noopener">${escapeHtml(item.url || "")}</a>
    <div class="detailGrid">
      <div class="metric"><div class="metricLabel">Preference</div><div class="metricValue">${formatScore(item.preference_score)}/10</div></div>
      <div class="metric"><div class="metricLabel">Score</div><div class="metricValue">${formatScore(item.score)}/10</div></div>
      <div class="metric"><div class="metricLabel">Source</div><div class="metricValue">${escapeHtml(item.source || "")}</div></div>
      <div class="metric"><div class="metricLabel">Collected</div><div class="metricValue">${formatTime(item.collected_at)}</div></div>
    </div>
    <div class="detailSection"><h3>Summary</h3><p>${escapeHtml(item.summary || "未分析")}</p></div>
    <div class="detailSection"><h3>Why Relevant</h3><p>${escapeHtml(item.why_relevant || "暂无")}</p></div>
    <div class="detailSection"><h3>Risk</h3><p>${escapeHtml(item.risk || "暂无")}</p></div>
    <div class="detailSection"><h3>Content</h3>${contentHtml}</div>
    <div class="detailSection"><h3>Tags</h3><div class="tags">${(item.tags || []).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("") || '<span class="tag">none</span>'}</div></div>
  `;
}

function updateHeader() {
  const pageStart = state.pagination.total ? state.pagination.offset + 1 : 0;
  const pageEnd = state.pagination.offset + state.pagination.returned;
  els.viewTitle.textContent = state.selectedDate ? `Items / ${state.selectedDate}` : "Items / all dates";
  const filters = [state.selectedSource || "all sources", state.selectedCategory || "all categories", scoreLabel(state.minScore)];
  if (state.query) filters.unshift(`search: ${state.query}`);
  els.viewMeta.textContent = `${state.pagination.total} matches | ${filters.join(" | ")}`;
  els.resultMeta.textContent = `${pageStart}-${pageEnd} / ${state.pagination.total}`;
  els.prevPage.disabled = state.pagination.offset <= 0;
  els.nextPage.disabled = !state.pagination.has_more;
}

function closeFilter() {
  if (!state.openFilter) return;
  state.openFilter = null;
  renderFilters();
}

function setRunMessage(message) {
  els.viewMeta.textContent = message;
}

function filterValue(id) {
  if (id === "source") return state.selectedSource;
  if (id === "category") return state.selectedCategory;
  return state.minScore;
}

function sourceLabel() {
  if (!state.selectedSource) return "All sources";
  const collector = state.collectors.find((item) => item.name === state.selectedSource);
  return collector?.display_name || state.selectedSource;
}

function scoreLabel(value) {
  return scoreOptions.find((option) => option.value === value)?.label || "All scores";
}

function contentPreview(item) {
  return item.preview_text || item.summary || cleanContentText(item.content || "").slice(0, 180);
}

function cleanContentText(value) {
  const raw = String(value || "");
  if (!raw) return "";
  let text = raw;
  if (/<[a-z][\s\S]*>/i.test(raw)) {
    const doc = new DOMParser().parseFromString(raw, "text/html");
    doc.querySelectorAll("script, style, noscript, iframe, svg, img, picture, video, audio, small, .lightbox-wrapper").forEach((node) => node.remove());
    text = doc.body.textContent || "";
  }
  return text
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n[ \t]+/g, "\n")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/阅读完整话题/g, "")
    .replace(/\d+\s*个帖子\s*-\s*\d+\s*位参与者/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function extractCoverUrl(item) {
  if (item.image_url) return item.image_url;
  const raw = String(item.content || "");
  if (!/<[a-z][\s\S]*>/i.test(raw)) return "";
  const doc = new DOMParser().parseFromString(raw, "text/html");
  const img = Array.from(doc.images).find((node) => {
    const src = node.getAttribute("src") || "";
    return src.startsWith("http://") || src.startsWith("https://");
  });
  return img?.getAttribute("src") || "";
}

function formatScore(value) {
  const number = Number(value || 0);
  return Number.isInteger(number) ? String(number) : number.toFixed(1);
}

function formatTime(value) {
  if (!value) return "n/a";
  return new Date(value * 1000).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderMarkdown(markdown) {
  const lines = String(markdown || "").split(/\r?\n/);
  const html = [];
  let inList = false;
  let inCode = false;
  let codeLines = [];
  const closeList = () => {
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
  };
  lines.forEach((line) => {
    if (line.startsWith("```")) {
      if (inCode) {
        html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
        codeLines = [];
        inCode = false;
      } else {
        closeList();
        inCode = true;
      }
      return;
    }
    if (inCode) {
      codeLines.push(line);
      return;
    }
    if (!line.trim()) {
      closeList();
      return;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      closeList();
      html.push(`<h${heading[1].length}>${inlineMarkdown(heading[2])}</h${heading[1].length}>`);
      return;
    }
    const bullet = line.match(/^\s*[-*]\s+(.+)$/);
    if (bullet) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${inlineMarkdown(bullet[1])}</li>`);
      return;
    }
    if (line.startsWith("> ")) {
      closeList();
      html.push(`<blockquote>${inlineMarkdown(line.slice(2))}</blockquote>`);
      return;
    }
    closeList();
    html.push(`<p>${inlineMarkdown(line)}</p>`);
  });
  closeList();
  if (inCode) html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
  return html.join("");
}

function inlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}

function debounce(fn, delay) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#096;");
}

init();
