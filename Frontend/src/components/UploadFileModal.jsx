import { useEffect, useRef, useState } from "react";
import { Upload, CheckCircle, XCircle, X, Loader2, FolderUp } from "lucide-react";
import axios from "axios";

const API_BASE_URL = "http://127.0.0.1:8000";

const IMPORT_TARGETS = [
  { value: "policyholders", label: "Policyholders", endpoint: "/import/policyholders/upload" },
  { value: "fire-property", label: "Fire & Property Surveys", endpoint: "/import/fire-property/surveys/upload" },
  { value: "motor", label: "Motor Quotations", endpoint: "/import/motor/quotations/upload" },
];

// Mirrors Backend/app/routers/import_batch.py's IMPORT_TYPE_REGISTRY.
const BATCH_IMPORT_TYPES = [
  { value: "policyholder", label: "Customer / Policyholder Information" },
  { value: "fire_property", label: "Fire & Property Survey" },
  { value: "fire_property_quotation", label: "Fire & Property Quotation" },
  { value: "fire_property_policy", label: "Fire & Property Policy" },
  { value: "motor", label: "Motor Quotation" },
  { value: "motor_policy", label: "Motor Policy" },
];

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// `key`-remounted by the parent whenever its default target changes, so
// `target` only needs a plain initial value — no effect required to keep it
// in sync with `defaultTarget` across re-opens.
export default function UploadModal({ isOpen, onClose, onUploadSuccess, defaultTarget = "policyholders" }) {
  const [mode, setMode] = useState("single"); // "single" | "folder"

  // ---- single-file mode state ----
  const [uploadedFile, setUploadedFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | uploading | done | error
  const [summary, setSummary] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [target, setTarget] = useState(defaultTarget);

  // ---- folder mode state ----
  const dirInputRef = useRef(null);
  const [folderFiles, setFolderFiles] = useState([]);
  const [folderStage, setFolderStage] = useState("idle"); // idle | detecting | review | importing | done
  const [detected, setDetected] = useState([]);
  const [chosenTypes, setChosenTypes] = useState({}); // filename -> type value
  const [batchResults, setBatchResults] = useState([]);
  const [folderError, setFolderError] = useState(null);

  useEffect(() => {
    // No first-class React prop for webkitdirectory -- set it imperatively.
    if (dirInputRef.current) dirInputRef.current.webkitdirectory = true;
  }, []);

  if (!isOpen) return null;

  const activeTarget = IMPORT_TARGETS.find((t) => t.value === target) || IMPORT_TARGETS[0];

  // ---- single-file handlers ----
  const uploadFile = async (file) => {
    setUploadedFile(file);
    setStatus("uploading");
    setErrorMsg(null);
    setSummary(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(`${API_BASE_URL}${activeTarget.endpoint}`, formData, { headers: authHeaders() });
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

  // ---- folder handlers ----
  const handleFolderChange = async (e) => {
    const files = Array.from(e.target.files || []).filter((f) => /\.(xlsx|xls|csv)$/i.test(f.name));
    e.target.value = ""; // allow picking the same folder again later
    if (files.length === 0) return;

    setFolderFiles(files);
    setFolderError(null);
    setFolderStage("detecting");

    const formData = new FormData();
    files.forEach((f) => formData.append("files", f, f.webkitRelativePath || f.name));

    try {
      const response = await axios.post(`${API_BASE_URL}/import/batch/detect`, formData, { headers: authHeaders() });
      setDetected(response.data.files);
      const initialChoices = {};
      response.data.files.forEach((d) => {
        if (d.best_guess) initialChoices[d.filename] = d.best_guess;
      });
      setChosenTypes(initialChoices);
      setFolderStage("review");
    } catch (err) {
      setFolderError(err.response?.data?.detail || "Could not read these files. Check they're valid Excel/CSV files.");
      setFolderStage("idle");
    }
  };

  const allTypesChosen = folderFiles.length > 0 && folderFiles.every((f) => chosenTypes[f.name]);

  const importAll = async () => {
    setFolderStage("importing");
    setFolderError(null);

    const formData = new FormData();
    folderFiles.forEach((f) => formData.append("files", f, f.webkitRelativePath || f.name));
    folderFiles.forEach((f) => formData.append("import_types", chosenTypes[f.name]));

    try {
      const response = await axios.post(`${API_BASE_URL}/import/batch/upload`, formData, { headers: authHeaders() });
      setBatchResults(response.data.files);
      setFolderStage("done");
      onUploadSuccess?.();
    } catch (err) {
      setFolderError(err.response?.data?.detail || "Import failed. Check the files and try again.");
      setFolderStage("review");
    }
  };

  const resetFolder = () => {
    setFolderFiles([]);
    setFolderStage("idle");
    setDetected([]);
    setChosenTypes({});
    setBatchResults([]);
    setFolderError(null);
  };

  const handleClose = () => {
    setUploadedFile(null);
    setStatus("idle");
    setSummary(null);
    setErrorMsg(null);
    resetFolder();
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
    >
      <div
        className={`relative bg-[#d9d9d9] rounded-xl transition-colors ${
          mode === "folder" ? "w-[680px] max-w-[95vw] h-[520px]" : "w-[600px] max-w-[95vw] h-[350px]"
        } ${mode === "single" && dragging ? "bg-[#c8c8c8]" : ""}`}
        onDragOver={mode === "single" ? (e) => { e.preventDefault(); setDragging(true); } : undefined}
        onDragLeave={mode === "single" ? () => setDragging(false) : undefined}
        onDrop={mode === "single" ? handleDrop : undefined}
      >
        {/* Close */}
        <button
          onClick={handleClose}
          className="absolute right-5 top-5 z-10 hover:opacity-70 transition"
        >
          <X className="w-8 h-8 text-black" />
        </button>

        {/* Mode toggle */}
        <div className="absolute left-5 top-5 z-10 flex bg-white/70 rounded-lg overflow-hidden text-xs font-medium">
          <button
            type="button"
            onClick={() => setMode("single")}
            className={`px-3 py-1.5 transition ${mode === "single" ? "bg-black text-white" : "text-gray-700 hover:bg-white"}`}
          >
            Single file
          </button>
          <button
            type="button"
            onClick={() => setMode("folder")}
            className={`px-3 py-1.5 transition ${mode === "folder" ? "bg-black text-white" : "text-gray-700 hover:bg-white"}`}
          >
            Folder
          </button>
        </div>

        {mode === "single" ? (
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
        ) : (
          <div className="flex h-full flex-col px-6 pt-16 pb-5">
            {folderStage === "idle" && (
              <label className="flex flex-1 cursor-pointer flex-col items-center justify-center text-center">
                <input
                  ref={dirInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  accept=".xlsx,.xls,.csv"
                  onChange={handleFolderChange}
                />
                <FolderUp size={30} strokeWidth={2.5} className="text-black" />
                <h2 className="mt-3 text-2xl font-bold text-black">Upload a Folder</h2>
                <p className="mt-2 text-md text-gray-700">Click to choose a folder of Excel/CSV files</p>
                <p className="mt-1 text-xs text-gray-500">Each file's type is detected automatically from its columns</p>
                {folderError && <p className="mt-3 text-xs text-red-500 max-w-[480px]">{folderError}</p>}
              </label>
            )}

            {folderStage === "detecting" && (
              <div className="flex flex-1 flex-col items-center justify-center text-center">
                <Loader2 size={40} className="animate-spin text-black" />
                <h2 className="mt-3 text-2xl font-bold text-black">Reading files...</h2>
              </div>
            )}

            {(folderStage === "review" || folderStage === "importing") && (
              <>
                <h2 className="text-lg font-bold text-black mb-1">Confirm file types</h2>
                <p className="text-xs text-gray-600 mb-3">
                  Files highlighted in amber couldn't be confidently detected — pick their type manually.
                </p>
                <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                  {detected.map((d) => (
                    <div
                      key={d.filename}
                      className={`rounded-lg border px-3 py-2 ${
                        d.confidence === "high" ? "border-gray-200 bg-white" : "border-amber-300 bg-amber-50"
                      }`}
                    >
                      <p className="text-xs font-medium text-gray-800 truncate">{d.filename}</p>
                      {d.error ? (
                        <p className="text-xs text-red-500 mt-1">{d.error}</p>
                      ) : (
                        <>
                          <select
                            value={chosenTypes[d.filename] || ""}
                            onChange={(e) => setChosenTypes((prev) => ({ ...prev, [d.filename]: e.target.value }))}
                            disabled={folderStage === "importing"}
                            className="mt-1 text-xs bg-white border border-gray-300 rounded px-2 py-1 w-full"
                          >
                            <option value="">Select type...</option>
                            {BATCH_IMPORT_TYPES.map((t) => (
                              <option key={t.value} value={t.value}>{t.label}</option>
                            ))}
                          </select>
                          {d.ambiguous && (
                            <p className="text-[11px] text-amber-700 mt-1">
                              Could be {d.candidates.filter((c) => c.score > 0).slice(0, 2).map((c) => c.label).join(" or ")}
                            </p>
                          )}
                        </>
                      )}
                    </div>
                  ))}
                </div>
                {folderError && <p className="mt-2 text-xs text-red-500">{folderError}</p>}
                <div className="flex items-center justify-between mt-3">
                  <button
                    type="button"
                    onClick={resetFolder}
                    className="text-xs text-gray-500 underline hover:text-gray-700 transition"
                  >
                    Start over
                  </button>
                  <button
                    type="button"
                    onClick={importAll}
                    disabled={!allTypesChosen || folderStage === "importing"}
                    className="flex items-center gap-1.5 bg-[#FBBF24] hover:bg-[#f0b30f] disabled:opacity-40 rounded-lg px-4 py-2 text-xs font-bold transition"
                  >
                    {folderStage === "importing" && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Import All ({folderFiles.length})
                  </button>
                </div>
              </>
            )}

            {folderStage === "done" && (
              <div className="flex-1 overflow-y-auto">
                <div className="flex items-center gap-2 mb-3">
                  <CheckCircle size={28} className="text-[#FBBF24]" />
                  <h2 className="text-lg font-bold text-[#FBBF24]">Import complete</h2>
                </div>
                <div className="space-y-2">
                  {batchResults.map((r) => (
                    <div
                      key={r.filename}
                      className={`rounded-lg border px-3 py-2 text-xs ${
                        r.error ? "border-red-200 bg-red-50" : "border-gray-200 bg-white"
                      }`}
                    >
                      <p className="font-medium text-gray-800 truncate">{r.filename}</p>
                      {r.error ? (
                        <p className="text-red-500 mt-1">{r.error}</p>
                      ) : (
                        <p className="text-gray-600 mt-1">
                          {r.summary.total_rows} row{r.summary.total_rows !== 1 ? "s" : ""} — {r.summary.matched} matched,{" "}
                          {r.summary.unmatched_created} new, {r.summary.needs_review} needs review, {r.summary.failed} failed
                        </p>
                      )}
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={resetFolder}
                  className="mt-4 text-xs text-gray-500 underline hover:text-gray-700 transition"
                >
                  Upload another folder
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
