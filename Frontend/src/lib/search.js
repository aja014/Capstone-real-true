// Table search (Policy Holder Information, Proposal): the typed text is split into words and
// a row matches when EVERY word appears in what some field shows on screen (not in its raw
// JavaScript string). The words may sit in different fields — "Antonio Gonzales Umali" finds
// a client whose names are in the Last/First/Middle Name columns — and in any order. One
// word behaves exactly as a plain substring search.
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

// "  Gonzales   Umali " → ["gonzales", "umali"]; blank → [].
export function searchWords(search) {
  return String(search ?? "").trim().toLowerCase().split(/\s+/).filter(Boolean);
}

// Each row's searchable text is built once (rows are fetched objects that don't change in
// place) and kept here, so a keystroke is only a substring check per row. Fields are joined
// by a newline, which a typed word can't contain, so one word never spans two fields.
const rowTextCache = new WeakMap();

// typeByKey: { fieldName: "currency" } for the money columns.
export function rowMatchesSearch(row, search, typeByKey = {}) {
  const words = searchWords(search);
  if (words.length === 0) return true;
  let text = rowTextCache.get(row);
  if (text === undefined) {
    text = Object.entries(row).flatMap(([key, value]) => searchTexts(value, typeByKey[key])).join("\n").toLowerCase();
    rowTextCache.set(row, text);
  }
  return words.every((w) => text.includes(w));
}

// Same word rule over a chosen list of values — for the searches that only look at a few
// fields (Claims Module: Policy No., Client Name, Assured, Accuterm Claim No.; Distribution
// and Renewal tables: policy number and client).
export function fieldsMatchSearch(values, search) {
  const words = searchWords(search);
  if (words.length === 0) return true;
  const text = values.map((v) => (v === null || v === undefined ? "" : String(v))).join("\n").toLowerCase();
  return words.every((w) => text.includes(w));
}
