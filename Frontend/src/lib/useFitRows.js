import { useEffect, useRef, useState } from "react";

// Rows per page that fit a table's white card down to its pagination line, so the table
// fills the screen instead of stopping halfway (fewer rows on a smaller screen).
//
// Worked out from the page's geometry, never from the rows shown right now:
//   rows = floor((card bottom - space under the rows - top of the first row) / row height)
// where the card bottom is the lowest of (a) the window bottom, (b) a taller card beside
// this one in the same row (Proposal's right-hand column, Renewal's rate card) and
// (c) the card's own min-height. Showing more or fewer rows moves none of these, so a new
// row count never changes the next measurement (no re-render loop), and the state is only
// set when the number actually changes.
//
// Markup it expects: `areaRef` is the table's scroll area, its parent is the white card,
// and the element right after it is the pagination bar (its top spacing as padding).

const MIN_ROWS = 5;
const MAX_ROWS = 50;
const DEFAULT_ROW_HEIGHT = 41;    // a text-xs row with py-3, until a real row is measured
const DEFAULT_HEADER_HEIGHT = 41;
const DEBOUNCE_MS = 100;

const px = (value) => parseFloat(value) || 0;
const bottomSpace = (style) => px(style.paddingBottom) + px(style.borderBottomWidth);

// Bottom of an element's own content (not of the height a flex row stretched it to).
function contentBottom(el) {
  const children = [...el.children];
  if (children.length === 0) return el.getBoundingClientRect().bottom;
  return Math.max(...children.map((c) => c.getBoundingClientRect().bottom)) + bottomSpace(getComputedStyle(el));
}

function measure(area, cache) {
  const card = area.parentElement;
  if (!card) return null;
  const pager = area.nextElementSibling;
  const cardStyle = getComputedStyle(card);

  const header = area.querySelector("thead");
  if (header) cache.header = header.offsetHeight;
  // Data rows only: "Loading…" / "No records found." rows span every column. The tallest
  // row seen so far is kept, so a page with a taller row can't make the count flip back and forth.
  for (const row of area.querySelectorAll("tbody > tr")) {
    if (!row.querySelector("td[colspan]")) cache.row = Math.max(cache.row ?? 0, row.offsetHeight);
  }
  const rowHeight = cache.row || DEFAULT_ROW_HEIGHT;

  const rowsTop = area.getBoundingClientRect().top + (cache.header ?? DEFAULT_HEADER_HEIGHT);
  const scrollbar = area.offsetHeight - area.clientHeight; // horizontal scrollbar, if any
  const underRows = scrollbar + (pager ? pager.offsetHeight : 0) + bottomSpace(cardStyle);

  // (a) window bottom with the page scrolled to the top (all positions here are relative
  // to the window as it is now), minus the padding of every box around the card
  let windowBottom = window.innerHeight - window.scrollY;
  for (let el = card.parentElement; el && el !== document.documentElement; el = el.parentElement) {
    windowBottom -= bottomSpace(getComputedStyle(el));
  }
  // (b) a taller neighbour in the same flex row
  let neighbourBottom = -Infinity;
  const parentStyle = getComputedStyle(card.parentElement);
  if (parentStyle.display.includes("flex") && parentStyle.flexDirection.startsWith("row")) {
    for (const sibling of card.parentElement.children) {
      if (sibling !== card) neighbourBottom = Math.max(neighbourBottom, contentBottom(sibling));
    }
  }
  // (c) the card's own min-height
  const minHeightBottom = card.getBoundingClientRect().top + px(cardStyle.minHeight);

  const room = Math.max(windowBottom, neighbourBottom, minHeightBottom) - underRows - rowsTop;
  return Math.min(MAX_ROWS, Math.max(MIN_ROWS, Math.floor(room / rowHeight)));
}

// `resetKey`: change it when the table switches to rows of another kind (e.g. another
// Type tab), so the row height is measured again.
export default function useFitRows(areaRef, resetKey) {
  const [rowsPerPage, setRowsPerPage] = useState(MIN_ROWS);

  const cache = useRef({});
  useEffect(() => {
    cache.current = {};
    let timer = null;
    const update = () => {
      timer = null;
      const area = areaRef.current;
      if (!area) return;
      const next = measure(area, cache.current);
      if (next !== null) setRowsPerPage((prev) => (prev === next ? prev : next));
    };
    const schedule = () => {
      clearTimeout(timer);
      timer = setTimeout(update, DEBOUNCE_MS);
    };

    // The whole document's size covers data loading above or beside the table.
    const observer = new ResizeObserver(schedule);
    observer.observe(document.documentElement);
    if (areaRef.current) observer.observe(areaRef.current);
    window.addEventListener("resize", schedule);
    schedule();
    return () => {
      clearTimeout(timer);
      observer.disconnect();
      window.removeEventListener("resize", schedule);
    };
  }, [areaRef, resetKey]);

  return rowsPerPage;
}
