import type { DatabaseProfile } from "./api/types";

// A unit is the first short parenthesised token in a column comment: "(Mt)", "(%)", "(t/person)".
// Anything with a space ("(Maddison Project)") is a remark, not a unit, so no unit is guessed.
const TOKEN = /\(([^()\s]{1,14})\)/g;

export function unitOf(comment: string | null): string | null {
  if (!comment) return null;
  for (const match of comment.matchAll(TOKEN)) {
    const token = match[1];
    if (token && /^[\p{L}\p{N}%°$/.\-]+$/u.test(token)) return token;
  }
  return null;
}

/** Column name to unit, from the database profile's column comments; ambiguous names are left out. */
export function unitsFromProfile(profile: DatabaseProfile | null): Record<string, string> {
  const units: Record<string, string> = {};
  const conflicting = new Set<string>();
  for (const table of profile?.tables ?? []) {
    for (const column of table.columns) {
      const unit = unitOf(column.comment);
      if (!unit) continue;
      if (units[column.name] && units[column.name] !== unit) conflicting.add(column.name);
      units[column.name] = unit;
    }
  }
  for (const name of conflicting) delete units[name];
  return units;
}
