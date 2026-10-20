/*
 * The menu of the examples: a button that opens a panel with a search field and the
 * examples, group by group. The search matches the words of a title, a summary, a group
 * or a name an example imports, so that "gossip" or "sink_at" finds the examples using them.
 * ↑ and ↓ move through what the search leaves, Enter opens it, Escape closes the panel.
 */

/** Whether `example` matches every word of `query`. */
export function matches(example, query) {
  const text = [example.title, example.summary, example.group, ...example.uses].join(" ").toLowerCase();
  return query.toLowerCase().split(/\s+/).every((word) => text.includes(word));
}

/**
 * Binds the menu to its elements: `button` opens it, `title` names the open example,
 * `panel` holds `search` and `list`. `onPick(name)` opens an example.
 */
export function createMenu({ button, title, panel, search, list }, { onPick }) {
  let examples = [];
  let shown = []; // the options the search leaves, in order
  let active = 0;

  const isOpen = () => !panel.hidden;

  function setActive(index) {
    shown[active]?.classList.remove("is-active");
    active = Math.max(0, Math.min(shown.length - 1, index));
    shown[active]?.classList.add("is-active");
    shown[active]?.scrollIntoView({ block: "nearest" });
    if (shown[active]) search.setAttribute("aria-activedescendant", shown[active].id);
    else search.removeAttribute("aria-activedescendant");
  }

  function option(example, query) {
    const item = document.createElement("button");
    item.type = "button";
    item.id = `pg-option-${example.name}`;
    item.className = "pg-option";
    item.setAttribute("role", "option");
    item.dataset.name = example.name;
    const name = document.createElement("span");
    name.className = "pg-option-title";
    name.textContent = example.title;
    const summary = document.createElement("span");
    summary.className = "pg-option-summary";
    summary.textContent = example.summary.replace(/^./, (first) => first.toUpperCase());
    item.append(name, summary);
    // The names that matched, when the reader searched for an API.
    const used = query ? example.uses.filter((each) => query.toLowerCase().split(/\s+/).some((word) => each.toLowerCase().includes(word))) : [];
    if (used.length > 0) {
      const uses = document.createElement("span");
      uses.className = "pg-option-uses";
      uses.textContent = used.join(" · ");
      item.append(uses);
    }
    item.addEventListener("click", () => pick(example.name));
    return item;
  }

  function render() {
    const query = search.value.trim();
    const found = examples.filter((example) => !query || matches(example, query));
    const groups = [...new Set(found.map((example) => example.group))];
    list.replaceChildren(
      ...groups.map((group) => {
        const section = document.createElement("div");
        section.className = "pg-menu-group";
        section.setAttribute("role", "group");
        section.setAttribute("aria-label", group);
        const heading = document.createElement("p");
        heading.className = "pg-menu-heading";
        heading.textContent = group;
        section.append(heading, ...found.filter((example) => example.group === group).map((example) => option(example, query)));
        return section;
      }),
    );
    if (found.length === 0) {
      const empty = document.createElement("p");
      empty.className = "pg-menu-empty";
      empty.textContent = "No example matches.";
      list.append(empty);
    }
    shown = [...list.querySelectorAll(".pg-option")];
    active = 0;
    setActive(0);
  }

  function open() {
    panel.hidden = false;
    button.setAttribute("aria-expanded", "true");
    search.value = "";
    render();
    search.focus();
  }

  function close() {
    panel.hidden = true;
    button.setAttribute("aria-expanded", "false");
  }

  function pick(name) {
    close();
    button.focus();
    onPick(name);
  }

  button.addEventListener("click", () => (isOpen() ? close() : open()));
  search.addEventListener("input", render);
  search.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setActive(active + (event.key === "ArrowDown" ? 1 : -1));
    } else if (event.key === "Enter" && shown[active]) {
      event.preventDefault();
      pick(shown[active].dataset.name);
    }
  });
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      close();
      button.focus();
    }
  });
  document.addEventListener("pointerdown", (event) => {
    if (isOpen() && !panel.contains(event.target) && !button.contains(event.target)) close();
  });

  return {
    setExamples(all) {
      examples = all;
    },
    /** Names the example open in the editor, or `text` for a program that is none of them. */
    show(text) {
      title.textContent = text;
    },
  };
}
