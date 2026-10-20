/*
 * The colour maps a layer of the playground can take: plasma, as in the walkthrough
 * and the GIFs of the docs; viridis; a diverging map, from blue to red;
 * categories, for ids; and directions, a wheel for headings, the same colour at both
 * ends. They extend the palette of the walkthrough, whose colours the stage draws by
 * their index.
 */
import { rgba, toneIndex } from "../walkthrough/palette.js";

export const MAPS = ["plasma", "viridis", "diverging", "categories"];
const LEVELS = 64; // tones of a map, as many as plasma has in the walkthrough
const VIRIDIS = [
  [68, 1, 84],
  [72, 40, 120],
  [62, 74, 137],
  [49, 104, 142],
  [38, 130, 142],
  [31, 158, 137],
  [53, 183, 121],
  [109, 205, 89],
  [180, 222, 44],
  [253, 231, 37],
];
// Blue to red through a grey, which shows on the light and the dark theme alike.
const DIVERGING = [
  [59, 76, 192],
  [150, 150, 150],
  [180, 4, 38],
];
// A wheel of hues: west, south, east, north and west again, so that a heading has one colour.
const DIRECTIONS = [
  [214, 76, 129],
  [235, 150, 60],
  [96, 178, 92],
  [62, 146, 204],
  [145, 104, 205],
  [214, 76, 129],
];
// Tableau 10: ten categories that tell apart on both themes.
const CATEGORIES = [
  [78, 121, 167],
  [242, 142, 43],
  [225, 87, 89],
  [118, 183, 178],
  [89, 161, 79],
  [237, 201, 72],
  [176, 122, 161],
  [255, 157, 167],
  [156, 117, 95],
  [186, 176, 172],
];

function interpolate(stops, t) {
  const position = Math.max(0, Math.min(1, t)) * (stops.length - 1);
  const index = Math.min(stops.length - 2, Math.floor(position));
  const fraction = position - index;
  return stops[index].map((low, channel) => Math.round(low + (stops[index + 1][channel] - low) * fraction));
}

/** `palette` with the colours of the other maps after its own, and the index where each map starts. */
export function extendPalette(palette) {
  // The darkest end of viridis vanishes on the dark theme, the lightest on the light one.
  const [low, high] = palette.dark ? [0.12, 1] : [0, 0.9];
  const levels = (stops, from = 0, to = 1) =>
    Array.from({ length: LEVELS }, (_, level) => interpolate(stops, from + ((to - from) * level) / (LEVELS - 1)));
  const rgb = [...palette.rgb];
  const starts = {};
  for (const [map, colours] of [
    ["viridis", levels(VIRIDIS, low, high)],
    ["diverging", levels(DIVERGING)],
    ["directions", levels(DIRECTIONS)],
    ["categories", CATEGORIES],
  ]) {
    starts[map] = rgb.length;
    rgb.push(...colours);
  }
  return { ...palette, rgb, css: rgb.map((colour) => rgba(colour)), starts };
}

/** The colour index of a tone in [0, 1] on a scale `map` of the extended `palette`. */
export function toneOf(palette, map, tone) {
  if (map === "plasma") return toneIndex(tone);
  return palette.starts[map] + Math.round(Math.max(0, Math.min(1, tone)) * (LEVELS - 1));
}

/** The colour index of a category: a whole number by its value, anything else by its text. */
export function categoryOf(palette, number, text) {
  let key = Math.round(number);
  if (!Number.isFinite(number)) {
    key = 0;
    for (const char of text) key = (key * 31 + char.codePointAt(0)) | 0;
  }
  return palette.starts.categories + (((key % CATEGORIES.length) + CATEGORIES.length) % CATEGORIES.length);
}

/** Nine colours along `map`, for its scale in the legend. */
export function stopsOf(palette, map) {
  if (map === "categories") return CATEGORIES.map((colour) => rgba(colour));
  return Array.from({ length: 9 }, (_, k) => palette.css[toneOf(palette, map, k / 8)]);
}
