import { useState } from "react";
import { Upload, CheckCircle, XCircle, X, Loader2, FolderUp } from "lucide-react";
import axios from "axios";

const API_BASE_URL = "http://127.0.0.1:8000";

const IMPORT_TARGETS = [
  { value: "policyholders", label: "Policyholders", endpoint: "/import/policyholders/upload" },
  { value: "fire-property", label: "Fire & Property Surveys", endpoint: "/import/fire-property/surveys/upload" },
  { value: "fire_property_quotation", label: "Fire & Property Quotations", endpoint: "/import/fire-property/quotations/upload" },
  { value: "fire_property_policy", label: "Fire & Property Policies", endpoint: "/import/fire-property/policies/upload" },
  { value: "motor", label: "Motor Quotations", endpoint: "/import/motor/quotations/upload" },
  { value: "motor_policy", label: "Motor Policies", endpoint: "/import/motor/policies/upload" },
  { value: "vehicle", label: "Vehicle Information", endpoint: "/import/vehicles/upload" },
  { value: "motor_claim", label: "Motor Claims", endpoint: "/import/claims/motor/upload" },
  { value: "fire_property_claim", label: "Fire & Property Claims", endpoint: "/import/claims/fire-property/upload" },
];

// Mirrors Backend/app/routers/import_batch.py's IMPORT_TYPE_REGISTRY.
const BATCH_IMPORT_TYPES = [
  { value: "policyholder", label: "Customer / Policyholder Information" },
  { value: "fire_property", label: "Fire & Property Survey" },
  { value: "fire_property_quotation", label: "Fire & Property Quotation" },
  { value: "fire_property_policy", label: "Fire & Property Policy" },
  { value: "motor", label: "Motor Quotation" },
  { value: "motor_policy", label: "Motor Policy" },
  { value: "vehicle", label: "Vehicle Information" },
  { value: "motor_claim", label: "Motor Claims" },
  { value: "fire_property_claim", label: "Fire & Property Claims" },
];

// IMPORT_TARGETS predates the backend's ImportType enum and kept its own
// value spellings for 2 entries ("policyholders", "fire-property") -- this
// bridges a detected/confirmed type (always one of BATCH_IMPORT_TYPES' enum
// values, since single-file detection reuses the same /import/batch/detect
// endpoint Folder mode calls) to the matching IMPORT_TARGETS entry.
const DETECTED_TYPE_TO_IMPORT_TARGET = {
  policyholder: "policyholders",
  fire_property: "fire-property",
  fire_property_quotation: "fire_property_quotation",
  fire_property_policy: "fire_property_policy",
  motor: "motor",
  motor_policy: "motor_policy",
  vehicle: "vehicle",
  motor_claim: "motor_claim",
  fire_property_claim: "fire_property_claim",
};
const IMPORT_TARGET_TO_DETECTED_TYPE = {
  policyholders: "policyholder",
  "fire-property": "fire_property",
  fire_property_quotation: "fire_property_quotation",
  fire_property_policy: "fire_property_policy",
  motor: "motor",
  motor_policy: "motor_policy",
  vehicle: "vehicle",
  motor_claim: "motor_claim",
  fire_property_claim: "fire_property_claim",
};

// These 2 importers geocode every row's address for the flood-risk lookup
// (app/services/flood_risk.py), rate-limited to >=1s/request against
// Nominatim -- worth calling out in the upload/import progress UI so a
// larger file doesn't look stuck.
const GEOCODED_BATCH_TYPES = new Set(["fire_property", "motor"]);

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// defaultTarget now only pre-fills the manual picker's dropdown when
// single-file detection is ambiguous or the user rejects its guess (the tab
// the modal was opened from is still a reasonable starting guess) -- it no
// longer drives an upfront type selector, since single-file mode detects
// the type from the file itself instead of asking first.
const ROW_MESSAGES_PREVIEW = 10;

