import { X } from "lucide-react";

import Logo from "../img/MAAGAP_LOGO.png";

// "**bold**" inside a legal text → <strong>
function RichText({ text }) {
  return text
    .split(/(\*\*[^*]+\*\*)/g)
    .map((part, i) =>
      part.startsWith("**") && part.endsWith("**") ? (
        <strong key={i} className="font-semibold text-gray-800">
          {part.slice(2, -2)}
        </strong>
      ) : (
        part
      )
    );
}

// Terms of Service / Privacy Policy (content/legal.js), shown on top of another modal.
// Only this modal closes; the modal underneath keeps its state.
export default function LegalModal({ doc, onClose }) {
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50"
      onClick={(e) => {
        e.stopPropagation();
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 max-h-[85vh] flex flex-col">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-500 hover:text-black transition"
        >
          <X size={20} strokeWidth={2} />
        </button>

        {/* Header */}
        <div className="flex items-center gap-1 px-7 pt-7 pb-4 pr-12 border-b border-gray-100">
          <img className="w-fit h-12 flex-shrink-0" src={Logo} alt="Logo" />
          <div>
            <h2 className="text-base font-black text-black tracking-tight leading-snug">
              {doc.title}
            </h2>
            <p className="text-xs text-gray-500">{doc.effective}</p>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-7 py-5 flex flex-col gap-4">
          {doc.sections.map((section, i) => (
            <section key={section.heading}>
              <h3 className="text-sm font-bold text-black mb-1">
                {i + 1}. {section.heading}
              </h3>
              {section.text && (
                <p className="text-xs text-gray-600 leading-relaxed">
                  <RichText text={section.text} />
                </p>
              )}
              {section.bullets && (
                <ul className="list-disc pl-5 mt-1 flex flex-col gap-1">
                  {section.bullets.map((bullet) => (
                    <li key={bullet} className="text-xs text-gray-600 leading-relaxed">
                      <RichText text={bullet} />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>

        {/* Footer */}
        <div className="px-7 pt-3 pb-6 border-t border-gray-100">
          <button
            type="button"
            onClick={onClose}
            className="w-full bg-yellow-400 hover:bg-yellow-500 active:scale-[0.98] text-black font-bold text-sm rounded-xl py-3 transition-all"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
