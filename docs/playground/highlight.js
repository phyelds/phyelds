/*
 * A small Python highlighter for the playground editor. It marks tokens with the
 * class names of Pygments, which highlights the code blocks of the docs, so the
 * theme colours them the same way, in light and dark mode.
 */
(() => {
  const KEYWORDS = new Set([
    "as", "assert", "async", "await", "break", "class", "continue", "def", "del", "elif",
    "else", "except", "finally", "for", "global", "if", "lambda", "nonlocal", "pass",
    "raise", "return", "try", "while", "with", "yield", "match", "case",
  ]);
  const NAMESPACE_KEYWORDS = new Set(["from", "import"]);
  const WORD_OPERATORS = new Set(["and", "in", "is", "not", "or"]);
  const CONSTANTS = new Set(["True", "False", "None"]);
  const BUILTINS = new Set([
    "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "int", "isinstance",
    "len", "list", "map", "max", "min", "print", "range", "round", "set", "sorted", "str",
    "sum", "tuple", "type", "zip",
  ]);

  // One alternative per kind of token; the first that matches at a position wins.
  const TOKEN = new RegExp(
    [
      String.raw`(?<comment>#[^\n]*)`,
      String.raw`(?<docstring>[rRbBfFuU]{0,2}("""|''')[\s\S]*?(?:\3|$))`,
      String.raw`(?<string>[rRbBfFuU]{0,2}(?:"(?:[^"\\\n]|\\.)*"?|'(?:[^'\\\n]|\\.)*'?))`,
      String.raw`(?<decorator>@[A-Za-z_][\w.]*)`,
      String.raw`(?<number>\b\d[\d_]*(?:\.\d*)?(?:[eE][+-]?\d+)?j?\b|\.\d+\b)`,
      String.raw`(?<name>[A-Za-z_]\w*)`,
      String.raw`(?<operator>[-+*/%=<>!&|^~]+)`,
    ].join("|"),
    "g",
  );

  function escape(text) {
    return text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  }

  function nameClass(name, previous) {
    if (previous === "def") return "nf";
    if (previous === "class") return "nc";
    if (KEYWORDS.has(name)) return "k";
    if (NAMESPACE_KEYWORDS.has(name)) return "kn";
    if (WORD_OPERATORS.has(name)) return "ow";
    if (CONSTANTS.has(name)) return "kc";
    if (BUILTINS.has(name)) return "nb";
    if (name === "self") return "bp";
    return null;
  }

  function tokenClass(groups, previousName) {
    if (groups.comment) return "c1";
    if (groups.docstring) return "sd";
    if (groups.string) return "s2";
    if (groups.decorator) return "nd";
    if (groups.number) return groups.number.includes(".") ? "mf" : "mi";
    if (groups.operator) return "o";
    return nameClass(groups.name, previousName);
  }

  /** Return `source` as HTML, with every recognised token in a <span class="...">. */
  function highlightPython(source) {
    let html = "";
    let last = 0;
    let previousName = null;
    for (const match of source.matchAll(TOKEN)) {
      html += escape(source.slice(last, match.index));
      const className = tokenClass(match.groups, previousName);
      const text = escape(match[0]);
      html += className ? `<span class="${className}">${text}</span>` : text;
      previousName = match.groups.name ?? null;
      last = match.index + match[0].length;
    }
    return html + escape(source.slice(last));
  }

  globalThis.highlightPython = highlightPython;
})();