// Every failed row ("Row n: reason", red) and every warning (amber) of one file's summary,
// collapsed to the first 10 lines with "Show all". Used by single-file and folder results.
function RowMessages({ summary }) {
  const [showAll, setShowAll] = useState(false);
  const rowLabel = (r) => (r.source_row ? `Row ${r.source_row}: ` : "");
  const lines = [
    ...(summary?.errors || []).map((e) => ({ text: rowLabel(e) + e.error, error: true })),
    ...(summary?.warnings || []).map((w) => ({ text: rowLabel(w) + w.warning, error: false })),
  ];
  if (lines.length === 0) return null;
  const shown = showAll ? lines : lines.slice(0, ROW_MESSAGES_PREVIEW);
  return (
    // preventDefault: in single-file mode this sits inside the file-picker <label>, and a
    // click on the list (e.g. to select text) must not open the picker.
    <div className="mt-1 w-full max-w-[520px] max-h-28 overflow-y-auto text-left text-xs" onClick={(e) => e.preventDefault()}>
      {shown.map((l, i) => (
        <p key={i} className={l.error ? "text-red-500" : "text-amber-700"}>{l.text}</p>
      ))}
      {lines.length > ROW_MESSAGES_PREVIEW && (
        <button
          type="button"
          onClick={(e) => { e.preventDefault(); setShowAll((s) => !s); }}
          className="mt-1 text-gray-500 underline hover:text-gray-700"
        >
          {showAll ? "Show less" : `Show all (${lines.length})`}
        </button>
      )}
    </div>
  );
}

// The detect endpoint's message for a file it couldn't open, without its prefix.
const unreadableReason = (error) => error.replace(/^Could not read file:\s*/, "");

