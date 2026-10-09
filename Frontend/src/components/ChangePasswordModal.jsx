import { useState } from "react";
import { X, Lock, Eye, EyeOff } from "lucide-react";
import api from "../api/api";
import { PASSWORD_HINT, passwordRuleError } from "../lib/passwordRule";

import Logo from "../img/MAAGAP_LOGO.png";

const EMPTY_FORM = { currentPassword: "", newPassword: "", confirmPassword: "" };

function PasswordField({ label, placeholder, value, onChange, error, hint }) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <div
        className={`flex items-center gap-2 bg-white rounded-xl px-4 py-3 border ${error ? "border-red-400" : "border-gray-200"} focus-within:border-yellow-400 transition`}
      >
        <Lock size={15} className="text-gray-400 flex-shrink-0" />
        <span className="text-xs font-semibold text-gray-600 whitespace-nowrap">
          {label}
        </span>
        <input
          type={show ? "text" : "password"}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1 text-xs outline-none bg-transparent text-gray-700 placeholder-gray-300 min-w-0"
        />
        <button
          type="button"
          onClick={() => setShow((v) => !v)}
          className="text-gray-400 hover:text-gray-600 flex-shrink-0"
        >
          {show ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
      </div>
      {error ? (
        <p className="text-[10px] text-red-500 mt-1 ml-1">{error}</p>
      ) : (
        hint && <p className="text-[10px] text-gray-400 mt-1 ml-1">{hint}</p>
      )}
    </div>
  );
}

// Lets the logged-in user change their own password (POST /users/me/password).
// The user stays logged in afterwards. When the backend ends every older session
// (SESSION_ENDS_ON_PASSWORD_CHANGE), it sends this browser a new token.
export default function ChangePasswordModal({ isOpen, onClose }) {
  const [step, setStep] = useState("form"); // "form" | "success"
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [otherDevicesLoggedOut, setOtherDevicesLoggedOut] = useState(false);

  if (!isOpen) return null;

  const setField = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));

  const validate = () => {
    const e = {};
    if (!form.currentPassword) e.currentPassword = "Current password is required";
    const ruleError = passwordRuleError(form.newPassword, localStorage.getItem("username") || "");
    if (ruleError) e.newPassword = ruleError;
    else if (form.newPassword === form.currentPassword)
      e.newPassword = "New password must be different from the current password.";
    if (form.newPassword !== form.confirmPassword)
      e.confirmPassword = "Passwords do not match";
    return e;
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    const e = validate();
    if (Object.keys(e).length > 0) {
      setErrors(e);
      return;
    }
    setErrors({});
    setLoading(true);

    try {
      const response = await api.post("/users/me/password", {
        current_password: form.currentPassword,
        new_password: form.newPassword,
      });
      const newToken = response.data?.access_token;
      if (newToken) localStorage.setItem("token", newToken); // the old one no longer works
      setOtherDevicesLoggedOut(!!newToken);
      setStep("success");
    } catch (error) {
      console.error(error);
      const detail = error.response?.data?.detail;
      setErrors({
        submit: error.response
          ? typeof detail === "string"
            ? detail
            : "Could not change the password"
          : "Network error. Is backend running?",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setStep("form");
    setForm(EMPTY_FORM);
    setErrors({});
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      {step === "form" ? (
        <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 px-7 py-8">
          <button
            onClick={handleClose}
            className="absolute top-4 right-4 text-gray-500 hover:text-black transition"
          >
            <X size={20} strokeWidth={2} />
          </button>

          <div className="flex flex-col items-center mb-6">
            <div className="flex items-center mb-1">
              <div>
                <img className="w-fit h-14" src={Logo} alt="Logo" />
              </div>
              <div>
                <h2 className="text-xl font-black text-black tracking-tight">
                  Change Password
                </h2>
                <p className="text-xs text-gray-500">
                  {localStorage.getItem("username") || "Your account"}
                </p>
              </div>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            {errors.submit && (
              <div className="bg-red-50 text-red-500 text-xs p-2 rounded mb-3 text-center border border-red-200">
                {errors.submit}
              </div>
            )}

            <PasswordField
              label="Current Password"
              placeholder="Enter current password"
              value={form.currentPassword}
              onChange={setField("currentPassword")}
              error={errors.currentPassword}
            />
            <PasswordField
              label="New Password"
              placeholder="Create a new password"
              value={form.newPassword}
              onChange={setField("newPassword")}
              error={errors.newPassword}
              hint={PASSWORD_HINT}
            />
            <PasswordField
              label="Confirm New Password"
              placeholder="Confirm new password"
              value={form.confirmPassword}
              onChange={setField("confirmPassword")}
              error={errors.confirmPassword}
            />

            <button
              type="submit"
              disabled={loading}
              className="mt-2 w-full bg-yellow-400 hover:bg-yellow-500 active:scale-[0.98] text-white font-bold text-sm rounded-xl py-3 transition-all disabled:opacity-60"
            >
              {loading ? "Saving…" : "Change Password"}
            </button>
            <button
              type="button"
              onClick={handleClose}
              className="w-full text-gray-500 hover:text-black text-xs py-1 transition"
            >
              Cancel
            </button>
          </form>
        </div>
      ) : (
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xs mx-4 px-8 py-10 flex flex-col items-center text-center">
          <h2 className="text-2xl font-black text-black mb-2">
            Password Changed
          </h2>
          <p className="text-sm text-gray-500 mb-7 leading-snug">
            Use your new password the next time you log in.
            {otherDevicesLoggedOut && " You were logged out on every other device."}
          </p>
          <button
            onClick={handleClose}
            className="w-full bg-yellow-400 hover:bg-yellow-500 active:scale-[0.98] text-black font-bold text-sm rounded-xl py-3 transition-all"
          >
            Continue
          </button>
        </div>
      )}
    </div>
  );
}
