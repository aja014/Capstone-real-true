// Table search (Policy Holder Information, Proposal): a row matches when the typed text
// appears in what a field shows on screen, not in its raw JavaScript string.
// - empty fields add nothing (never "null" / "undefined");
// - ISO dates also match as MM/DD/YYYY; money also as 1234.56 and ₱1,234.56;
// - JSON fields (the View popups) match by their keys and text values, never "[object Object]".
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})/;

export function searchTexts(value, type) {
  if (value === null || value === undefined || value === "") return [];
  if (Array.isArray(value)) return value.flatMap((v) => searchTexts(v));
  if (typeof value === "object") {
    return Object.entries(value).flatMap(([k, v]) => [k, ...(typeof v === "boolean" ? [] : searchTexts(v))]);
  }
  if (typeof value === "boolean") return [value ? "Yes" : "No"];
  const text = String(value);
  const out = [text];
  const iso = text.match(ISO_DATE);
  if (iso) out.push(`${iso[2]}/${iso[3]}/${iso[1]}`);
  if (type === "currency" && text.trim() !== "" && !isNaN(Number(text))) {
    const n = Number(text);
    out.push(n.toFixed(2), `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
  }
  return out;
}

// Each row's searchable text is built once (rows are fetched objects that don't change in
// place) and kept here, so a keystroke is only a substring check per row. Fields are joined
// by a newline, which a typed search can't contain, so a match never spans two fields.
const rowTextCache = new WeakMap();

// typeByKey: { fieldName: "currency" } for the money columns.
export function rowMatchesSearch(row, search, typeByKey = {}) {
  const q = search.trim().toLowerCase();
  if (!q) return true;
  let text = rowTextCache.get(row);
  if (text === undefined) {
    text = Object.entries(row).flatMap(([key, value]) => searchTexts(value, typeByKey[key])).join("\n").toLowerCase();
    rowTextCache.set(row, text);
  }
  return text.includes(q);
}
