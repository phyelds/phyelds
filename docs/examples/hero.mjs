/*
 * Records the animation of the home page: the playground runs the self-healing example in
 * 3D, the gradient grows from its source, then the source is dragged across the network and
 * the gradient repairs itself. It saves docs/assets/hero.gif and
 * docs/assets/hero-dark.gif, for the light and the dark theme of the docs:
 *
 *     npm install && node docs/examples/hero.mjs
 *
 * It serves the docs with `poetry run mkdocs serve`, so the docs dependencies must be
 * installed, and it needs the network, for Pyodide. It drives Chrome with puppeteer-core
 * (set CHROME to its path if it is not found) and needs ffmpeg and gifsicle. The rounds are
 * taken one per frame, so the animation does not depend on the speed of the machine.
 */
import { execFileSync, spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const ASSETS = path.join(ROOT, "docs", "assets");
const PORT = 8123;
const SITE = `http://127.0.0.1:${PORT}/phyelds/`;
const CHROMES = [
  process.env.CHROME,
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
];
const GROW = 12; // rounds the gradient grows from its source
const DRAG = 10; // rounds the source takes to cross the network
const HEAL = 14; // rounds the gradient takes to repair itself
const FPS = 5; // rounds per second of animation
const HOLD = 1.5; // seconds the last round stays
const WIDTH = 560; // pixels of the animation
const SOURCE = { x: 4, y: 4 }; // near where the playground switches the first sensor on
const TARGET = { x: 0.8, y: 0.9 }; // where the source is dragged to, across the network
// Everything but the network, which the animation shows alone, on the background of the docs, where it
// then sits with no frame. The map stays, unseen: the source is dragged on it.
const CLEAN =
  ".pg-side, .wt-player, .wt-hint, .pg-layers { display: none !important; } .wt-map { opacity: 0; }" +
  " .wt-stage { background: var(--wt-bg) !important; }";

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Serves the docs, and resolves once they answer. */
async function serve() {
  const server = spawn("poetry", ["run", "mkdocs", "serve", "--no-livereload", "-a", `127.0.0.1:${PORT}`], {
    cwd: ROOT,
    stdio: "ignore",
    detached: true,
  });
  for (let attempt = 0; attempt < 120; attempt += 1) {
    try {
      if ((await fetch(SITE)).ok) return server;
    } catch {
      // Not up yet.
    }
    await pause(500);
  }
  process.kill(-server.pid);
  throw new Error("mkdocs serve did not start");
}

/** Where the point of the arena (x, y) is on the map, in pixels of the page. */
function onMap(page, { x, y }) {
  return page.evaluate(
    (x, y) => {
      const box = document.querySelector("#wt-map").getBoundingClientRect();
      const side = Math.min(box.width, box.height) - 28;
      const left = box.left + (box.width - side) / 2;
      const top = box.top + (box.height - side) / 2;
      return [left + (x / 5) * side, top + (1 - y / 5) * side];
    },
    x,
    y,
  );
}

/** The device with its source on, found by hovering the map around SOURCE: where it is on the map. */
async function findSource(page) {
  const [cx, cy] = await onMap(page, SOURCE);
  for (let r = 0; r <= 24; r += 2) {
    for (let dx = -r; dx <= r; dx += 2) {
      for (const dy of [-r, r]) {
        await page.mouse.move(cx + dx, cy + dy);
        if (await page.$('#pg-sensors button[aria-pressed="true"]')) return [cx + dx, cy + dy];
      }
    }
  }
  throw new Error("no source near where the playground puts it");
}

/** Runs one round and waits for the network to show it. */
async function step(page) {
  const round = () => Number(document.querySelector("#wt-round").textContent.match(/round (\d+)/)[1]);
  const before = await page.evaluate(round);
  await page.keyboard.press(".");
  await page.waitForFunction((before) => Number(document.querySelector("#wt-round").textContent.match(/round (\d+)/)[1]) > before, {}, before);
  // Two frames: the stage draws on the next one.
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

/** Records the animation in `theme`, light or dark, as frames in `folder`. */
async function record(browser, theme, folder) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1240, height: 760 });
  // No rings around the devices that just ran, no easing: a frame changes only with the values.
  await page.emulateMediaFeatures([
    { name: "prefers-color-scheme", value: theme },
    { name: "prefers-reduced-motion", value: "reduce" },
  ]);
  await page.goto(`${SITE}playground/#example=gradient`, { waitUntil: "load" });
  await page.waitForFunction(() => /round <strong>[1-9]/.test(document.querySelector("#wt-round").innerHTML), { timeout: 180000 });
  await page.addStyleTag({ content: CLEAN });
  await page.evaluate(() => document.activeElement.blur());
  await page.keyboard.press("r");
  await page.waitForFunction(() => /round <strong>0</.test(document.querySelector("#wt-round").innerHTML));
  // Paused from here: every frame is one round. The button is hidden, not gone.
  await page.evaluate(() => document.querySelector("#wt-play").click());

  const stage = await page.$eval("#wt-stage", (element) => {
    const box = element.getBoundingClientRect();
    return { x: box.x, y: box.y, width: box.width, height: box.height };
  });
  // 4:3 across the stage, around the network and the name of its layer, as the animation it replaces.
  const clip = { x: stage.x, y: stage.y + (stage.height - stage.width * 0.75) / 2, width: stage.width, height: stage.width * 0.75 };
  const away = [20, stage.y + stage.height / 2]; // over the editor: no device is hovered
  let frames = 0;
  const shoot = async () => {
    await page.screenshot({ path: path.join(folder, `${String(frames).padStart(4, "0")}.png`), clip });
    frames += 1;
  };

  // The source, selected: its ring, not the one of the device in the middle, follows the drag.
  const from = await findSource(page);
  await page.mouse.down();
  await page.mouse.up();
  await page.mouse.move(...away);

  await shoot();
  for (let round = 0; round < GROW; round += 1) {
    await step(page);
    await shoot();
  }
  const to = await onMap(page, TARGET);
  await page.mouse.move(...from);
  await page.mouse.down();
  for (let round = 1; round <= DRAG; round += 1) {
    await page.mouse.move(from[0] + ((to[0] - from[0]) * round) / DRAG, from[1] + ((to[1] - from[1]) * round) / DRAG, { steps: 4 });
    await step(page);
    await shoot();
  }
  await page.mouse.up();
  await page.mouse.move(...away);
  for (let round = 0; round < HEAL; round += 1) {
    await step(page);
    await shoot();
  }
  await page.close();
  return frames;
}

