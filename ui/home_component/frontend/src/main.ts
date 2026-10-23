import { Streamlit, RenderData } from "streamlit-component-lib";
import "./style.css";

type Row = {
  token: string;
  title: string;
  subtitle: string;
  age: string;
  action: "practice" | "analyse" | string;
};

type Card = {
  id: string;
  title: string;
  subtitle: string;
  primary?: boolean;
};

type Flash = { message?: string; error?: boolean } | null;

type Props = {
  nonce?: string;
  product?: string;
  cards?: Card[];
  recents?: Row[];
  rows?: Row[];
  loading?: boolean;
  flash?: Flash;
};

type MenuState = {
  kind: "row" | "sort";
  token: string;
  focusId: string;
  x: number;
  y: number;
};

const ICONS = {
  wave: "<path d='M1 10h2.4V7.2H1zm3.6-5.2h2.4V13H4.6zm3.6 2.6h2.4v7.2H8.2zM11.8 2.2H14.2V14h-2.4z'/>",
  save: "<path d='M7.2.8h2.2v6.4h2.8L8.3 11.6 4.4 7.2h2.8zM2.2 12.4h12.2V15.2H2.2z'/>",
  doc: "<path d='M3.2 1h6.4L13.6 5.2V15H3.2zM9.2 1.4V5.6h4'/>",
  search: "<path fill-rule='evenodd' d='M7 1.4a4.4 4.4 0 1 0 2.7 7.9l3.2 3.2 1.2-1.2-3.2-3.2A4.4 4.4 0 0 0 7 1.4zm0 2a2.4 2.4 0 1 1 0 4.8 2.4 2.4 0 0 1 0-4.8z'/>",
  sort: "<path d='M2 3h12v2H2zm0 4h8v2H2zm0 4h4v2H2z'/>",
  more: "<path d='M2.2 6.7h2.6v2.6H2.2zm4.5 0h2.6v2.6H6.7zm4.5 0H13.8v2.6h-2.6z'/>",
  chevL: "<path d='M10.2 2.2 5 8l5.2 5.8h2.2L7.4 8l5-5.8z'/>",
  chevR: "<path d='M5.8 2.2 11 8l-5.2 5.8H3.6L8.6 8l-5-5.8z'/>",
};

let query = "";
let sortOldest = false;
let menu: MenuState | null = null;
let restoreFocus = "";

function svg(name: keyof typeof ICONS, size: number): string {
  return (
    `<svg viewBox="0 0 16 16" width="${size}" height="${size}" aria-hidden="true" fill="currentColor">` +
    `${ICONS[name]}</svg>`
  );
}

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
}

function send(nonce: string, type: string, id: string): void {
  Streamlit.setComponentValue({ nonce, type, id });
}

function closeMenu(returnFocus: boolean): void {
  const focusId = menu?.focusId ?? "";
  menu = null;
  if (returnFocus) restoreFocus = focusId;
  paint(lastProps);
}

let lastProps: Props = {};

function rail(
  parent: HTMLElement,
  kind: "cards" | "recents",
  build: (scroller: HTMLElement) => void,
): void {
  const wrap = el("div", `rail ${kind}-rail`);
  const prev = el("button", "scroll prev");
  prev.type = "button";
  prev.dataset.focusid = `${kind}-prev`;
  prev.setAttribute("aria-label", kind === "cards" ? "Scroll actions back" : "Scroll recents back");
  prev.innerHTML = svg("chevL", 14);
  const next = el("button", "scroll next");
  next.type = "button";
  next.dataset.focusid = `${kind}-next`;
  next.setAttribute("aria-label", kind === "cards" ? "Scroll actions forward" : "Scroll recents forward");
  next.innerHTML = svg("chevR", 14);
  const scroller = el("div", "scroller");
  scroller.dataset.rail = kind;
  build(scroller);
  const sync = (): void => {
    const overflow = scroller.scrollWidth - scroller.clientWidth > 2;
    prev.classList.toggle("is-on", overflow && scroller.scrollLeft > 2);
    next.classList.toggle(
      "is-on",
      overflow && scroller.scrollLeft + scroller.clientWidth < scroller.scrollWidth - 2,
    );
    prev.tabIndex = prev.classList.contains("is-on") ? 0 : -1;
    next.tabIndex = next.classList.contains("is-on") ? 0 : -1;
  };
  prev.addEventListener("click", () => {
    scroller.scrollBy({ left: kind === "cards" ? -220 : -162, behavior: "auto" });
    sync();
  });
  next.addEventListener("click", () => {
    scroller.scrollBy({ left: kind === "cards" ? 220 : 162, behavior: "auto" });
    sync();
  });
  scroller.addEventListener("scroll", sync);
  wrap.append(prev, scroller, next);
  parent.append(wrap);
  requestAnimationFrame(sync);
}

