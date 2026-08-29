import { useState } from "react";
import { Upload, CheckCircle, XCircle, X, Loader2 } from "lucide-react";
import axios from "axios";

const API_BASE_URL = "http://127.0.0.1:8000";

const IMPORT_TARGETS = [
  { value: "policyholders", label: "Policyholders", endpoint: "/import/policyholders/upload" },
  { value: "fire-property", label: "Fire & Property Surveys", endpoint: "/import/fire-property/surveys/upload" },
  { value: "motor", label: "Motor Quotations", endpoint: "/import/motor/quotations/upload" },
];

// `key`-remounted by the parent whenever its default target changes, so
// `target` only needs a plain initial value — no effect required to keep it
// in sync with `defaultTarget` across re-opens.
export default function UploadModal({ isOpen, onClose, onUploadSuccess, defaultTarget = "policyholders" }) {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | uploading | done | error
  const [summary, setSummary] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [target, setTarget] = useState(defaultTarget);

  if (!isOpen) return null;

  const activeTarget = IMPORT_TARGETS.find((t) => t.value === target) || IMPORT_TARGETS[0];

  const uploadFile = async (file) => {
    setUploadedFile(file);
    setStatus("uploading");
    setErrorMsg(null);
    setSummary(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const token = localStorage.getItem("token");
      const response = await axios.post(
        `${API_BASE_URL}${activeTarget.endpoint}`,
        formData,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      setSummary(response.data);
      setStatus("done");
      onUploadSuccess?.();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || "Upload failed. Check the file and try again.");
      setStatus("error");
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  };

  const reset = (e) => {
    e.preventDefault();
    setUploadedFile(null);
    setStatus("idle");
    setSummary(null);
    setErrorMsg(null);
  };

  const handleClose = () => {
    setUploadedFile(null);
    setStatus("idle");
    setSummary(null);
    setErrorMsg(null);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
    >
      <div
        className={`relative w-[600px] max-w-[95vw] h-[350px] rounded-xl transition-colors ${
          dragging ? "bg-[#c8c8c8]" : "bg-[#d9d9d9]"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        {/* Close */}
        <button
          onClick={handleClose}
          className="absolute right-5 top-5 z-10 hover:opacity-70 transition"
        >
          <X className="w-8 h-8 text-black" />
        </button>

        {/* Upload Area */}
        <label className="flex h-full cursor-pointer flex-col items-center justify-center px-8 text-center">
          <input
            type="file"
            className="hidden"
            accept=".xlsx,.xls,.csv"
            onChange={handleFileChange}
            disabled={status === "uploading"}
          />

          {status === "idle" && (
            <>
              <Upload
                size={30}
                strokeWidth={2.5}
                className={`transition-transform duration-200 ${dragging ? "scale-110 text-gray-600" : "text-black"}`}
              />
              <h2 className="mt-3 text-2xl font-bold text-black">Upload Files</h2>
              <p className="mt-2 text-md text-gray-700">
                {dragging ? "Drop to upload" : "Drag files here to upload"}
              </p>
              <p className="mt-1 text-xs text-gray-500">or click anywhere to browse</p>

              <select
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                onClick={(e) => e.stopPropagation()}
                className="mt-4 text-xs bg-white border border-gray-300 rounded-lg px-3 py-1.5 text-gray-700"
              >
                {IMPORT_TARGETS.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </>
          )}

          {status === "uploading" && (
            <>
              <Loader2 size={40} className="animate-spin text-black" />
              <h2 className="mt-3 text-2xl font-bold text-black">Uploading...</h2>
              <p className="mt-2 text-md text-gray-700 font-medium max-w-[500px] truncate">
                {uploadedFile?.name}
              </p>
            </>
          )}

          {status === "done" && summary && (
            <>
              <CheckCircle size={60} className="text-[#FBBF24]" />
              <h2 className="mt-3 text-2xl font-bold text-[#FBBF24]">Import complete</h2>
              <p className="mt-2 text-sm text-gray-700">
                {summary.total_rows} row{summary.total_rows !== 1 ? "s" : ""} —{" "}
                {summary.matched} matched, {summary.unmatched_created} new,{" "}
                {summary.needs_review} needs review, {summary.failed} failed
              </p>
              {summary.failed > 0 && summary.errors?.[0] && (
                <p className="mt-1 text-xs text-red-500 max-w-[480px] truncate">
                  Row {summary.errors[0].source_row}: {summary.errors[0].error}
                </p>
              )}
              <button
                type="button"
                onClick={reset}
                className="mt-4 text-xs text-gray-500 underline hover:text-gray-700 transition"
              >
                Upload another file
              </button>
            </>
          )}

          {status === "error" && (
            <>
              <XCircle size={60} className="text-red-500" />
              <h2 className="mt-3 text-2xl font-bold text-red-500">Upload failed</h2>
              <p className="mt-2 text-sm text-gray-700 max-w-[480px]">{errorMsg}</p>
              <button
                type="button"
                onClick={reset}
                className="mt-4 text-xs text-gray-500 underline hover:text-gray-700 transition"
              >
                Try again
              </button>
            </>
          )}
        </label>
      </div>
    </div>
  );
}
