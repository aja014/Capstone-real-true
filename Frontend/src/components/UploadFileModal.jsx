import { useState } from "react";
import { Upload, CheckCircle, X } from "lucide-react";

export default function UploadModal({ isOpen, onClose }) {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [dragging, setDragging] = useState(false);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) setUploadedFile(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) setUploadedFile(file);
  };

  const handleClose = () => {
    setUploadedFile(null);
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
        <label className="flex h-full cursor-pointer flex-col items-center justify-center">
          <input type="file" className="hidden" onChange={handleFileChange} />

          {!uploadedFile ? (
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
          ) : (
            <>
              <CheckCircle size={70} className="text-[#FBBF24]" />
              <h2 className="mt-3 text-2xl font-bold text-[#FBBF24]">Uploaded!</h2>
              <p className="mt-2 text-md text-gray-700 font-medium max-w-[500px] truncate text-center px-4">
                {uploadedFile.name}
              </p>
              <p className="mt-1 text-xs text-gray-500">File uploaded successfully</p>
              <button
                type="button"
                onClick={(e) => { e.preventDefault(); setUploadedFile(null); }}
                className="mt-5 text-xs text-gray-500 underline hover:text-gray-700 transition"
              >
                Upload another file
              </button>
            </>
          )}
        </label>
      </div>
    </div>
  );
}