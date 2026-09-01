import { useEffect, useState } from "react";
import { X, Loader2, Link2, UserPlus, Trash2 } from "lucide-react";
import axios from "axios";

const API_BASE_URL = "http://127.0.0.1:8000";

// These two import types finalize a Policy row, which requires picking an
// existing quotation (no shared ID in the source data to auto-derive it from)
// rather than linking/creating a policyholder — see quotation-candidates below.
const POLICY_IMPORT_TYPES = ["fire_property_policy", "motor_policy"];

function formatAmount(amount) {
  if (amount === null || amount === undefined) return "—";
  const n = Number(amount);
  if (isNaN(n)) return "—";
  return `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function clientLabel(p) {
  return [p.last_name, p.first_name].filter(Boolean).join(", ") || `Client #${p.id}`;
}

export default function NeedsReviewModal({ isOpen, onClose, records, loading, policyholders, onResolved }) {
  const [selectedMatch, setSelectedMatch] = useState({}); // recordId -> policyholder id (string)
  const [selectedQuotation, setSelectedQuotation] = useState({}); // recordId -> quotation id (string)
  const [quotationCandidates, setQuotationCandidates] = useState({}); // recordId -> array | undefined (not fetched yet)
  const [busyId, setBusyId] = useState(null);
  const [rowError, setRowError] = useState({}); // recordId -> error message

  const authHeaders = () => {
    const token = localStorage.getItem("token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  useEffect(() => {
    if (!isOpen) return;
    records.forEach((r) => {
      const needsPicker = POLICY_IMPORT_TYPES.includes(r.import_type) && r.matched_policyholder_id;
      if (!needsPicker || quotationCandidates[r.id] !== undefined) return;

      axios
        .get(`${API_BASE_URL}/import/policyholders/records/${r.id}/quotation-candidates`, { headers: authHeaders() })
        .then((response) => setQuotationCandidates((prev) => ({ ...prev, [r.id]: response.data })))
        .catch(() => setQuotationCandidates((prev) => ({ ...prev, [r.id]: [] })));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, records]);

  if (!isOpen) return null;

  const resolve = async (recordId, body) => {
    setBusyId(recordId);
    setRowError((prev) => ({ ...prev, [recordId]: null }));
    try {
      await axios.patch(
        `${API_BASE_URL}/import/policyholders/records/${recordId}/resolve`,
        body,
        { headers: authHeaders() }
      );
      onResolved?.();
    } catch (err) {
      setRowError((prev) => ({
        ...prev,
        [recordId]: err.response?.data?.detail || "Failed to resolve this record.",
      }));
    } finally {
      setBusyId(null);
    }
  };

  const deleteRecord = async (recordId) => {
    if (!window.confirm("Discard this import row? It moves to the deleted archive.")) return;
    setBusyId(recordId);
    setRowError((prev) => ({ ...prev, [recordId]: null }));
    try {
      await axios.delete(
        `${API_BASE_URL}/import/policyholders/records/${recordId}`,
        { headers: authHeaders() }
      );
      onResolved?.();
    } catch (err) {
      setRowError((prev) => ({
        ...prev,
        [recordId]: err.response?.data?.detail || "Failed to delete this record.",
      }));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="relative w-[720px] max-w-[95vw] max-h-[85vh] bg-white rounded-2xl shadow-lg flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-black">Needs Review ({records.length})</h2>
          <button onClick={onClose} className="hover:opacity-70 transition">
            <X className="w-5 h-5 text-black" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {loading ? (
            <p className="text-center py-8 text-gray-400 text-xs">Loading...</p>
          ) : records.length === 0 ? (
            <p className="text-center py-8 text-gray-400 text-xs">Nothing needs review right now.</p>
          ) : (
            records.map((r) => {
              const needsPicker = POLICY_IMPORT_TYPES.includes(r.import_type) && r.matched_policyholder_id;
              const candidates = quotationCandidates[r.id];

              return (
                <div key={r.id} className="border border-gray-100 rounded-xl p-4">
                  <p className="text-[11px] text-gray-400 mb-2">
                    {r.source_file} — row {r.source_row}
                  </p>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-700 mb-3">
                    {Object.entries(r.raw_data || {})
                      .filter(([, v]) => v !== null && v !== "")
                      .map(([k, v]) => (
                        <div key={k}><span className="text-gray-400">{k}:</span> {String(v)}</div>
                      ))}
                  </div>

                  {needsPicker ? (
                    candidates === undefined ? (
                      <p className="text-xs text-gray-400">Loading quotation candidates...</p>
                    ) : candidates.length === 0 ? (
                      <p className="text-xs text-amber-600">
                        No unattached quotation found for this policyholder — import the quotation first.
                      </p>
                    ) : (
                      <div className="flex flex-wrap items-center gap-2">
                        <select
                          className="text-xs border border-gray-200 rounded-lg px-2 py-1.5"
                          value={selectedQuotation[r.id] || ""}
                          onChange={(e) =>
                            setSelectedQuotation((prev) => ({ ...prev, [r.id]: e.target.value }))
                          }
                        >
                          <option value="">Select quotation...</option>
                          {candidates.map((c) => (
                            <option key={c.id} value={c.id}>
                              {formatAmount(c.amount)} — {c.quotation_date || "no date"} (case #{c.case_id})
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          disabled={!selectedQuotation[r.id] || busyId === r.id}
                          onClick={() =>
                            resolve(r.id, { matched_quotation_id: Number(selectedQuotation[r.id]) })
                          }
                          className="flex items-center gap-1 text-xs font-medium bg-[#FBBF24] hover:bg-[#f0b30f] disabled:opacity-40 rounded-lg px-3 py-1.5 transition"
                        >
                          <Link2 className="w-3.5 h-3.5" /> Confirm
                        </button>
                        <button
                          type="button"
                          disabled={busyId === r.id}
                          onClick={() => deleteRecord(r.id)}
                          title="Discard this row"
                          className="flex items-center gap-1 text-xs font-medium text-gray-400 hover:text-red-500 disabled:opacity-40 rounded-lg px-2 py-1.5 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                        {busyId === r.id && <Loader2 className="w-4 h-4 animate-spin text-gray-400" />}
                      </div>
                    )
                  ) : (
                    <div className="flex flex-wrap items-center gap-2">
                      <select
                        className="text-xs border border-gray-200 rounded-lg px-2 py-1.5"
                        value={selectedMatch[r.id] || ""}
                        onChange={(e) =>
                          setSelectedMatch((prev) => ({ ...prev, [r.id]: e.target.value }))
                        }
                      >
                        <option value="">Link to existing client...</option>
                        {policyholders.map((p) => (
                          <option key={p.id} value={p.id}>{clientLabel(p)} (#{p.id})</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        disabled={!selectedMatch[r.id] || busyId === r.id}
                        onClick={() =>
                          resolve(r.id, { matched_policyholder_id: Number(selectedMatch[r.id]) })
                        }
                        className="flex items-center gap-1 text-xs font-medium bg-gray-100 hover:bg-gray-200 disabled:opacity-40 rounded-lg px-3 py-1.5 transition"
                      >
                        <Link2 className="w-3.5 h-3.5" /> Link
                      </button>
                      <button
                        type="button"
                        disabled={busyId === r.id}
                        onClick={() => resolve(r.id, { create_new: true })}
                        className="flex items-center gap-1 text-xs font-medium bg-[#FBBF24] hover:bg-[#f0b30f] disabled:opacity-40 rounded-lg px-3 py-1.5 transition"
                      >
                        <UserPlus className="w-3.5 h-3.5" /> Create as new
                      </button>
                      <button
                        type="button"
                        disabled={busyId === r.id}
                        onClick={() => deleteRecord(r.id)}
                        title="Discard this row"
                        className="flex items-center gap-1 text-xs font-medium text-gray-400 hover:text-red-500 disabled:opacity-40 rounded-lg px-2 py-1.5 transition"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                      {busyId === r.id && <Loader2 className="w-4 h-4 animate-spin text-gray-400" />}
                    </div>
                  )}
                  {rowError[r.id] && (
                    <p className="mt-2 text-[11px] text-red-500">{rowError[r.id]}</p>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
