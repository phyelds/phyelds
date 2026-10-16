/*
 * The colours of the walkthrough: the tokens of the current theme, read from
 * the CSS custom properties, and plasma, the colour map of the gifs of the docs.
 */
import { OFF, ON } from "./views.js";

const LEVELS = 64; // tones of the colour map; ON and OFF come after them
const PLASMA = [
  [13, 8, 135],
  [84, 2, 163],
  [139, 10, 165],
  [185, 50, 137],
  [219, 92, 104],
  [244, 136, 73],
  [254, 188, 43],
  [240, 249, 33],
];

function plasma(t) {
  const position = Math.max(0, Math.min(1, t)) * (PLASMA.length - 1);
  const index = Math.min(PLASMA.length - 2, Math.floor(position));
  const fraction = position - index;
  return PLASMA[index].map((low, channel) => Math.round(low + (PLASMA[index + 1][channel] - low) * fraction));
}

function hexToRgb(hex) {
  const value = Number.parseInt(hex.replace("#", ""), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

export const rgba = ([red, green, blue], alpha = 1) => `rgba(${red}, ${green}, ${blue}, ${alpha})`;

/**
 * The palette of the theme now in use. A tone index below LEVELS is a step of
 * the colour map; LEVELS and LEVELS + 1 are the colours of True and False.
 */
export function readPalette() {
  const style = getComputedStyle(document.documentElement);
  const token = (name) => hexToRgb(style.getPropertyValue(name).trim());
  const dark = document.documentElement.dataset.theme === "dark";
  // The ends of plasma vanish on the background: dark purple on dark, yellow on light.
  const [low, high] = dark ? [0.14, 1] : [0, 0.86];
  const map = Array.from({ length: LEVELS }, (_, level) => plasma(low + ((high - low) * level) / (LEVELS - 1)));
  const rgb = [...map, token("--wt-true"), token("--wt-false")];
  return {
    dark,
    ink: token("--wt-ink"),
    muted: token("--wt-muted"),
    stage: token("--wt-stage"),
    on: LEVELS,
    off: LEVELS + 1,
    rgb,
    css: rgb.map((color) => rgba(color)),
    mono: style.getPropertyValue("--wt-font-mono").trim(),
  };
}

/** The colour index of a tone: a value of the colour map in [0, 1], ON, OFF, or null. */
export function toneIndex(tone, reversed = false) {
  if (tone === null || Number.isNaN(tone)) return null;
  if (tone === ON) return LEVELS;
  if (tone === OFF) return LEVELS + 1;
  const t = Math.max(0, Math.min(1, reversed ? 1 - tone : tone));
  return Math.round(t * (LEVELS - 1));
}
