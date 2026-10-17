/*
 * The colour scheme of the full-screen pages: the one chosen in the docs (Material
 * keeps it in localStorage), else the system's. Loaded as a plain script in <head>,
 * it runs before the first paint, so that a dark page never flashes light.
 */
(() => {
  const system = matchMedia("(prefers-color-scheme: dark)");
  // The pages sit one folder below the root of the docs, whose path Material uses as the key.
  const key = `${new URL("..", location.href).pathname}.__palette`;
  const apply = () => {
    let scheme = null;
    try {
      scheme = JSON.parse(localStorage.getItem(key))?.color?.scheme ?? null;
    } catch {
      scheme = null;
    }
    const theme = (scheme ? scheme === "slate" : system.matches) ? "dark" : "light";
    if (document.documentElement.dataset.theme !== theme) {
      document.documentElement.dataset.theme = theme;
      dispatchEvent(new Event("themechange"));
    }
  };
  apply();
  system.addEventListener("change", apply);
  addEventListener("storage", apply);
})();
