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

/** Polite status for keyboard reorder. Lives outside #root so a re-render keeps it. */
function announce(message: string): void {
  let live = document.getElementById("mt-live");
  if (!live) {
    live = document.createElement("div");
    live.id = "mt-live";
    live.className = "sr-only";
    live.setAttribute("role", "status");
    live.setAttribute("aria-live", "polite");
    document.body.appendChild(live);
  }
  live.textContent = "";
  window.setTimeout(() => {
    if (live) live.textContent = message;
  }, 30);
}

/**
 * Tabs pattern: Left/Right/Home/End move focus, Enter/Space open, Delete closes.
 * Shift+Left / Shift+Right move the focused mix tab one slot (reorder without a mouse).
 */
function bindTabStripKeys(bar: HTMLElement): void {
  bar.addEventListener("keydown", (ev: KeyboardEvent) => {
    const stops = tabStops(bar);
    const current = (ev.target as HTMLElement).closest<HTMLElement>('[role="tab"]');
    const idx = current ? stops.indexOf(current) : -1;
    if (idx < 0) return;
    if (ev.shiftKey && (ev.key === "ArrowLeft" || ev.key === "ArrowRight")) {
      const id = current!.dataset.id;
      if (!id) return; // Home is not a mix tab and never moves.
      ev.preventDefault();
      const mixTabs = Array.from(bar.querySelectorAll<HTMLElement>(".mix-tab"));
      const here = mixTabs.indexOf(current!);
      const to = ev.key === "ArrowLeft" ? here - 1 : here + 1;
      const label = current!.querySelector(".title")?.textContent || "Mix";
      if (to < 0 || to >= mixTabs.length) {
        announce(`${label} is already ${to < 0 ? "first" : "last"}`);
        return;
      }
      announce(`${label} moved to position ${to + 1} of ${mixTabs.length}`);
      report("reorder", id, to);
      return;
    }
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

function report(action: string, id?: string, to?: number): void {
  const payload: { action: string; id?: string; to?: number; seq: number } = {
    action,
    seq: nextSeq(),
  };
  if (id != null) payload.id = id;
  if (to != null) payload.to = to;
  Streamlit.setComponentValue(payload);
}

let dragId: string | null = null;

function clearDragMarks(bar: HTMLElement, includeDragging: boolean): void {
  const selector = includeDragging ? ".dragging, .drop-before, .drop-after" : ".drop-before, .drop-after";
  bar.querySelectorAll<HTMLElement>(selector).forEach((el) => {
    el.classList.remove("drop-before", "drop-after");
    if (includeDragging) el.classList.remove("dragging");
  });
}

/** Where a pointer would drop: before/after a tab, or the end (plus / empty space). */
function dropTarget(
  bar: HTMLElement,
  ev: DragEvent,
): { slot: number; mark: HTMLElement | null; after: boolean } | null {
  const tabs = Array.from(bar.querySelectorAll<HTMLElement>(".mix-tab"));
  const raw = ev.target;
  const el = raw instanceof Element ? raw : null;
  const over = el?.closest<HTMLElement>(".mix-tab") ?? null;
  if (over) {
    const rect = over.getBoundingClientRect();
    const after = ev.clientX > rect.left + rect.width / 2;
    const at = tabs.indexOf(over);
    return { slot: after ? at + 1 : at, mark: over, after };
  }
  // Past the last tab means "last". Home and anything else is not a drop zone.
  if (el?.closest(".plus-btn, .spacer") && tabs.length) {
    return { slot: tabs.length, mark: tabs[tabs.length - 1], after: true };
  }
  return null;
}

/** Drag a mix tab to reorder. A drop anywhere else cancels and the tab stays put. */
function bindTabStripDrag(bar: HTMLElement): void {
  bar.addEventListener("dragstart", (ev: DragEvent) => {
    const raw = ev.target;
    const tab = raw instanceof Element ? raw.closest<HTMLElement>(".mix-tab") : null;
    if (!tab?.dataset.id) return;
    dragId = tab.dataset.id;
    tab.classList.add("dragging");
    if (ev.dataTransfer) {
      ev.dataTransfer.effectAllowed = "move";
      ev.dataTransfer.setData("text/plain", dragId);
    }
  });
  bar.addEventListener("dragover", (ev: DragEvent) => {
    if (!dragId) return;
    clearDragMarks(bar, false);
    const hit = dropTarget(bar, ev);
    if (!hit) return; // no preventDefault: the browser shows "not allowed"
    ev.preventDefault();
    if (ev.dataTransfer) ev.dataTransfer.dropEffect = "move";
    hit.mark?.classList.add(hit.after ? "drop-after" : "drop-before");
  });
  bar.addEventListener("drop", (ev: DragEvent) => {
    if (!dragId) return;
    const id = dragId;
    dragId = null;
    const hit = dropTarget(bar, ev);
    const tabs = Array.from(bar.querySelectorAll<HTMLElement>(".mix-tab"));
    const from = tabs.findIndex((el) => el.dataset.id === id);
    clearDragMarks(bar, true);
    if (!hit || from < 0) return;
    ev.preventDefault();
    const to = hit.slot > from ? hit.slot - 1 : hit.slot;
    if (to !== from) {
      const label = tabs[from].querySelector(".title")?.textContent || "Mix";
      announce(`${label} moved to position ${to + 1} of ${tabs.length}`);
      report("reorder", id, to);
    }
  });
  bar.addEventListener("dragend", () => {
    dragId = null;
    clearDragMarks(bar, true);
  });
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
        <div class="mix-tab${active ? " active" : ""}${busyClass}" data-id="${escapeHtml(id)}" data-focus-key="tab:${escapeHtml(id)}" role="tab" draggable="true" tabindex="${active ? 0 : -1}" aria-selected="${active}"${ariaBusy}>
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
    <div class="mix-tab-shell">
      <div class="mix-tab-wrap">
        <div class="mix-tab-bar" role="tablist" aria-label="Open mixes. Shift plus left or right arrow moves the focused tab.">
          <button type="button" class="home-btn${homeActive ? " active" : ""}" data-action="home" data-focus-key="home" role="tab" tabindex="${homeActive ? 0 : -1}" aria-selected="${homeActive}">
            ${homeIcon()}
            <span>${escapeHtml(homeLabel)}</span>
          </button>
          ${tabHtml}
          ${showPlus ? `<button type="button" class="plus-btn" data-action="plus" title="New tab" aria-label="New tab">+</button>` : ""}
          <span class="spacer"></span>
        </div>
      </div>
    </div>
  `;

  const wrap = root.querySelector<HTMLElement>(".mix-tab-wrap");
  const bar = root.querySelector<HTMLElement>(".mix-tab-bar");
  if (wrap && bar) {
    bindTabStripWheel(bar);
    bindTabStripKeys(bar);
    bindTabStripDrag(bar);
    const stops = tabStops(bar);
    if (!stops.some((el) => el.getAttribute("tabindex") === "0") && stops[0]) {
      stops[0].setAttribute("tabindex", "0");
    }
    bar.scrollLeft = prevScroll;
    const selected = bar.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]');
    selected?.scrollIntoView({ block: "nearest", inline: "nearest" });
    if (focusedKey) {
      const target = root.querySelector<HTMLElement>(
        `[data-focus-key="${CSS.escape(focusedKey)}"]`,
      );
      target?.focus();
      // The focused control may be gone (closed tab) or disabled (no tabs left to
      // close). Keep keyboard focus in the strip instead of dropping it.
      if (document.activeElement !== target) selected?.focus();
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
