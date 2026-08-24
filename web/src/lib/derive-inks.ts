// Two-plate school inks. Brand hexes in, A/B plates out.
//   A  = dark plate. Hero ground, display numbers, non-highlight fills.
//        Scouted darks are forced to >= 7:1 on production paper.
//   B  = bright plate. Highlight area only. Never small type on paper.
//   onB = ink or cream, whichever reads on B at >= 4.5:1.
// House path (no usable brand colour) returns production forest + ochre
// unchanged — those are the site inks, not a derived pair.

export const PAPER = "#f1ece1";
export const INK = "#1c1e1b";
export const CREAM_ON_B = "#fdf6ea";
export const CHARCOAL = "#333f48";
export const HOUSE_A = "#3f5b3a";
export const HOUSE_B = "#8a6a2b";

export const TARGET_A = 7;
export const TARGET_ON_B = 4.5;
export const MIN_B_ON_CREAM = 1.25;
export const MIN_B_ON_A = 3;
export const MIN_B_L = 0.58;
export const NEUTRAL_C = 0.035;
export const HUE_SEP = 22;

export type InkContrast = {
  aOnCream: number;
  textOnB: number;
  bOnCream: number;
  bOnA: number;
};

export type DerivedInks = {
  a: string;
  b: string;
  onB: string;
  rule: string;
  house: boolean;
  bTypeOnA: boolean;
  paper: string;
  contrast: InkContrast;
};

type Lch = { L: number; C: number; h: number };

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

function hexToRgb(h: string): [number, number, number] {
  let hex = h.trim().replace(/^#/, "");
  if (hex.length === 3) hex = hex.split("").map((c) => c + c).join("");
  const n = parseInt(hex, 16);
  return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255];
}

const rgbToHex = (rgb: number[]) =>
  "#" + rgb.map((c) => Math.round(clamp01(c) * 255).toString(16).padStart(2, "0")).join("");

const toLin = (c: number) =>
  c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
const toSrgb = (c: number) =>
  c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;

function rgbToOklab([r, g, b]: [number, number, number]): [number, number, number] {
  r = toLin(r);
  g = toLin(g);
  b = toLin(b);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
  ];
}

function oklabToRgb([L, a, b]: [number, number, number]): [number, number, number] {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3;
  return [
    toSrgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    toSrgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    toSrgb(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s),
  ];
}

const inGamut = (rgb: number[]) => rgb.every((c) => c >= -0.001 && c <= 1.001);

function hexToLch(hex: string): Lch {
  const [L, a, b] = rgbToOklab(hexToRgb(hex));
  return { L, C: Math.hypot(a, b), h: (Math.atan2(b, a) * 180 / Math.PI + 360) % 360 };
}

function lchToHex({ L, C, h }: Lch): string {
  const rad = h * Math.PI / 180;
  for (let c = C; c >= 0; c -= 0.004) {
    const rgb = oklabToRgb([clamp01(L), Math.cos(rad) * c, Math.sin(rad) * c]);
    if (inGamut(rgb)) return rgbToHex(rgb);
  }
  return rgbToHex(oklabToRgb([clamp01(L), 0, 0]));
}

