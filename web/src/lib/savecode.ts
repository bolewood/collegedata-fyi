import type { StudentProfile } from "./positioning";

const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const LOOKUP = new Map(Array.from(ALPHABET).map((char, index) => [char, index]));
const GPA_SENTINEL = 511;
const SAT_SENTINEL = 127;
const ACT_SENTINEL = 0;
const VERSION = 1;

const GPA_SCALE_CODES: Record<NonNullable<StudentProfile["gpaScale"]>, number> = {
  unknown: 0,
  unweighted_4: 1,
  weighted: 2,
};

const GPA_SCALE_BY_CODE = new Map<number, NonNullable<StudentProfile["gpaScale"]>>(
  Object.entries(GPA_SCALE_CODES).map(([scale, code]) => [
    code,
    scale as NonNullable<StudentProfile["gpaScale"]>,
  ]),
);

function clampInt(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Math.round(value)));
}

function cleanNumber(value: number | undefined, min: number, max: number): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  if (value < min || value > max) return null;
  return value;
}

function encodeBase32(value: number): string {
  let out = "";
  for (let i = 0; i < 6; i += 1) {
    out = ALPHABET[value & 31] + out;
    value = Math.floor(value / 32);
  }
  return `${out.slice(0, 3)}-${out.slice(3)}`;
}

function decodeBase32(code: string): number | null {
  const normalized = code.toUpperCase().replace(/[^0-9A-Z]/g, "");
  if (normalized.length !== 6) return null;

  let value = 0;
  for (const char of normalized) {
    const digit = LOOKUP.get(char);
    if (digit == null) return null;
    value = value * 32 + digit;
  }
  return value;
}

export function encodeProfileCode(profile: StudentProfile): string {
  const gpa = cleanNumber(profile.gpa, 0, 5);
  const sat = cleanNumber(profile.sat, 400, 1600);
  const act = cleanNumber(profile.act, 1, 36);
  const gpaCode = gpa == null ? GPA_SENTINEL : clampInt(gpa * 100, 0, 500);
  const satCode = sat == null ? SAT_SENTINEL : clampInt((sat - 400) / 10, 0, 120);
  const actCode = act == null ? ACT_SENTINEL : clampInt(act, 1, 36);
  const scaleCode = GPA_SCALE_CODES[profile.gpaScale ?? "unknown"] ?? 0;

  const packed =
    (VERSION << 24) |
    (scaleCode << 22) |
    (actCode << 16) |
    (satCode << 9) |
    gpaCode;

  return encodeBase32(packed);
}

export function decodeProfileCode(code: string): StudentProfile | null {
  const packed = decodeBase32(code);
  if (packed == null) return null;

  const version = (packed >> 24) & 3;
  if (version !== VERSION) return null;

  const scaleCode = (packed >> 22) & 3;
  const actCode = (packed >> 16) & 63;
  const satCode = (packed >> 9) & 127;
  const gpaCode = packed & 511;
  const profile: StudentProfile = {
    gpaScale: GPA_SCALE_BY_CODE.get(scaleCode) ?? "unknown",
  };

  if (gpaCode !== GPA_SENTINEL) {
    profile.gpa = Number((gpaCode / 100).toFixed(2));
  }
  if (satCode !== SAT_SENTINEL) {
    profile.sat = 400 + satCode * 10;
  }
  if (actCode !== ACT_SENTINEL) {
    profile.act = actCode;
  }

  return profile;
}
