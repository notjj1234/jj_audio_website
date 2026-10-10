import { Streamlit, RenderData, Theme } from "streamlit-component-lib";
import "./style.css";

type TabInfo = {
  id: string;
  title: string;
  active?: boolean;
  /** True while a separation job is bound to this draft tab. */
  busy?: boolean;
  /** 0–1 when running; omit for indeterminate (queued / paused). */
  progress?: number | null;
};

type Args = {
  homeLabel?: string;
  homeActive?: boolean;
  showPlus?: boolean;
  tabs?: TabInfo[];
};

function applyTheme(theme?: Theme): void {
  const root = document.documentElement;
  if (!theme) return;
  if (theme.backgroundColor) {
    root.style.setProperty("--mt-bar", theme.backgroundColor);
    root.style.setProperty("--mt-bg", theme.backgroundColor);
  }
  if (theme.secondaryBackgroundColor) {
    root.style.setProperty("--mt-active", theme.secondaryBackgroundColor);
    root.style.setProperty("--mt-hover", theme.secondaryBackgroundColor);
  }
  if (theme.textColor) root.style.setProperty("--mt-fg", theme.textColor);
  if (theme.primaryColor) root.style.setProperty("--mt-accent", theme.primaryColor);
}

function homeIcon(): string {
  return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1v-10.5z"/></svg>`;
}

function docIcon(): string {
  return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M7 3h8l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M15 3v6h6"/><path d="M9 13h6M9 17h6"/></svg>`;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function clampProgress(raw: unknown): number | null {
  if (raw == null || raw === "") return null;
  const n = Number(raw);
  if (!Number.isFinite(n)) return null;
  return Math.min(1, Math.max(0, n));
}

function progressMarkup(busy: boolean, progress: number | null): string {
  if (!busy) return "";
  if (progress == null) {
    return `<span class="tab-progress indeterminate" aria-hidden="true"><span class="tab-progress-bar"></span></span>`;
  }
  const pct = Math.round(progress * 100);
  return `<span class="tab-progress" style="--mt-progress:${pct}%" aria-hidden="true"><span class="tab-progress-bar"></span></span>`;
}

let lastSeq = 0;

function nextSeq(): number {
  let seq = Date.now();
  if (seq <= lastSeq) seq = lastSeq + 1;
  lastSeq = seq;
  return seq;
}

/** Wheel over the strip scrolls tabs sideways and leaves the page still. */
function bindTabStripWheel(bar: HTMLElement): void {
  bar.addEventListener(
    "wheel",
    (ev: WheelEvent) => {
      const maxScroll = bar.scrollWidth - bar.clientWidth;
      if (maxScroll <= 1) return;
      const delta =
        Math.abs(ev.deltaX) > Math.abs(ev.deltaY) ? ev.deltaX : ev.deltaY;
      if (delta === 0) return;
      ev.preventDefault();
      bar.scrollLeft += delta;
    },
    { passive: false },
  );
}

/** Edge fades tell the user more tabs are off screen on that side. */
function updateOverflowFades(wrap: HTMLElement, bar: HTMLElement): void {
  const max = bar.scrollWidth - bar.clientWidth;
  wrap.classList.toggle("fade-left", max > 1 && bar.scrollLeft > 1);
  wrap.classList.toggle("fade-right", max > 1 && bar.scrollLeft < max - 1);
}

function tabStops(bar: HTMLElement): HTMLElement[] {
  return Array.from(bar.querySelectorAll<HTMLElement>('[role="tab"]'));
}

/** Tabs pattern: Left/Right/Home/End move focus, Enter/Space open, Delete closes. */
function bindTabStripKeys(bar: HTMLElement): void {
  bar.addEventListener("keydown", (ev: KeyboardEvent) => {
    const stops = tabStops(bar);
    const current = (ev.target as HTMLElement).closest<HTMLElement>('[role="tab"]');
    const idx = current ? stops.indexOf(current) : -1;
    if (idx < 0) return;
    let next = -1;
    if (ev.key === "ArrowRight") next = (idx + 1) % stops.length;
    else if (ev.key === "ArrowLeft") next = (idx - 1 + stops.length) % stops.length;
    else if (ev.key === "Home") next = 0;
    else if (ev.key === "End") next = stops.length - 1;
    else if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      current!.click();
      return;
    } else if (ev.key === "Delete") {
      const id = current!.dataset.id;
      if (id) {
        ev.preventDefault();
        report("close", id);
      }
      return;
    } else return;
    ev.preventDefault();
    stops.forEach((el, i) => el.setAttribute("tabindex", i === next ? "0" : "-1"));
    stops[next].focus();
    stops[next].scrollIntoView({ block: "nearest", inline: "nearest" });
  });
}

