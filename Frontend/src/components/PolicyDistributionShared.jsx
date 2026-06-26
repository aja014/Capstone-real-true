import { useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { ChevronDown, ChevronLeft, ChevronRight, Search } from "lucide-react";

const PAGE_SIZE = 8;

export const tableData = [
    // January 2026
    { month: "January 2026",  policy: "POL-1001", client: "Juan Dela Cruz",    line: "Motor Car",       issued: "01/15/2026", expiry: "01/15/2027", premium: "₱2,500", sum: "₱850,000", status: "New"     },
    { month: "January 2026",  policy: "POL-1003", client: "Emily Fernandez",   line: "Fire & Property", issued: "01/15/2026", expiry: "01/15/2027", premium: "₱2,500", sum: "₱850,000", status: "New"     },
    { month: "January 2026",  policy: "POL-1005", client: "Lina Mercado",      line: "Fire & Property", issued: "01/15/2026", expiry: "01/15/2027", premium: "₱2,500", sum: "₱850,000", status: "Renewed" },
    { month: "January 2026",  policy: "POL-1007", client: "Antonio Reyes",     line: "Fire & Property", issued: "01/15/2026", expiry: "01/15/2027", premium: "₱2,500", sum: "₱850,000", status: "New"     },
    { month: "January 2026",  policy: "POL-1009", client: "Sofia Ramirez",     line: "Fire & Property", issued: "01/20/2026", expiry: "01/20/2027", premium: "₱3,000", sum: "₱920,000", status: "New"     },
    { month: "January 2026",  policy: "POL-1011", client: "Carmen Flores",     line: "Fire & Property", issued: "01/25/2026", expiry: "01/25/2027", premium: "₱2,800", sum: "₱780,000", status: "New"     },
    // February 2026
    { month: "February 2026", policy: "POL-1002", client: "Maria Santos",      line: "Motor Car",       issued: "02/01/2026", expiry: "01/15/2027", premium: "₱1,500", sum: "₱480,000", status: "Renewed" },
    { month: "February 2026", policy: "POL-1004", client: "Dennis Reyes",      line: "Motor Car",       issued: "02/01/2026", expiry: "01/15/2027", premium: "₱1,500", sum: "₱480,000", status: "New"     },
    { month: "February 2026", policy: "POL-1006", client: "Roberto Gomez",     line: "Fire & Property", issued: "02/01/2026", expiry: "01/15/2027", premium: "₱1,500", sum: "₱480,000", status: "Renewed" },
    { month: "February 2026", policy: "POL-1008", client: "Manuel Chua",       line: "Motor Car",       issued: "02/01/2026", expiry: "01/15/2027", premium: "₱1,500", sum: "₱480,000", status: "Renewed" },
    { month: "February 2026", policy: "POL-1010", client: "Ricardo Santiago",  line: "Motor Car",       issued: "02/05/2026", expiry: "02/05/2027", premium: "₱2,000", sum: "₱600,000", status: "Renewed" },
    { month: "February 2026", policy: "POL-1012", client: "Miguel Torres",     line: "Motor Car",       issued: "02/10/2026", expiry: "02/10/2027", premium: "₱1,800", sum: "₱520,000", status: "New"     },
    { month: "February 2026", policy: "POL-1013", client: "Leonor Rivera",     line: "Fire & Property", issued: "02/12/2026", expiry: "02/12/2027", premium: "₱3,200", sum: "₱950,000", status: "Renewed" },
    { month: "February 2026", policy: "POL-1014", client: "Jose Rizal",        line: "Motor Car",       issued: "02/15/2026", expiry: "02/15/2027", premium: "₱2,200", sum: "₱670,000", status: "New"     },
    { month: "February 2026", policy: "POL-1015", client: "Ana Reyes",         line: "Fire & Property", issued: "02/18/2026", expiry: "02/18/2027", premium: "₱2,900", sum: "₱810,000", status: "Renewed" },
    { month: "February 2026", policy: "POL-1016", client: "Pedro Gomez",       line: "Motor Car",       issued: "02/20/2026", expiry: "02/20/2027", premium: "₱1,700", sum: "₱510,000", status: "New"     },
    // March 2026
    { month: "March 2026",    policy: "POL-1017", client: "Rosa Mendoza",      line: "Fire & Property", issued: "03/01/2026", expiry: "03/01/2027", premium: "₱3,100", sum: "₱880,000", status: "New"     },
    { month: "March 2026",    policy: "POL-1018", client: "Carlos Bautista",   line: "Motor Car",       issued: "03/05/2026", expiry: "03/05/2027", premium: "₱2,300", sum: "₱720,000", status: "Renewed" },
    { month: "March 2026",    policy: "POL-1019", client: "Elena Cruz",        line: "Motor Car",       issued: "03/08/2026", expiry: "03/08/2027", premium: "₱1,900", sum: "₱580,000", status: "New"     },
    { month: "March 2026",    policy: "POL-1020", client: "Diego Santos",      line: "Fire & Property", issued: "03/10/2026", expiry: "03/10/2027", premium: "₱2,700", sum: "₱830,000", status: "Renewed" },
    { month: "March 2026",    policy: "POL-1021", client: "Tina Bautista",     line: "Motor Car",       issued: "03/12/2026", expiry: "03/12/2027", premium: "₱2,100", sum: "₱630,000", status: "New"     },
    { month: "March 2026",    policy: "POL-1022", client: "Marco Velarde",     line: "Fire & Property", issued: "03/15/2026", expiry: "03/15/2027", premium: "₱3,300", sum: "₱970,000", status: "New"     },
];

// ── Dropdown ──────────────────────────────────────────────────────────────────
export function Dropdown({ label, options, value, onChange }) {
    const [open, setOpen] = useState(false);
    return (
        <div className="relative">
            <button onClick={() => setOpen(o => !o)}
                className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-medium text-gray-700 hover:border-gray-400 transition whitespace-nowrap">
                {value || label}
                <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
            </button>
            {open && options && (
                <div className="absolute top-full mt-1 left-0 z-20 bg-white border border-gray-100 rounded-xl shadow-lg min-w-[140px]">
                    {options.map(opt => (
                        <button key={opt} onClick={() => { onChange?.(opt); setOpen(false); }}
                            className={`block w-full text-left px-4 py-2 text-xs hover:bg-yellow-50 transition ${(value || label) === opt ? "font-bold text-black" : "text-gray-600"}`}>
                            {opt}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

// ── StatCard ──────────────────────────────────────────────────────────────────
export function StatCard({ sub, value, label, target }) {
    return (
        <div className="bg-white rounded-2xl px-5 py-4 shadow-sm flex flex-col justify-between min-h-[110px]">
            <p className="text-gray-400 text-xs">{sub}</p>
            <p className="text-black font-black text-xl md:text-4xl leading-none my-2">{value}</p>
            <div>
                <p className="text-gray-500 text-xs">{label}</p>
                {target && <p className="text-gray-400 text-[11px] mt-0.5">Target: {target}</p>}
            </div>
        </div>
    );
}

// ── PolicyTable ───────────────────────────────────────────────────────────────
// When `data` is provided by a parent, the table uses it directly and hides
// the internal month dropdown (the parent's picker handles month filtering).
// When `data` is omitted, the table falls back to the full tableData with its
// own built-in month dropdown.
export function PolicyTable({ search, setSearch, extraFilters, data: externalData }) {
    const [page, setPage]           = useState(1);
    const [lineFilter, setLine]     = useState("Policy Line: All");
    const [statusFilter, setStatus] = useState("Status: All");

    const sourceData = externalData ?? tableData;

    const filtered = sourceData.filter(r => {
        const matchLine   = lineFilter   === "Policy Line: All" || r.line   === lineFilter;
        const matchStatus = statusFilter === "Status: All"      || r.status === statusFilter;
        const matchSearch = r.policy.toLowerCase().includes(search.toLowerCase()) ||
                            r.client.toLowerCase().includes(search.toLowerCase());
        return  matchLine && matchStatus && matchSearch;
    });

    const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    const safePage   = Math.min(page, totalPages);
    const pageRows   = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

    const handleMonthChange  = (val) => { setMonth(val);  setPage(1); };
    const handleLineChange   = (val) => { setLine(val);   setPage(1); };
    const handleStatusChange = (val) => { setStatus(val); setPage(1); };
    const handleSearch       = (e)   => { setSearch(e.target.value); setPage(1); };

    return (
        <div className="bg-white min-h-[500px] rounded-2xl p-5 shadow-sm flex flex-col flex-1">

            <div className="flex flex-wrap gap-2 mb-4 items-center">
                
                <Dropdown
                    label="Policy Line: All"
                    options={["Policy Line: All", "Motor Car", "Fire & Property"]}
                    value={lineFilter}
                    onChange={handleLineChange}
                />
                <Dropdown
                    label="Status: All"
                    options={["Status: All", "New", "Renewed"]}
                    value={statusFilter}
                    onChange={handleStatusChange}
                />
                <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2">
                    <Search className="w-3.5 h-3.5 text-gray-400" />
                    <input
                        className="text-xs outline-none text-gray-600 w-36"
                        placeholder="Search Policy Number"
                        value={search}
                        onChange={handleSearch}
                    />
                </div>
                {extraFilters}
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-xs text-center">
                    <thead>
                        <tr className="border-b border-gray-200">
                            {["Policy Number", "Client Name", "Policy Line", "Issued Date", "Expiry Date", "Premium", "Sum Insured", "Status"].map(h => (
                                <th key={h} className="py-3 px-3 text-gray-700 font-bold whitespace-nowrap">{h}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {pageRows.map((r, i) => (
                            <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
                                <td className="py-3 px-3">{r.policy}</td>
                                <td className="py-3 px-3">{r.client}</td>
                                <td className="py-3 px-3">{r.line}</td>
                                <td className="py-3 px-3">{r.issued}</td>
                                <td className="py-3 px-3">{r.expiry}</td>
                                <td className="py-3 px-3">{r.premium}</td>
                                <td className="py-3 px-3">{r.sum}</td>
                                <td className="py-3 px-3">{r.status}</td>
                            </tr>
                        ))}
                        {pageRows.length === 0 && (
                            <tr><td colSpan={8} className="py-6 text-gray-400 text-xs">No records found.</td></tr>
                        )}
                    </tbody>
                </table>
            </div>

            <div className="flex justify-end items-center gap-2 mt-auto text-xs text-gray-500">
                <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={safePage === 1}
                    className="disabled:opacity-30"
                >«</button>
                <span>{safePage} / {totalPages}</span>
                <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={safePage === totalPages}
                    className="disabled:opacity-30"
                >»</button>
            </div>
        </div>
    );
}

// ── MiniPie ───────────────────────────────────────────────────────────────────
export function MiniPie({ title, data, colors, sub = "As of March 2026" }) {
    return (
        <div className="bg-white rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
                <p className="font-bold text-black text-sm">{title}</p>
                <p className="text-gray-400 text-[10px]">{sub}</p>
            </div>
            <div className="flex items-center gap-3">
                <ResponsiveContainer width={110} height={100}>
                    <PieChart>
                        <Pie data={data} dataKey="value" cx="50%" cy="50%" outerRadius={46} labelLine={false}
                            label={({ cx, cy, midAngle, innerRadius, outerRadius, value }) => {
                                const RADIAN = Math.PI / 180;
                                const r = innerRadius + (outerRadius - innerRadius) * 0.5;
                                return <text x={cx + r * Math.cos(-midAngle * RADIAN)} y={cy + r * Math.sin(-midAngle * RADIAN)}
                                    fill="#fff" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={700}>{value}</text>;
                            }}>
                            {data.map((_, i) => <Cell key={i} fill={colors[i]} />)}
                        </Pie>
                    </PieChart>
                </ResponsiveContainer>
                <div className="flex flex-col gap-2">
                    {data.map((d, i) => (
                        <div key={d.name} className="flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: colors[i] }} />
                            <span className="text-[10px] text-gray-600">{d.name}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}