import { useRef, useState, useEffect } from "react";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

function parseLocalDate(str) {
  const [y, m, d] = str.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function toDateString(date) {
  if (!date) return "";
  const d = new Date(date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function toMonthString(date) {
  if (!date) return "";
  const d = new Date(date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function formatDay(date) {
  if (!date) return "Filter by Date";
  const d = new Date(date);
  return `${MONTHS[d.getMonth()]} ${d.getDate()}`;
}

function formatMonth(date) {
  if (!date) return "Select Month";
  const d = new Date(date);
  return `${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

// ── FullCalendarPicker ────────────────────────────────────────────────────────
export function FullCalendarPicker({ value, onChange }) {
  const inputRef = useRef(null);

  const openPicker = () => {
    if (inputRef.current) {
      try { inputRef.current.showPicker(); } catch { inputRef.current.click(); }
    }
  };

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={openPicker}
        className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-medium text-gray-700 hover:border-gray-400 transition whitespace-nowrap"
      >
        {formatDay(value)}
        <svg className="w-3 h-3 text-gray-400" viewBox="0 0 12 12" fill="currentColor">
          <path d="M6 8L1 3h10z" />
        </svg>
      </button>
      <input
        ref={inputRef}
        type="date"
        value={toDateString(value)}
        onChange={(e) => onChange(e.target.value ? parseLocalDate(e.target.value) : null)}
        className="absolute inset-0 opacity-0 pointer-events-none w-full h-full"
        tabIndex={-1}
      />
    </div>
  );
}

// ── MonthYearPicker ───────────────────────────────────────────────────────────
export function MonthYearPicker({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const [tempMonth, setTempMonth] = useState(() => value ? new Date(value).getMonth() : new Date().getMonth());
  const [tempYear, setTempYear] = useState(() => value ? new Date(value).getFullYear() : new Date().getFullYear());
  const [showMonthList, setShowMonthList] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
        setShowMonthList(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleOpen = () => {
    if (value) {
      setTempMonth(new Date(value).getMonth());
      setTempYear(new Date(value).getFullYear());
    }
    setShowMonthList(false);
    setOpen(true);
  };

  const handleOk = () => {
    onChange(new Date(tempYear, tempMonth, 1));
    setOpen(false);
    setShowMonthList(false);
  };

  const handleCancel = () => {
    setOpen(false);
    setShowMonthList(false);
  };

  const years = Array.from({ length: 7 }, (_, i) => 2022 + i);

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        type="button"
        onClick={handleOpen}
        className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-medium text-gray-700 hover:border-gray-400 transition whitespace-nowrap"
      >
        {formatMonth(value)}
        <svg className="w-3 h-3 text-gray-400" viewBox="0 0 12 12" fill="currentColor">
          <path d="M6 8L1 3h10z" />
        </svg>
      </button>

      {open && (
        <div className="absolute top-5 mt-2 right-0 z-30 bg-white rounded-2xl shadow-2xl border border-gray-100 overflow-hidden w-fit">
          <div className="px-5 pt-4 pb-2 border-b border-gray-100">
            <p className="text-xs text-gray-400 font-medium">Select date</p>
          </div>

          <div className="px-5 py-3">
            <button
              type="button"
              onClick={() => setShowMonthList(v => !v)}
              className="flex items-center gap-1.5 text-sm font-semibold text-gray-800 hover:text-black transition"
            >
              {MONTHS[tempMonth]} {tempYear}
              <svg className={`w-3 h-3 text-gray-500 transition-transform ${showMonthList ? "rotate-180" : ""}`} viewBox="0 0 12 12" fill="currentColor">
                <path d="M6 8L1 3h10z" />
              </svg>
            </button>

            {showMonthList && (
              <div className="mt-3 flex gap-2">
                <div className="flex-1 max-h-36 overflow-y-auto flex flex-col gap-0.5">
                  {MONTHS.map((m, i) => (
                    <button key={m} type="button" onClick={() => setTempMonth(i)}
                      className={`text-left text-xs px-2 py-1 rounded-lg transition ${tempMonth === i ? "bg-yellow-400 font-bold text-black" : "hover:bg-gray-100 text-gray-700"}`}>
                      {m}
                    </button>
                  ))}
                </div>
                <div className="flex flex-col gap-0.5 max-h-36 overflow-y-auto">
                  {years.map(y => (
                    <button key={y} type="button" onClick={() => setTempYear(y)}
                      className={`text-xs px-2 py-1 rounded-lg transition ${tempYear === y ? "bg-yellow-400 font-bold text-black" : "hover:bg-gray-100 text-gray-700"}`}>
                      {y}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-4 justify-end px-5 pt-4">
              <button type="button" onClick={handleCancel}
                className="text-xs font-semibold text-violet-500 hover:text-violet-700 transition">
                Cancel
              </button>
              <button type="button" onClick={handleOk}
                className="text-xs font-bold text-violet-600 hover:text-violet-800 transition">
                OK
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}