const relLum = (hex: string) => {
  const [r, g, b] = hexToRgb(hex).map(toLin);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

export function contrast(x: string, y: string): number {
  const a = relLum(x);
  const b = relLum(y);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

function forceDark(hex: string): string {
  let lch = hexToLch(hex);
  let out = hex;
  for (let i = 0; i < 90 && contrast(out, PAPER) < TARGET_A; i++) {
    lch = { ...lch, L: Math.max(0, lch.L - 0.01) };
    out = lchToHex(lch);
  }
  return out;
}

function forceBright(hex: string, floor = MIN_B_L): string {
  const lch = hexToLch(hex);
  if (lch.C < NEUTRAL_C) return lchToHex({ L: Math.max(lch.L, floor), C: 0, h: 0 });
  if (lch.L >= floor) return hex;
  return lchToHex({ L: floor, C: Math.max(lch.C * 1.35, 0.16), h: lch.h });
}

const hueGap = (a: number, b: number) => {
  const d = Math.abs(a - b) % 360;
  return d > 180 ? 360 - d : d;
};

function separateFromPaper(hex: string): { hex: string; moved: boolean } {
  if (contrast(hex, PAPER) >= MIN_B_ON_CREAM) return { hex, moved: false };
  const lch = hexToLch(hex);
  let out = hex;
  let L = lch.L;
  for (let i = 0; i < 90 && contrast(out, PAPER) < MIN_B_ON_CREAM; i++) {
    L = Math.max(0, L - 0.01);
    out = lchToHex({ ...lch, L });
  }
  return { hex: out, moved: true };
}

const bestOn = (b: string) =>
  contrast(INK, b) >= contrast(CREAM_ON_B, b) ? INK : CREAM_ON_B;

function walk(hex: string, dir: number): { hex: string; on: string; steps: number } {
  const lch = hexToLch(hex);
  const on = dir > 0 ? INK : CREAM_ON_B;
  let out = hex;
  let L = lch.L;
  for (let i = 1; i <= 80; i++) {
    L = clamp01(L + dir * 0.01);
    out = lchToHex({ ...lch, L });
    if (contrast(on, out) >= TARGET_ON_B) return { hex: out, on, steps: i };
    if (L === 0 || L === 1) break;
  }
  return { hex: out, on, steps: Infinity };
}

function fitOnB(hex: string): { hex: string; onB: string; moved: boolean } {
  const on = bestOn(hex);
  if (contrast(on, hex) >= TARGET_ON_B) return { hex, onB: on, moved: false };
  const up = walk(hex, +1);
  const down = walk(hex, -1);
  const win = down.steps <= up.steps ? down : up;
  return { hex: win.hex, onB: bestOn(win.hex), moved: win.steps !== Infinity };
}

function round2(n: number): number {
  return +n.toFixed(2);
}

function pack(a: string, b: string, onB: string, rule: string, house: boolean): DerivedInks {
  const bOnA = contrast(b, a);
  const bTypeOnA = bOnA >= MIN_B_ON_A;
  if (!bTypeOnA) rule += " · type on A stays cream";
  return {
    a,
    b,
    onB,
    rule,
    house,
    bTypeOnA,
    paper: PAPER,
    contrast: {
      aOnCream: round2(contrast(a, PAPER)),
      textOnB: round2(contrast(onB, b)),
      bOnCream: round2(contrast(b, PAPER)),
      bOnA: round2(bOnA),
    },
  };
}

function houseResult(rule: string): DerivedInks {
  return pack(HOUSE_A, HOUSE_B, bestOn(HOUSE_B), rule, true);
}

function finish(a: string, b: string, rule: string, house = false): DerivedInks {
  if (house) return houseResult(rule);
  a = forceDark(a);
  const sep = separateFromPaper(b);
  if (sep.moved) rule += " · B pulled down to separate from the stock";
  const fit = fitOnB(sep.hex);
  if (fit.moved) rule += " · B nudged so its label clears 4.5:1";
  return pack(a, fit.hex, fit.onB, rule, false);
}

export function parseBrandHexes(brand: string | string[] | null | undefined): string[] {
  if (brand == null) return [];
  const parts = Array.isArray(brand) ? brand : String(brand).split(/[,\s]+/);
  return parts
    .map((h) => h.trim())
    .filter(Boolean)
    .map((h) => (h.startsWith("#") ? h : `#${h}`).toLowerCase());
}

export function deriveInks(brand: string | string[] | null | undefined): DerivedInks {
  const hexes = parseBrandHexes(brand);
  if (!hexes.length) {
    return finish(HOUSE_A, HOUSE_B, "no brand colours on file — house inks", true);
  }

  const cols = hexes.map((hex) => ({ hex, ...hexToLch(hex) }));
  const inks = cols.filter((c) => c.C >= NEUTRAL_C);
  const greys = cols.length - inks.length;
  const greyNote = greys ? " (neutral second colour rejected)" : "";

  if (inks.length === 0) {
    return finish(
      HOUSE_A,
      HOUSE_B,
      "brand colours are neutral — house inks, no hue invented",
      true,
    );
  }
  if (inks.length === 1) {
    const only = inks[0];
    if (only.L < 0.55) {
      return finish(
        forceDark(only.hex),
        forceBright(only.hex, 0.62),
        `single ink — A is the brand colour, B a brightened tint${greyNote}`,
      );
    }
    return finish(
      CHARCOAL,
      only.hex,
      `single bright ink — A falls back to charcoal${greyNote}`,
    );
  }

  const dark = inks.reduce((m, c) => (c.L < m.L ? c : m));
  const rest = inks.filter((c) => c !== dark);
  const bright = rest.reduce((m, c) =>
    c.L * (0.5 + c.C) > m.L * (0.5 + m.C) ? c : m,
  );

  const a = forceDark(dark.hex);
  const separated =
    hueGap(dark.h, bright.h) >= HUE_SEP || bright.L - dark.L >= 0.22;

  if (!separated) {
    return finish(
      a,
      forceBright(bright.hex, 0.66),
      "second ink too close to A — B pushed brighter to separate",
    );
  }
  if (bright.L < 0.5) {
    return finish(a, forceBright(bright.hex), "two darks — B brightened to carry as an area colour");
  }
  return finish(a, bright.hex, "ideal pair — both plates used as given");
}

export function inkStyle(inks: DerivedInks): Record<string, string> {
  return {
    "--ink-a": inks.a,
    "--ink-b": inks.b,
    "--onb": inks.onB,
  };
}

export const INK_LAB_PRESETS: Array<[string, string]> = [
  ["University of Michigan", "#00274C, #FFCB05"],
  ["Stanford", "#8C1515, #E98300"],
  ["Berkeley", "#003262, #FDB515"],
  ["Howard", "#003A63, #E51937"],
  ["UT Austin", "#BF5700"],
  ["MIT", "#750014, #8A8B8C"],
  ["Wellesley", "#0142A2, #C9D9EE"],
  ["Grinnell", "#B01F24, #F0B323"],
  ["Spelman", "#00457C, #7A9A01"],
  ["Reed", "#A70E13, #4F5858"],
  ["Bethel", "#10306B, #F0B323"],
  ["Oberlin", "#C00000, #FFC72C"],
  ["Morehouse", "#8A1C1C, #B79A5B"],
  ["Smith", "#F5C400, #002B45"],
  ["Rice", "#00205B, #7C7E7F"],
  ["Tulane", "#006747, #418FDE"],
  ["Colorado College", "#FFC72C, #1E1E1E"],
  ["Deep Springs", "#3B3B3B"],
  ["Pale primary · test", "#FFF9C4"],
  ["Amherst", "#4F2683, #B7A57A"],
  ["Hampton", "#00447C, #005EB8"],
];
