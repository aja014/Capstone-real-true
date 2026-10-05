import { XCircle } from "lucide-react";

// In-app message box (replaces the browser alert() for a refused/failed delete). Closed by
// OK (focused, so Enter works) or a click on the backdrop. message null = closed.
export default function NoticeModal({ title, message, onClose }) {
  if (!message) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-[1px]"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div role="alertdialog" aria-labelledby="notice-title" className="bg-white rounded-2xl shadow-xl w-[420px] max-w-[92vw] p-5">
        <div className="flex items-start gap-3">
          <XCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h3 id="notice-title" className="text-sm font-bold text-gray-800">{title}</h3>
            <p className="mt-1 text-xs text-gray-600 break-words">{message}</p>
          </div>
        </div>
        <div className="flex justify-end mt-4">
          <button type="button" autoFocus onClick={onClose}
            className="bg-black text-white text-xs px-4 py-1.5 rounded-lg hover:bg-gray-800 transition">
            OK
          </button>
        </div>
      </div>
    </div>
  );
}