export default function UploadModal({ isOpen, onClose, onUploadSuccess, defaultTarget = "policyholders" }) {
  const [mode, setMode] = useState("single"); // "single" | "folder"

  // ---- single-file mode state ----
  const [uploadedFile, setUploadedFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  // idle | detecting | confirm | picking | uploading | done | error
  const [status, setStatus] = useState("idle");
  const [summary, setSummary] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [detection, setDetection] = useState(null); // the single DetectedFile result, or null
  const [chosenType, setChosenType] = useState(""); // a BATCH_IMPORT_TYPES value

  // ---- folder mode state ----
  const [folderFiles, setFolderFiles] = useState([]);
  const [folderStage, setFolderStage] = useState("idle"); // idle | detecting | review | importing | done
  const [detected, setDetected] = useState([]);
  const [chosenTypes, setChosenTypes] = useState({}); // filename -> type value
  const [batchResults, setBatchResults] = useState([]);
  const [folderError, setFolderError] = useState(null);
  const [folderDragging, setFolderDragging] = useState(false);

  if (!isOpen) return null;

  // ---- single-file handlers ----
  // Runs the file's headers through the SAME detection endpoint Folder mode
  // calls (import_batch.detect_headers via /import/batch/detect) -- just with
  // one file in the list instead of many. Confident -> confirm step;
  // ambiguous/no guess/unreadable -> fall back to manual picking, exactly
  // like Folder mode's own per-file review row does.
  const detectSingleFile = async (file) => {
    setUploadedFile(file);
    setStatus("detecting");
    setErrorMsg(null);
    setSummary(null);
    setDetection(null);

    const formData = new FormData();
    formData.append("files", file);

    try {
      const response = await axios.post(`${API_BASE_URL}/import/batch/detect`, formData, { headers: authHeaders() });
      const result = response.data.files?.[0];
      if (!result) {
        setErrorMsg("Could not read this file. Check it's a valid Excel/CSV file.");
        setStatus("error");
        return;
      }

      setDetection(result);
      if (result.error) {
        setErrorMsg(result.error);
        setStatus("error");
      } else if (!result.ambiguous && result.best_guess) {
        setChosenType(result.best_guess);
        setStatus("confirm");
      } else {
        setChosenType(IMPORT_TARGET_TO_DETECTED_TYPE[defaultTarget] || "");
        setStatus("picking");
      }
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || "Could not read this file. Check it's a valid Excel/CSV file.");
      setStatus("error");
    }
  };

  // Runs the actual import once a type is confirmed (via the auto-detected
  // confirm step, or the manual picker) -- same upload behavior as before.
  const proceedUpload = async (type) => {
    const targetValue = DETECTED_TYPE_TO_IMPORT_TARGET[type] || type;
    const resolvedTarget = IMPORT_TARGETS.find((t) => t.value === targetValue);
    if (!resolvedTarget) {
      setErrorMsg("Unknown import type.");
      setStatus("error");
      return;
    }

    setStatus("uploading");
    setErrorMsg(null);
    setSummary(null);

    const formData = new FormData();
    formData.append("file", uploadedFile);

    try {
      const response = await axios.post(`${API_BASE_URL}${resolvedTarget.endpoint}`, formData, { headers: authHeaders() });
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
    if (file) detectSingleFile(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) detectSingleFile(file);
  };

  const reset = (e) => {
    e.preventDefault();
    setUploadedFile(null);
    setStatus("idle");
    setSummary(null);
    setErrorMsg(null);
    setDetection(null);
    setChosenType("");
  };

  // ---- folder handlers ----
  // A dropped folder only exposes its contents via
  // dataTransfer.items[].webkitGetAsEntry() (dataTransfer.files alone loses
  // the directory structure) -- not implemented, so a dropped folder is
  // safely ignored rather than falling through to the browser's default
  // navigate-to-file:// behavior. Click-to-browse (the native folder
  // picker below) remains the supported way to use Folder mode.
  const handleFolderDrop = (e) => {
    e.preventDefault();
    setFolderDragging(false);
    if (folderStage === "idle") {
      setFolderError("Drag-and-drop isn't supported for folders yet — click to browse instead.");
    }
  };

  const handleFolderChange = async (e) => {
    const rawFiles = Array.from(e.target.files || []);
    const files = rawFiles.filter((f) => /\.(xlsx|xls|csv)$/i.test(f.name));
    e.target.value = ""; // allow picking the same folder again later
    if (rawFiles.length === 0) {
      setFolderError("This folder is empty — please select a folder that contains files.");
      return;
    }
    if (files.length === 0) {
      setFolderError("No spreadsheet files (.xlsx, .xls or .csv) were found in this folder.");
      return;
    }

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

  // A file the detect step couldn't open is skipped; the rest of the folder still imports.
  const keyOf = (f) => f.webkitRelativePath || f.name;
  const unreadable = detected.filter((d) => d.error);
  const unreadableNames = new Set(unreadable.map((d) => d.filename));
  const readableFiles = folderFiles.filter((f) => !unreadableNames.has(keyOf(f)));
  const allTypesChosen = readableFiles.length > 0 && readableFiles.every((f) => chosenTypes[keyOf(f)]);

  const importAll = async () => {
    setFolderStage("importing");
    setFolderError(null);

    const formData = new FormData();
    readableFiles.forEach((f) => formData.append("files", f, keyOf(f)));
    readableFiles.forEach((f) => formData.append("import_types", chosenTypes[keyOf(f)]));

    try {
      const response = await axios.post(`${API_BASE_URL}/import/batch/upload`, formData, { headers: authHeaders() });
      const skipped = unreadable.map((d) => ({ filename: d.filename, skipped: true, error: unreadableReason(d.error) }));
      setBatchResults([...response.data.files, ...skipped]);
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
        } ${(mode === "single" && dragging) || (mode === "folder" && folderDragging) ? "bg-[#c8c8c8]" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (mode === "single") setDragging(true);
          else setFolderDragging(true);
        }}
        onDragLeave={() => {
          if (mode === "single") setDragging(false);
          else setFolderDragging(false);
        }}
        onDrop={mode === "single" ? handleDrop : handleFolderDrop}
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
              disabled={status === "uploading" || status === "detecting"}
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
              </>
            )}

            {status === "detecting" && (
              <>
                <Loader2 size={40} className="animate-spin text-black" />
                <h2 className="mt-3 text-2xl font-bold text-black">Detecting file type...</h2>
                <p className="mt-2 text-md text-gray-700 font-medium max-w-[500px] truncate">
                  {uploadedFile?.name}
                </p>
              </>
            )}

            {status === "confirm" && (
              <>
                <CheckCircle size={40} className="text-[#FBBF24]" />
                <h2 className="mt-3 text-xl font-bold text-black">
                  Detected as: {BATCH_IMPORT_TYPES.find((t) => t.value === chosenType)?.label || chosenType}
                </h2>
                <p className="mt-2 text-md text-gray-700 font-medium max-w-[500px] truncate">
                  {uploadedFile?.name}
                </p>
                <div className="mt-4 flex items-center gap-3">
                  <button
                    type="button"
                    onClick={(e) => { e.preventDefault(); proceedUpload(chosenType); }}
                    className="bg-[#FBBF24] hover:bg-[#f0b30f] rounded-lg px-4 py-2 text-xs font-bold transition"
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    onClick={(e) => { e.preventDefault(); setChosenType(""); setStatus("picking"); }}
                    className="text-xs text-gray-500 underline hover:text-gray-700 transition"
                  >
                    Not right? Choose type manually
                  </button>
                </div>
              </>
            )}

            {status === "picking" && (
              <>
                <h2 className="mt-3 text-xl font-bold text-black">Select the file type</h2>
                <p className="mt-2 text-xs text-gray-500 max-w-[480px]">
                  {detection?.ambiguous && detection.candidates?.some((c) => c.score > 0)
                    ? `Couldn't confidently tell which type this is — could be ${detection.candidates
                        .filter((c) => c.score > 0)
                        .slice(0, 2)
                        .map((c) => c.label)
                        .join(" or ")}.`
                    : "Pick the correct type for this file."}
                </p>
                <p className="mt-1 text-md text-gray-700 font-medium max-w-[500px] truncate">
                  {uploadedFile?.name}
                </p>
                <select
                  value={chosenType}
                  onChange={(e) => setChosenType(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  className="mt-3 text-xs bg-white border border-gray-300 rounded-lg px-3 py-1.5 text-gray-700"
                >
                  <option value="">Select type...</option>
                  {BATCH_IMPORT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
                <div className="mt-4 flex items-center gap-3">
                  <button
                    type="button"
                    disabled={!chosenType}
                    onClick={(e) => { e.preventDefault(); proceedUpload(chosenType); }}
                    className="bg-[#FBBF24] hover:bg-[#f0b30f] disabled:opacity-40 rounded-lg px-4 py-2 text-xs font-bold transition"
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    onClick={reset}
                    className="text-xs text-gray-500 underline hover:text-gray-700 transition"
                  >
                    Start over
                  </button>
                </div>
              </>
            )}

            {status === "uploading" && (
              <>
                <Loader2 size={40} className="animate-spin text-black" />
                <h2 className="mt-3 text-2xl font-bold text-black">Uploading...</h2>
                <p className="mt-2 text-md text-gray-700 font-medium max-w-[500px] truncate">
                  {uploadedFile?.name}
                </p>
                {GEOCODED_BATCH_TYPES.has(chosenType) && (
                  <p className="mt-2 text-xs text-gray-500 max-w-[480px]">
                    Processing — this may take longer for larger files due to flood-risk lookups.
                  </p>
                )}
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
                <RowMessages summary={summary} />
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
                  ref={(el) => { if (el) el.webkitdirectory = true; }}
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
                        <p className="text-xs text-red-500 mt-1">
                          Can't be read: {unreadableReason(d.error)} · will be skipped
                        </p>
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
                {folderStage === "importing" && Object.values(chosenTypes).some((t) => GEOCODED_BATCH_TYPES.has(t)) && (
                  <p className="mt-2 text-xs text-gray-500">
                    Processing — this may take longer for larger files due to flood-risk lookups.
                  </p>
                )}
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
                    Import All ({readableFiles.length})
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
                        r.skipped ? "border-gray-200 bg-gray-100"
                          : r.error ? "border-red-200 bg-red-50" : "border-gray-200 bg-white"
                      }`}
                    >
                      <p className="font-medium text-gray-800 truncate">{r.filename}</p>
                      {r.skipped ? (
                        <p className="text-gray-500 mt-1">Skipped — can't be read: {r.error}</p>
                      ) : r.error ? (
                        <p className="text-red-500 mt-1">{r.error}</p>
                      ) : (
                        <>
                          <p className="text-gray-600 mt-1">
                            {r.summary.total_rows} row{r.summary.total_rows !== 1 ? "s" : ""} — {r.summary.matched} matched,{" "}
                            {r.summary.unmatched_created} new, {r.summary.needs_review} needs review, {r.summary.failed} failed
                          </p>
                          <RowMessages summary={r.summary} />
                        </>
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
