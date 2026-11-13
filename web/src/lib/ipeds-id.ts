/** A valid IPEDS unit id is six digits. Returns the id, or null. */
export function normalizeIpedsId(raw: string | null | undefined): string | null {
  const trimmed = (raw ?? "").trim();
  return /^\d{6}$/.test(trimmed) ? trimmed : null;
}
