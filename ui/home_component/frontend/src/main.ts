import { Streamlit, RenderData } from "streamlit-component-lib";
import "./style.css";

type Row = {
  token: string;
  title: string;
  subtitle: string;
  age: string;
  action: "practice" | "analyse" | string;
  state?: "ready" | "analysing" | "waiting" | "failed" | "idle" | string;
};

function isLocked(row: Row): boolean {
  return row.state === "analysing" || row.state === "waiting";
}

function progressBar(row: Row): HTMLElement {
  const bar = el("span", row.state === "analysing" ? "bar is-active" : "bar is-queued");
  bar.setAttribute("role", "progressbar");
  bar.setAttribute(
    "aria-label",
    row.state === "analysing" ? "Getting key and chords" : "Waiting for key and chords",
  );
  bar.setAttribute("aria-busy", "true");
  bar.append(el("span", "fill"));
  return bar;
}

type Card = {
  id: string;
  title: string;
  subtitle: string;
  primary?: boolean;
};

type Flash = { message?: string; error?: boolean } | null;

type Setlist = {
  id: string;
  name: string;
  tokens?: string[];
};

type Props = {
  nonce?: string;
  product?: string;
  cards?: Card[];
  recents?: Row[];
  rows?: Row[];
  setlists?: Setlist[];
  trashed?: Row[];
  loading?: boolean;
  flash?: Flash;
  activeSetlist?: string;
  locale?: string;
  strings?: Record<string, string>;
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
let libraryFilter = "all";
let activeSetlistId = "";
let activeSetlistReady = false;
let menu: MenuState | null = null;
let restoreFocus = "";
let picked = new Set<string>();
const FILES_SCROLL_KEY = "att-home-files-scroll";
const MAIN_SCROLL_KEY = "att-home-main-scroll";
const SELECT_KEY = "att-home-select-mode";

function stored(key: string): string {
  try {
    return sessionStorage.getItem(key) || "";
  } catch {
    return "";
  }
}

function store(key: string, value: string): void {
  try {
    sessionStorage.setItem(key, value);
  } catch {
    /* private mode */
  }
}

let selectMode = stored(SELECT_KEY) === "1";

function mainScroller(): HTMLElement | null {
  try {
    const doc = window.parent.document;
    return (
      doc.querySelector<HTMLElement>('[data-testid="stMain"]') ||
      doc.querySelector<HTMLElement>("section.main")
    );
  } catch {
    return null;
  }
}

function rememberScroll(): void {
  const files = document.querySelector<HTMLElement>(".files-scroll");
  if (files) store(FILES_SCROLL_KEY, String(files.scrollTop));
  const main = mainScroller();
  if (main) store(MAIN_SCROLL_KEY, String(main.scrollTop));
}

function restoreScroll(): void {
  const filesTop = Number(stored(FILES_SCROLL_KEY) || "0");
  const mainTop = Number(stored(MAIN_SCROLL_KEY) || "0");
  const apply = (): void => {
    const files = document.querySelector<HTMLElement>(".files-scroll");
    if (files && Number.isFinite(filesTop) && filesTop > 0) files.scrollTop = filesTop;
    const main = mainScroller();
    if (main && Number.isFinite(mainTop) && mainTop > 0) main.scrollTop = mainTop;
  };
  requestAnimationFrame(apply);
  window.setTimeout(apply, 50);
}

function canSelect(row: Row): boolean {
  return row.state !== "analysing";
}

function label(props: Props, key: string, fallback: string): string {
  return props.strings?.[key] || fallback;
}

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
  if (type === "delete_song" || type === "delete_songs") rememberScroll();
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
  rememberScroll();
  lastProps = props;
  const nonce = props.nonce || "";
  const setlists = props.setlists || [];
  if (!activeSetlistReady) {
    activeSetlistReady = true;
    activeSetlistId = props.activeSetlist || "";
  }
  if (activeSetlistId && !setlists.some((item) => item.id === activeSetlistId)) {
    activeSetlistId = "";
  }
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
      if (isLocked(row)) {
        button.disabled = true;
        button.classList.add("is-locked");
        meta.textContent = row.subtitle || "Getting key and chords…";
        button.append(progressBar(row));
      }
      button.addEventListener("click", () => {
        if (!isLocked(row)) send(nonce, "open_recent", row.token);
      });
      scroller.append(button);
    });
  });

  const head = el("div", "files-head");
  const top = el("div", "files-row");
  const filesHeading = el("h2");
  filesHeading.textContent = "Files";
  const toolbar = el("div", "toolbar");
  const all = el("button", "pill");
  all.type = "button";
  all.dataset.pill = "all";
  all.dataset.focusid = "pill-all";
  all.textContent = "All";
  all.setAttribute("aria-pressed", activeSetlistId ? "false" : "true");
  all.addEventListener("click", () => {
    activeSetlistId = "";
    paint(lastProps);
    send(nonce, "select_setlist", "");
  });
  const pills = [all];
  setlists.forEach((item) => {
    const pill = el("button", "pill");
    pill.type = "button";
    pill.dataset.pill = item.id;
    pill.dataset.focusid = `pill-${item.id}`;
    pill.textContent = item.name;
    pill.setAttribute("aria-pressed", item.id === activeSetlistId ? "true" : "false");
    pill.addEventListener("click", () => {
      activeSetlistId = item.id;
      paint(lastProps);
      send(nonce, "select_setlist", item.id);
    });
    pills.push(pill);
  });
  const create = el("button", "pill");
  create.type = "button";
  create.dataset.pill = "new";
  create.dataset.focusid = "pill-new";
  create.textContent = "New setlist";
  create.setAttribute("aria-pressed", "false");
  create.addEventListener("click", () => {
    const name = window.prompt("Setlist name");
    if (name === null) return;
    send(nonce, "new_setlist", name);
  });
  const selected = setlists.find((item) => item.id === activeSetlistId);
  const rename = el("button", "pill");
  const removeList = el("button", "pill");
  if (selected) {
    rename.type = "button";
    rename.dataset.focusid = "setlist-rename";
    rename.textContent = "Rename";
    rename.addEventListener("click", () => {
      const name = window.prompt("Setlist name", selected.name);
      if (name === null) return;
      send(nonce, "rename_setlist", `${selected.id}|${name}`);
    });
    removeList.type = "button";
    removeList.dataset.focusid = "setlist-delete";
    removeList.textContent = "Delete setlist";
    removeList.addEventListener("click", () => {
      if (!window.confirm("Delete this setlist? Songs stay in the library.")) return;
      activeSetlistId = "";
      send(nonce, "delete_setlist", selected.id);
    });
  }
  const search = el("label", "search");
  search.appendChild(document.createRange().createContextualFragment(svg("search", 16)));
  const input = el("input");
  input.id = "home-search";
  input.type = "search";
  input.placeholder = label(props, "search", "Search");
  input.value = query;
  input.dataset.focusid = "search";
  input.setAttribute("aria-label", label(props, "search", "Search"));
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
  toolbar.append(...pills, create);
  if (selected) toolbar.append(rename, removeList);
  const filters = el("div", "filters");
  filters.setAttribute("role", "group");
  filters.setAttribute("aria-label", "Library filters");
  for (const item of [
    ["all", "all", "All"],
    ["practice", "practice", "Ready to practice"],
    ["analyse", "analyse", "Not analysed"],
    ["deleted", "deleted", "Deleted"],
  ] as const) {
    const chip = el("button", "pill");
    chip.type = "button";
    chip.dataset.focusid = `filter-${item[0]}`;
    chip.textContent = label(props, item[1], item[2]);
    chip.setAttribute("aria-pressed", libraryFilter === item[0] ? "true" : "false");
    chip.addEventListener("click", () => {
      libraryFilter = item[0];
      paint(lastProps);
    });
    filters.append(chip);
  }
  const selectToggle = el("button", "pill");
  selectToggle.type = "button";
  selectToggle.dataset.focusid = "select-mode";
  selectToggle.textContent = "Select";
  selectToggle.setAttribute("aria-pressed", selectMode ? "true" : "false");
  selectToggle.setAttribute("aria-label", "Select mixes");
  selectToggle.addEventListener("click", () => {
    selectMode = !selectMode;
    if (!selectMode) picked.clear();
    store(SELECT_KEY, selectMode ? "1" : "0");
    paint(lastProps);
  });
  filters.append(selectToggle);
  const tools = el("div", "files-tools");
  tools.append(search, sort);
  top.append(filesHeading, toolbar, tools);
  head.append(top, filters);
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
    const source = libraryFilter === "deleted" ? props.trashed || [] : props.rows || [];
    const needle = query.trim().toLowerCase();
    const active = setlists.find((item) => item.id === activeSetlistId);
    const allowed = active && libraryFilter !== "deleted" ? new Set(active.tokens || []) : null;
    let shown = source.filter((row) => {
      if (allowed && !allowed.has(row.token)) return false;
      if (libraryFilter === "practice" || libraryFilter === "analyse") {
        if (row.action !== libraryFilter) return false;
      }
      if (!needle) return true;
      return `${row.title} ${row.subtitle}`.toLowerCase().includes(needle);
    });
    shown = sortOldest ? [...shown].reverse() : shown;
    if (shown.length === 0 && active) {
      const empty = el("p", "empty");
      empty.textContent = needle ? "No songs match that search." : "No songs in this setlist.";
      files.append(empty);
    } else if (source.length === 0) {
      const empty = el("p", "empty");
      empty.textContent = "No songs yet.";
      files.append(empty);
    } else if (shown.length === 0) {
      const empty = el("p", "empty");
      empty.textContent = "No songs match that search.";
      files.append(empty);
    } else {
      const picking = selectMode && libraryFilter !== "deleted";
      const pickable = picking ? shown.filter((row) => canSelect(row)) : [];
      const chosen = pickable.filter((row) => picked.has(row.token));
      if (chosen.length > 0) {
        const bar = el("div", "select-bar");
        bar.setAttribute("role", "region");
        bar.setAttribute("aria-label", "Selected mixes");
        const count = el("span");
        count.textContent = chosen.length === 1 ? "1 selected" : `${chosen.length} selected`;
        const remove = el("button", "pill");
        remove.type = "button";
        remove.dataset.focusid = "delete-selected";
        remove.textContent = "Delete selected";
        remove.addEventListener("click", () => {
          const ids = chosen.map((row) => row.token);
          const noun = ids.length === 1 ? "mix" : "mixes";
          if (
            !window.confirm(
              `Delete ${ids.length} ${noun}? You can recover them from Deleted.`,
            )
          ) {
            return;
          }
          ids.forEach((token) => picked.delete(token));
          send(nonce, "delete_songs", ids.join(","));
        });
        bar.append(count, remove);
        files.append(bar);
      }
      const table = el("table");
      const thead = el("thead");
      const header = el("tr");
      if (picking) {
        const checkHead = el("th", "col-check");
        const allBox = el("input");
        allBox.type = "checkbox";
        allBox.dataset.focusid = "select-all";
        allBox.setAttribute("aria-label", "Select all");
        allBox.checked = pickable.length > 0 && chosen.length === pickable.length;
        allBox.indeterminate = chosen.length > 0 && chosen.length < pickable.length;
        allBox.disabled = pickable.length === 0;
        allBox.addEventListener("change", () => {
          pickable.forEach((row) => {
            if (allBox.checked) picked.add(row.token);
            else picked.delete(row.token);
          });
          paint(lastProps);
        });
        checkHead.append(allBox);
        header.append(checkHead);
      }
      const titleHead = el("th");
      titleHead.textContent = label(props, "title", "Title");
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
        if (picking) {
          const checkCell = el("td", "col-check");
          if (canSelect(row)) {
            const box = el("input");
            box.type = "checkbox";
            box.dataset.focusid = `check-${row.token}`;
            box.setAttribute("aria-label", `Select ${row.title}`);
            box.checked = picked.has(row.token);
            box.addEventListener("change", () => {
              if (box.checked) picked.add(row.token);
              else picked.delete(row.token);
              paint(lastProps);
            });
            checkCell.append(box);
          }
          tr.append(checkCell);
        }
        const titleCell = el("td");
        const opener = el("button", "row-open");
        opener.type = "button";
        opener.dataset.focusid = `row-${row.token}`;
        const name = el("span", "name");
        name.textContent = row.title;
        const sub = el("span", "sub");
        sub.textContent = row.subtitle || "";
        opener.append(name, sub);
        if (isLocked(row)) {
          opener.disabled = true;
          opener.classList.add("is-locked");
          opener.setAttribute("aria-disabled", "true");
          opener.append(progressBar(row));
        }
        opener.addEventListener("click", () => {
          if (!isLocked(row)) send(nonce, "open_row", row.token);
        });
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
  restoreScroll();

  if (menu) {
    const popup = el("div", "menu");
    popup.setAttribute("role", "menu");
    popup.style.left = `${menu.x}px`;
    popup.style.top = `${menu.y}px`;
    const menuRow = (props.rows || []).find((row) => row.token === menu?.token);
    const lockedMenu = menu.kind === "row" && menuRow !== undefined && isLocked(menuRow);
    const allItems: { label: string; type: string; id: string }[] =
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
            ...(setlists.length
              ? setlists.map((item) => ({
                  label: setlists.length === 1 ? "Add to setlist" : `Add to ${item.name}`,
                  type: "add_to_setlist",
                  id: `${item.id}|${menu?.token || ""}`,
                }))
              : [{ label: "Add to setlist", type: "add_to_setlist", id: `|${menu.token}` }]),
            ...(activeSetlistId
              ? [
                  {
                    label: "Remove from setlist",
                    type: "remove_from_setlist",
                    id: `${activeSetlistId}|${menu.token}`,
                  },
                ]
              : []),
            ...(libraryFilter === "deleted"
              ? [
                  {
                    label: label(props, "recover", "Recover"),
                    type: "recover_song",
                    id: menu.token,
                  },
                ]
              : [
                  {
                    label: label(props, "delete", "Delete song"),
                    type: "delete_song",
                    id: menu.token,
                  },
                ]),
          ];
    const items = allItems.filter((item) => {
      if (item.type === "open_row" || item.type === "analyse" || item.type === "practice") {
        return !lockedMenu;
      }
      if (item.type === "delete_song") return menuRow?.state !== "analysing";
      return true;
    });
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
        if (type === "delete_song" && !window.confirm("Delete this song from the library? You can recover it from Deleted.")) {
          return;
        }
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
