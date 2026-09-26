import type { Cell } from "./api/types";

const TEMPORAL = /(^|_)(year|yr|date|day|month|quarter|week|time|period)s?($|_)/i;

const number = new Intl.NumberFormat("en", { maximumFractionDigits: 3 });
const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });

export function isTemporal(column: string): boolean {
  return TEMPORAL.test(column);
}

/** Display a result cell: years stay plain, other numbers get separators, NULL is shown as such. */
export function formatCell(column: string, value: Cell): string {
  if (value === null) return "NULL";
  if (typeof value === "number") {
    if (isTemporal(column) && Number.isInteger(value)) return String(value);
    return number.format(value);
  }
  return String(value);
}

/** Axis ticks: short numbers (12k, 1.4B) so labels never collide. */
export function formatTick(column: string, value: unknown): string {
  if (typeof value !== "number") return String(value);
  if (isTemporal(column) && Number.isInteger(value)) return String(value);
  return Math.abs(value) >= 1000 ? compact.format(value) : number.format(value);
}
