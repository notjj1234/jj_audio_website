import { Streamlit, RenderData, Theme } from "streamlit-component-lib";
import "./style.css";

type TabInfo = {
  id: string;
  title: string;
  active?: boolean;
};

type Args = {
  homeLabel?: string;
  homeActive?: boolean;
  showPlus?: boolean;
  tabs?: TabInfo[];
};

function applyTheme(theme?: Theme): void {
  if (!theme) return;
  const root = document.documentElement;
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
  return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8 12h8M12 8v8"/></svg>`;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function report(action: string, id?: string): void {
  const payload: { action: string; id?: string } = { action };
  if (id != null) payload.id = id;
  Streamlit.setComponentValue(payload);
}

function renderUI(args: Args): void {
  const root = document.getElementById("root");
  if (!root) return;
  const homeLabel = args.homeLabel || "Home";
  const homeActive = !!args.homeActive;
  const showPlus = args.showPlus !== false;
  const tabs = Array.isArray(args.tabs) ? args.tabs : [];

  const tabHtml = tabs
    .map((t) => {
      const id = String(t.id || "");
      const title = escapeHtml(String(t.title || id || "Mix"));
      const active = !!t.active && !homeActive;
      return `
        <div class="mix-tab${active ? " active" : ""}" data-id="${escapeHtml(id)}" role="tab" aria-selected="${active}">
          ${docIcon()}
          <span class="title" title="${title}">${title}</span>
          <button type="button" class="close" data-close="${escapeHtml(id)}" aria-label="Close tab" title="Close tab">×</button>
        </div>`;
    })
    .join("");

  root.innerHTML = `
    <div class="mix-tab-bar" role="tablist">
      <button type="button" class="home-btn${homeActive ? " active" : ""}" data-action="home">
        ${homeIcon()}
        <span>${escapeHtml(homeLabel)}</span>
      </button>
      ${tabHtml}
      ${showPlus ? `<button type="button" class="plus-btn" data-action="plus" title="New" aria-label="New">+</button>` : ""}
      <span class="spacer"></span>
    </div>
  `;

  root.querySelector('[data-action="home"]')?.addEventListener("click", () => {
    report("home");
  });
  root.querySelector('[data-action="plus"]')?.addEventListener("click", () => {
    report("plus");
  });
  root.querySelectorAll<HTMLElement>(".mix-tab").forEach((el) => {
    el.addEventListener("click", (ev) => {
      const target = ev.target as HTMLElement;
      if (target.closest("[data-close]")) return;
      const id = el.dataset.id;
      if (id) report("focus", id);
    });
  });
  root.querySelectorAll<HTMLElement>("[data-close]").forEach((btn) => {
    btn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const id = btn.getAttribute("data-close");
      if (id) report("close", id);
    });
  });

  requestAnimationFrame(() => Streamlit.setFrameHeight());
}

function onRender(event: Event): void {
  const data = (event as CustomEvent<RenderData>).detail;
  applyTheme(data.theme);
  renderUI((data.args || {}) as Args);
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
Streamlit.setFrameHeight(48);