function report(action: string, id?: string): void {
  const payload: { action: string; id?: string; seq: number } = {
    action,
    seq: nextSeq(),
  };
  if (id != null) payload.id = id;
  Streamlit.setComponentValue(payload);
}

/** One listener on the strip root, so in-place tab updates cannot drop the X. */
function ensureStripClicks(root: HTMLElement): void {
  if (root.dataset.clicks === "1") return;
  root.dataset.clicks = "1";
  root.addEventListener("click", (ev) => {
    const raw = ev.target;
    const target =
      raw instanceof Element ? raw : (raw as Node | null)?.parentElement ?? null;
    if (!target) return;
    const closer = target.closest<HTMLElement>("[data-close]");
    if (closer) {
      ev.preventDefault();
      ev.stopPropagation();
      const id = closer.getAttribute("data-close");
      if (id) report("close", id);
      return;
    }
    const tab = target.closest<HTMLElement>(".mix-tab");
    if (tab?.dataset.id) {
      report("focus", tab.dataset.id);
      return;
    }
    const action = target.closest<HTMLElement>("[data-action]")?.getAttribute("data-action");
    if (action === "home") report("home");
    else if (action === "plus") report("plus");
  });
}

/** Home label, plus button, and tab ids. Busy/progress can change without this. */
function structureKey(homeLabel: string, showPlus: boolean, tabs: TabInfo[]): string {
  return JSON.stringify({
    homeLabel,
    showPlus,
    ids: tabs.map((t) => String(t.id || "")),
  });
}

/** Keep an indeterminate bar node so its animation does not restart. */
function syncProgress(el: HTMLElement, busy: boolean, progress: number | null): void {
  const existing = el.querySelector<HTMLElement>(".tab-progress");
  if (!busy) {
    existing?.remove();
    return;
  }
  if (progress == null) {
    if (existing?.classList.contains("indeterminate")) return;
    existing?.remove();
    el.insertAdjacentHTML("beforeend", progressMarkup(true, null));
    return;
  }
  const pct = `${Math.round(progress * 100)}%`;
  if (existing && !existing.classList.contains("indeterminate")) {
    existing.style.setProperty("--mt-progress", pct);
    return;
  }
  existing?.remove();
  el.insertAdjacentHTML("beforeend", progressMarkup(true, progress));
}

/**
 * Patch busy state on the existing strip when the tabs themselves did not change.
 * Replacing innerHTML restarts the indeterminate bar.
 */
function updateTabsInPlace(root: HTMLElement, args: Args, tabs: TabInfo[]): boolean {
  const homeLabel = args.homeLabel || "Home";
  const homeActive = !!args.homeActive;
  const showPlus = args.showPlus !== false;
  if (root.dataset.structure !== structureKey(homeLabel, showPlus, tabs)) return false;

  const homeBtn = root.querySelector<HTMLElement>('[data-action="home"]');
  if (!homeBtn) return false;
  const nodes: HTMLElement[] = [];
  for (const t of tabs) {
    const id = String(t.id || "");
    const el = root.querySelector<HTMLElement>(`.mix-tab[data-id="${CSS.escape(id)}"]`);
    if (!el) return false;
    nodes.push(el);
  }

  homeBtn.classList.toggle("active", homeActive);
  homeBtn.setAttribute("aria-selected", homeActive ? "true" : "false");
  homeBtn.setAttribute("tabindex", homeActive ? "0" : "-1");

  tabs.forEach((t, i) => {
    const el = nodes[i];
    if (!el) return;
    const id = String(t.id || "");
    const title = String(t.title || id || "Mix");
    const active = !!t.active && !homeActive;
    const busy = !!t.busy;
    const progress = clampProgress(t.progress);
    el.classList.toggle("active", active);
    el.classList.toggle("busy", busy);
    el.setAttribute("aria-selected", active ? "true" : "false");
    el.setAttribute("tabindex", active ? "0" : "-1");
    if (busy) el.setAttribute("aria-busy", "true");
    else el.removeAttribute("aria-busy");
    const titleEl = el.querySelector<HTMLElement>(".title");
    if (titleEl) {
      titleEl.textContent = title;
      titleEl.setAttribute("title", title);
    }
    const close = el.querySelector<HTMLElement>("[data-close]");
    if (close) close.setAttribute("aria-label", `Close ${title}`);
    syncProgress(el, busy, progress);
  });

  const wrap = root.querySelector<HTMLElement>(".mix-tab-wrap");
  const bar = root.querySelector<HTMLElement>(".mix-tab-bar");
  if (wrap && bar) {
    updateOverflowFades(wrap, bar);
    const selected = bar.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]');
    selected?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
  requestAnimationFrame(() => Streamlit.setFrameHeight());
  return true;
}

