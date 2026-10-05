// Filter by Date (Policy Holder Information). The tabs' date fields aren't all the same
// shape — most tabs pre-format theirs to "MM/DD/YYYY" during fetch, Policy and Claims keep
// the raw ISO string — so extractDateParts() reads either into the same {month, day, year}.
export function extractDateParts(value) {
  if (!value) return null;
  if (typeof value === "string" && value.includes("/")) {
    const [mm, dd, yyyy] = value.split("/").map(Number);
    if (!mm || !dd || !yyyy) return null;
    return { month: mm, day: dd, year: yyyy };
  }
  // "YYYY-MM-DD" or the server's local timestamp "YYYY-MM-DDTHH:MM:SS" (no time zone):
  // read the date as written. new Date() + getUTC* moved a survey imported before 08:00
  // (UTC+8) to the previous day.
  const iso = typeof value === "string" && value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return { month: Number(iso[2]), day: Number(iso[3]), year: Number(iso[1]) };
  const d = new Date(value);
  if (isNaN(d)) return null;
  return { month: d.getUTCMonth() + 1, day: d.getUTCDate(), year: d.getUTCFullYear() };
}

// picked = the calendar's local Date, or null. Once a date is picked, a row matches only
// when its date is that day — a row with no (or an unreadable) date is hidden. No date
// picked → every row matches.
export function matchesPickedDate(value, picked) {
  if (!picked) return true;
  const parts = extractDateParts(value);
  return !!parts
    && parts.month === picked.getMonth() + 1
    && parts.day === picked.getDate()
    && parts.year === picked.getFullYear();
}