function openMenu(state: MenuState): void {
  menu = state;
  restoreFocus = "";
  paint(lastProps);
  requestAnimationFrame(() => {
    document.querySelector<HTMLElement>(".menu button")?.focus();
  });
}

function paint(props: Props): void {
  lastProps = props;
  const nonce = props.nonce || "";
  const root = document.querySelector("#root");
  if (!root) return;
  root.replaceChildren();
  const home = el("div", "home");

  const cards = props.cards || [];
  rail(home, "cards", (scroller) => {
    cards.forEach((card) => {
      const button = el("button", "card");
      button.type = "button";
      button.dataset.card = card.id;
      button.dataset.focusid = `card-${card.id}`;
      button.title = card.subtitle || card.title;
      const glyph = el("span", "glyph");
      glyph.style.color = "#F6AD49";
      const icon = card.id === "youtube" ? "save" : card.id === "tab" ? "doc" : "wave";
      glyph.innerHTML = svg(icon, 20);
      const label = el("span", "label");
      label.textContent = card.title;
      button.append(glyph, label);
      button.addEventListener("click", () => send(nonce, "open_card", card.id));
      scroller.append(button);
    });
  });

  const recentsHeading = el("h2");
  recentsHeading.textContent = "Recents";
  home.append(recentsHeading);
  const recents = props.recents || [];
  rail(home, "recents", (scroller) => {
    recents.forEach((row) => {
      const button = el("button", "recent");
      button.type = "button";
      button.dataset.recent = row.token;
      button.dataset.focusid = `recent-${row.token}`;
      const art = el("span", "art");
      art.setAttribute("aria-hidden", "true");
      const title = el("span", "title");
      title.textContent = row.title;
      const meta = el("span", "meta");
      meta.textContent = row.age || "";
      button.append(art, title, meta);
      button.addEventListener("click", () => send(nonce, "open_recent", row.token));
      scroller.append(button);
    });
  });

  const head = el("div", "files-head");
  const filesHeading = el("h2");
  filesHeading.textContent = "Files";
  const toolbar = el("div", "toolbar");
  const all = el("button", "pill");
  all.type = "button";
  all.dataset.pill = "all";
  all.dataset.focusid = "pill-all";
  all.textContent = "All";
  all.setAttribute("aria-pressed", "true");
  const search = el("label", "search");
  search.appendChild(document.createRange().createContextualFragment(svg("search", 16)));
  const input = el("input");
  input.id = "home-search";
  input.type = "search";
  input.placeholder = "Search";
  input.value = query;
  input.dataset.focusid = "search";
  input.setAttribute("aria-label", "Search");
  input.addEventListener("input", () => {
    query = input.value;
    paint(lastProps);
    document.querySelector<HTMLInputElement>("#home-search")?.focus();
  });
  search.append(input);
  const sort = el("button", "icon-btn");
  sort.type = "button";
  sort.dataset.focusid = "sort";
  sort.setAttribute("aria-label", "Sort");
  sort.setAttribute("aria-haspopup", "menu");
  sort.innerHTML = svg("sort", 16);
  sort.addEventListener("click", () => {
    const box = sort.getBoundingClientRect();
    openMenu({ kind: "sort", token: "", focusId: "sort", x: box.left, y: box.bottom + 4 });
  });
  toolbar.append(all, search, sort);
  head.append(filesHeading, toolbar);
  home.append(head);

  if (props.flash && props.flash.message) {
    const alert = el("div", "alert");
    alert.setAttribute("role", "alert");
    alert.textContent = props.flash.message;
    home.append(alert);
  }

  const files = el("div", "files-scroll");
  if (props.loading) {
    for (let index = 0; index < 3; index += 1) {
      const bone = el("div", "skel");
      bone.dataset.skeleton = String(index);
      files.append(bone);
    }
  } else {
    const source = props.rows || [];
    const needle = query.trim().toLowerCase();
    let shown = source.filter((row) => {
      if (!needle) return true;
      return `${row.title} ${row.subtitle}`.toLowerCase().includes(needle);
    });
    shown = sortOldest ? [...shown].reverse() : shown;
    if (source.length === 0) {
      const empty = el("p", "empty");
      empty.textContent = "No songs yet.";
      files.append(empty);
    } else if (shown.length === 0) {
      const empty = el("p", "empty");
      empty.textContent = "No songs match that search.";
      files.append(empty);
    } else {
      const table = el("table");
      const thead = el("thead");
      const header = el("tr");
      const titleHead = el("th");
      titleHead.textContent = "Title";
      const createdHead = el("th", "col-created");
      createdHead.textContent = "Created";
      const actionHead = el("th", "col-action");
      actionHead.textContent = "";
      header.append(titleHead, createdHead, actionHead);
      thead.append(header);
      const body = el("tbody");
      shown.forEach((row) => {
        const tr = el("tr");
        tr.dataset.row = row.token;
        const titleCell = el("td");
        const opener = el("button", "row-open");
        opener.type = "button";
        opener.dataset.focusid = `row-${row.token}`;
        const name = el("span", "name");
        name.textContent = row.title;
        const sub = el("span", "sub");
        sub.textContent = row.subtitle || "";
        opener.append(name, sub);
        opener.addEventListener("click", () => send(nonce, "open_row", row.token));
        titleCell.append(opener);
        const created = el("td", "col-created");
        created.textContent = row.age || "";
        const action = el("td", "col-action");
        const kebab = el("button", "icon-btn");
        kebab.type = "button";
        kebab.dataset.focusid = `kebab-${row.token}`;
        kebab.setAttribute("aria-label", "Row actions");
        kebab.setAttribute("aria-haspopup", "menu");
        kebab.innerHTML = svg("more", 16);
        kebab.addEventListener("click", () => {
          const box = kebab.getBoundingClientRect();
          openMenu({
            kind: "row",
            token: row.token,
            focusId: `kebab-${row.token}`,
            x: Math.max(8, box.right - 180),
            y: box.bottom + 4,
          });
        });
        action.append(kebab);
        tr.append(titleCell, created, action);
        body.append(tr);
      });
      table.append(thead, body);
      files.append(table);
    }
  }
  home.append(files);
  root.append(home);

  if (menu) {
    const popup = el("div", "menu");
    popup.setAttribute("role", "menu");
    popup.style.left = `${menu.x}px`;
    popup.style.top = `${menu.y}px`;
    const items: { label: string; type: string; id: string }[] =
      menu.kind === "sort"
        ? [
            { label: "Newest", type: "sort-newest", id: "newest" },
            { label: "Oldest", type: "sort-oldest", id: "oldest" },
          ]
        : [
            { label: "Open", type: "open_row", id: menu.token },
            {
              label:
                (props.rows || []).find((row) => row.token === menu?.token)?.action === "practice"
                  ? "Practice"
                  : "Analyse",
              type:
                (props.rows || []).find((row) => row.token === menu?.token)?.action === "practice"
                  ? "practice"
                  : "analyse",
              id: menu.token,
            },
          ];
    items.forEach((item) => {
      const button = el("button");
      button.type = "button";
      button.setAttribute("role", "menuitem");
      button.textContent = item.label;
      button.addEventListener("click", () => {
        if (item.type === "sort-newest" || item.type === "sort-oldest") {
          sortOldest = item.type === "sort-oldest";
          closeMenu(true);
          return;
        }
        const type = item.type;
        const id = item.id;
        menu = null;
        send(nonce, type, id);
      });
      popup.append(button);
    });
    root.append(popup);
  }

  if (restoreFocus) {
    const id = restoreFocus;
    restoreFocus = "";
    requestAnimationFrame(() => {
      document.querySelector<HTMLElement>(`[data-focusid="${CSS.escape(id)}"]`)?.focus();
    });
  }
}

function onKey(event: KeyboardEvent): void {
  if (event.key === "Escape" && menu) {
    event.preventDefault();
    closeMenu(true);
  }
}

function onPointer(event: MouseEvent): void {
  if (!menu) return;
  const target = event.target;
  if (target instanceof Node && document.querySelector(".menu")?.contains(target)) return;
  closeMenu(true);
}

window.addEventListener("keydown", onKey);
window.addEventListener("mousedown", onPointer);

function onRender(event: Event): void {
  const data = (event as CustomEvent<RenderData>).detail;
  paint((data.args || {}) as Props);
  Streamlit.setFrameHeight(window.innerHeight);
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