/** The frames of `folder` as an optimised GIF at `output`, the last one held. */
function assemble(folder, output) {
  const filter =
    `scale=${WIDTH}:-1:flags=lanczos,tpad=stop_mode=clone:stop_duration=${HOLD},` +
    // Flat colours, without dithering: the background and the planes then compress well.
    "split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle";
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-framerate", String(FPS), "-i", path.join(folder, "%04d.png"), "-vf", filter, "-loop", "0", output]);
  execFileSync("gifsicle", ["-O3", "--batch", output]);
}

async function main() {
  const executablePath = CHROMES.find((candidate) => candidate && existsSync(candidate));
  if (!executablePath) throw new Error("Chrome not found: set CHROME to its path");
  const server = await serve();
  const browser = await puppeteer.launch({ executablePath, headless: true });
  try {
    for (const [theme, name] of [
      ["light", "hero.gif"],
      ["dark", "hero-dark.gif"],
    ]) {
      const folder = mkdtempSync(path.join(tmpdir(), "phyelds-hero-"));
      const frames = await record(browser, theme, folder);
      assemble(folder, path.join(ASSETS, name));
      rmSync(folder, { recursive: true, force: true });
      console.log(`${name}: ${frames} rounds`);
    }
  } finally {
    await browser.close();
    process.kill(-server.pid);
  }
}

await main();
