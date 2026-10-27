import { useState } from "react";
import { createPortal } from "react-dom";
import { X, Lock, Eye, EyeOff, Copy, Check, KeyRound, User } from "lucide-react";

import Logo from "../img/MAAGAP_LOGO.png";

// Shared pieces of the recovery-code windows (Forgot password, Settings, Reset a Password,
// Account Created, the forced password change). Same look as ChangePasswordModal, darker text.

// The white card on a dark backdrop. onClose null = no X and no backdrop click (blocking window).
// Rendered into <body>, so no stacking context of the page (the login page's panels) can cover it.
export function ModalCard({ title, subtitle, onClose, children, wide = false, z = "z-50" }) {
  return createPortal(
    <div
      className={`fixed inset-0 ${z} flex items-center justify-center bg-black/50`}
      onClick={(e) => {
        if (onClose && e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-label={title}
        className={`relative bg-white rounded-2xl shadow-2xl w-full ${wide ? "max-w-md" : "max-w-sm"} mx-4 px-7 py-8 max-h-[calc(100vh-32px)] overflow-y-auto`}
      >
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="absolute top-4 right-4 text-gray-600 hover:text-black transition"
          >
            <X size={20} strokeWidth={2} />
          </button>
        )}
        <div className="flex items-center justify-center mb-6">
          <img className="w-fit h-14" src={Logo} alt="Logo" />
          <div>
            <h2 className="text-xl font-black text-black tracking-tight">{title}</h2>
            {subtitle && <p className="text-xs text-gray-600">{subtitle}</p>}
          </div>
        </div>
        {children}
      </div>
    </div>,
    document.body
  );
}

// One input row: icon, label, input. type "password" gets the show/hide eye.
export function Field({ label, placeholder, value, onChange, error, hint, type = "text", icon = "lock", autoFocus }) {
  const [show, setShow] = useState(false);
  const Icon = icon === "user" ? User : icon === "key" ? KeyRound : Lock;
  const inputType = type === "password" && !show ? "password" : "text";
  return (
    <div>
      <label
        className={`flex items-center gap-2 bg-white rounded-xl px-4 py-3 border ${error ? "border-red-500" : "border-gray-300"} focus-within:border-yellow-500 transition`}
      >
        <Icon size={15} className="text-gray-500 flex-shrink-0" />
        <span className="text-xs font-semibold text-gray-700 whitespace-nowrap">{label}</span>
        <input
          type={inputType}
          placeholder={placeholder}
          value={value}
          autoFocus={autoFocus}
          autoComplete="off"
          spellCheck={false}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1 text-xs outline-none bg-transparent text-gray-800 placeholder-gray-500 min-w-0"
        />
        {type === "password" && (
          <button
            type="button"
            onClick={() => setShow((v) => !v)}
            aria-label={show ? "Hide" : "Show"}
            className="text-gray-500 hover:text-gray-800 flex-shrink-0"
          >
            {show ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        )}
      </label>
      {error ? (
        <p className="text-[11px] text-red-700 mt-1 ml-1">{error}</p>
      ) : (
        hint && <p className="text-[11px] text-gray-600 mt-1 ml-1">{hint}</p>
      )}
    </div>
  );
}

export function SubmitError({ message }) {
  if (!message) return null;
  return (
    <div role="alert" className="bg-red-50 text-red-700 text-xs p-2 rounded text-center border border-red-200">
      {message}
    </div>
  );
}

export function PrimaryButton({ children, disabled, onClick, type = "submit" }) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className="mt-2 w-full bg-yellow-400 hover:bg-yellow-500 active:scale-[0.98] text-black font-bold text-sm rounded-xl py-3 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {children}
    </button>
  );
}

export function TextButton({ children, onClick }) {
  return (
    <button type="button" onClick={onClick} className="w-full text-gray-700 hover:text-black text-xs py-1 transition">
      {children}
    </button>
  );
}

// A secret shown once (recovery code or temporary password), large, with a Copy button.
export function SecretBox({ label, value }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false); // no clipboard access: the value stays on screen to write down
    }
  };
  return (
    <div className="w-full">
      <p className="text-xs font-semibold text-gray-700 mb-1">{label}</p>
      <div className="flex items-center gap-2 bg-yellow-50 border-2 border-yellow-400 rounded-xl px-4 py-3">
        <span className="flex-1 font-mono text-xl font-bold tracking-wider text-black select-all break-all">
          {value}
        </span>
        <button
          type="button"
          onClick={copy}
          className="flex items-center gap-1 text-xs font-semibold text-black bg-white border border-gray-400 rounded-lg px-2.5 py-1.5 hover:bg-gray-100 transition flex-shrink-0"
        >
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}

// "I saved this code" checkbox; Done stays disabled until it is ticked.
export function SavedCheckbox({ checked, onChange, label = "I saved this code" }) {
  return (
    <label className="flex items-center gap-2 text-xs font-semibold text-gray-800 cursor-pointer select-none">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="w-4 h-4 accent-yellow-500"
      />
      {label}
    </label>
  );
}

// "Save your recovery code" screen: used after a reset with the code, a code change, a Manager
// reset (with the temporary password) and Account Created. The code lives only in React state.
export function SaveRecoveryCodeModal({ title = "Save your recovery code", intro, code, temporaryPassword,
                                        username, checkboxLabel, onDone }) {
  const [saved, setSaved] = useState(false);
  return (
    <ModalCard title={title} subtitle={username} onClose={null} wide z="z-[60]">
      <div className="flex flex-col gap-4">
        {intro && <p className="text-sm text-gray-800 leading-snug">{intro}</p>}
        {temporaryPassword && <SecretBox label="Temporary password" value={temporaryPassword} />}
        <SecretBox label="Recovery code" value={code} />
        <p className="text-xs text-gray-700 leading-snug">
          This is shown only once. Keep it somewhere safe, away from your password. It works one time:
          after you use it, you get a new code.
        </p>
        <SavedCheckbox checked={saved} onChange={setSaved} label={checkboxLabel} />
        <PrimaryButton type="button" disabled={!saved} onClick={onDone}>
          Done
        </PrimaryButton>
      </div>
    </ModalCard>
  );
}