function renderUI(args: Args): void {
  const root = document.getElementById("root");
  if (!root) return;
  ensureStripClicks(root);
  const homeLabel = args.homeLabel || "Home";
  const homeActive = !!args.homeActive;
  const showPlus = args.showPlus !== false;
  const tabs = Array.isArray(args.tabs) ? args.tabs : [];
  if (updateTabsInPlace(root, args, tabs)) return;

  const tabHtml = tabs
    .map((t) => {
      const id = String(t.id || "");
      const title = escapeHtml(String(t.title || id || "Mix"));
      const active = !!t.active && !homeActive;
      const busy = !!t.busy;
      const progress = clampProgress(t.progress);
      const busyClass = busy ? " busy" : "";
      const ariaBusy = busy ? ` aria-busy="true"` : "";
      return `
        <div class="mix-tab${active ? " active" : ""}${busyClass}" data-id="${escapeHtml(id)}" data-focus-key="tab:${escapeHtml(id)}" role="tab" tabindex="${active ? 0 : -1}" aria-selected="${active}"${ariaBusy}>
          ${docIcon()}
          <span class="title" title="${title}">${title}</span>
          <button type="button" class="close" data-close="${escapeHtml(id)}" tabindex="-1" aria-label="Close ${title}" title="Close tab">×</button>
          ${progressMarkup(busy, progress)}
        </div>`;
    })
    .join("");

  const focusedKey = (document.activeElement as HTMLElement | null)?.dataset?.focusKey;
  const prevBar = root.querySelector<HTMLElement>(".mix-tab-bar");
  const prevScroll = prevBar ? prevBar.scrollLeft : 0;

  root.innerHTML = `
    <div class="mix-tab-wrap">
      <div class="mix-tab-bar" role="tablist" aria-label="Open mixes">
        <button type="button" class="home-btn${homeActive ? " active" : ""}" data-action="home" data-focus-key="home" role="tab" tabindex="${homeActive ? 0 : -1}" aria-selected="${homeActive}">
          ${homeIcon()}
          <span>${escapeHtml(homeLabel)}</span>
        </button>
        ${tabHtml}
        ${showPlus ? `<button type="button" class="plus-btn" data-action="plus" title="New tab" aria-label="New tab">+</button>` : ""}
        <span class="spacer"></span>
      </div>
    </div>
  `;

  const wrap = root.querySelector<HTMLElement>(".mix-tab-wrap");
  const bar = root.querySelector<HTMLElement>(".mix-tab-bar");
  if (wrap && bar) {
    bindTabStripWheel(bar);
    bindTabStripKeys(bar);
    const stops = tabStops(bar);
    if (!stops.some((el) => el.getAttribute("tabindex") === "0") && stops[0]) {
      stops[0].setAttribute("tabindex", "0");
    }
    bar.scrollLeft = prevScroll;
    const selected = bar.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]');
    selected?.scrollIntoView({ block: "nearest", inline: "nearest" });
    if (focusedKey) {
      bar.querySelector<HTMLElement>(`[data-focus-key="${CSS.escape(focusedKey)}"]`)?.focus();
    }
    bar.addEventListener("scroll", () => updateOverflowFades(wrap, bar), { passive: true });
    updateOverflowFades(wrap, bar);
  }

  root.dataset.structure = structureKey(homeLabel, showPlus, tabs);
  requestAnimationFrame(() => Streamlit.setFrameHeight());
}

function onRender(event: Event): void {
  const data = (event as CustomEvent<RenderData>).detail;
  applyTheme(data.theme);
  renderUI((data.args || {}) as Args);
}

window.addEventListener("resize", () => {
  const wrap = document.querySelector<HTMLElement>(".mix-tab-wrap");
  const bar = document.querySelector<HTMLElement>(".mix-tab-bar");
  if (wrap && bar) updateOverflowFades(wrap, bar);
});

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
Streamlit.setFrameHeight(48);
