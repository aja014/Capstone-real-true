import { useState } from "react";
import {
  X,
  User,
  Mail,
  Lock,
  Eye,
  EyeOff,
  Shield,
  CheckCircle,
} from "lucide-react";
import api from "../api/api";
import { PASSWORD_HINT, passwordRuleError } from "../lib/passwordRule";
import LegalModal from "./LegalModal";
import { TERMS_OF_SERVICE, PRIVACY_POLICY } from "../content/legal";
import { SavedCheckbox, SecretBox } from "./RecoveryShared";

import Logo from "../img/MAAGAP_LOGO.png";

export default function CreateAccountModal({ isOpen, onClose }) {
  const [step, setStep] = useState("form"); // "form" | "success"
  const [form, setForm] = useState({
    email: "",
    username: "",
    password: "",
    confirmPassword: "",
  });
  const [showPass, setShowPass] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false); // disables Sign Up while the request runs
  const [legalDoc, setLegalDoc] = useState(null); // Terms / Privacy shown on top; form state kept
  // The new account's first recovery code: shown once on the success step, never stored.
  const [recoveryCode, setRecoveryCode] = useState(null);
  const [codeSaved, setCodeSaved] = useState(false);

  if (!isOpen) return null;

  const validate = () => {
    const e = {};
    if (!form.username.trim()) e.username = "Username is required";
    const passwordError = passwordRuleError(form.password, form.username);
    if (passwordError) e.password = passwordError;
    if (form.password !== form.confirmPassword)
      e.confirmPassword = "Passwords do not match";
    if (!agreed) e.agreed = "You must agree to the terms";
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
      const response = await api.post("/users", {
        username: form.username,
        password: form.password,
      });

      setRecoveryCode(response.data.recovery_code);
      setCodeSaved(false);
      setStep("success");
    } catch (error) {
      console.error(error);

      if (error.response) {
        const detail = error.response.data.detail;
        setErrors({
          // A 422 lists the refused fields: show them as "field: reason".
          submit: (Array.isArray(detail) ? detail.map((d) => `${d.loc?.at(-1)}: ${d.msg}`).join(" ") : detail) || "Registration failed",
        });
      } else {
        setErrors({
          submit: "Network error. Is backend running?",
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setStep("form");
    setLegalDoc(null);
    setForm({ username: "", password: "", confirmPassword: "" });
    setAgreed(false);
    setErrors({});
    setShowPass(false);
    setShowConfirm(false);
    setRecoveryCode(null);
    setCodeSaved(false);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget && step === "form") handleClose(); // the success step holds the code
      }}
    >
      {step === "form" ? (
        /* ── FORM STEP ─────────────────────────────────────────────── */
        <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 px-7 py-8">
          {/* Close */}
          <button
            onClick={handleClose}
            className="absolute top-4 right-4 text-gray-500 hover:text-black transition"
          >
            <X size={20} strokeWidth={2} />
          </button>

          {/* Header */}
          <div className="flex flex-col items-center mb-6">
            <div className="flex items-center mb-1">
              <div>
                <img className="w-fit h-14" src={Logo} alt="Logo" />
              </div>
              <div>
                <h2 className="text-xl font-black text-black tracking-tight">
                  Create Account
                </h2>
                <p className="text-xs text-gray-500">
                  Admin &amp; Finance Role
                </p>
              </div>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            {errors.submit && (
              <div className="bg-red-50 text-red-500 text-xs p-2 rounded mb-3 text-center border border-red-200">
                {errors.submit}
              </div>
            )}
            {/* Email */}
            {/* <div>
                            <div className={`flex items-center gap-2 bg-white rounded-xl px-4 py-3 border ${errors.username  ? "border-red-400" : "border-gray-200"} focus-within:border-yellow-400 transition`}>
                                <Mail size={15} className="text-gray-400 flex-shrink-0" />
                                <span className="text-xs font-semibold text-gray-600 whitespace-nowrap">Email</span>
                                <input
                                    type="email"
                                    placeholder="Enter your Email"
                                    value={form.email}
                                    onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                                    className="flex-1 text-xs outline-none bg-transparent text-gray-700 placeholder-gray-300 min-w-0"
                                />
                            </div>
                            {errors.username && <p className="text-[10px] text-red-500 mt-1 ml-1">{errors.username}</p>}
                        </div> */}

            {/* Username */}
            <div>
              <div
                className={`flex items-center gap-2 bg-white rounded-xl px-4 py-3 border ${errors.username ? "border-red-400" : "border-gray-200"} focus-within:border-yellow-400 transition`}
              >
                <User size={15} className="text-gray-400 flex-shrink-0" />
                <span className="text-xs font-semibold text-gray-600 whitespace-nowrap">
                  Username
                </span>
                <input
                  type="text"
                  placeholder="Enter your username"
                  value={form.username}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, username: e.target.value }))
                  }
                  className="flex-1 text-xs outline-none bg-transparent text-gray-700 placeholder-gray-300 min-w-0"
                />
              </div>
              {errors.username && (
                <p className="text-[10px] text-red-500 mt-1 ml-1">
                  {errors.username}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <div
                className={`flex items-center gap-2 bg-white rounded-xl px-4 py-3 border ${errors.password ? "border-red-400" : "border-gray-200"} focus-within:border-yellow-400 transition`}
              >
                <Lock size={15} className="text-gray-400 flex-shrink-0" />
                <span className="text-xs font-semibold text-gray-600 whitespace-nowrap">
                  Password
                </span>
                <input
                  type={showPass ? "text" : "password"}
                  placeholder="Create a password"
                  value={form.password}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, password: e.target.value }))
                  }
                  className="flex-1 text-xs outline-none bg-transparent text-gray-700 placeholder-gray-300 min-w-0"
                />
                <button
                  type="button"
                  onClick={() => setShowPass((v) => !v)}
                  className="text-gray-400 hover:text-gray-600 flex-shrink-0"
                >
                  {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              {errors.password ? (
                <p className="text-[10px] text-red-500 mt-1 ml-1">
                  {errors.password}
                </p>
              ) : (
                <p className="text-[10px] text-gray-400 mt-1 ml-1">
                  {PASSWORD_HINT}
                </p>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <div
                className={`flex items-center gap-2 bg-white rounded-xl px-4 py-3 border ${errors.confirmPassword ? "border-red-400" : "border-gray-200"} focus-within:border-yellow-400 transition`}
              >
                <Lock size={15} className="text-gray-400 flex-shrink-0" />
                <span className="text-xs font-semibold text-gray-600 whitespace-nowrap">
                  Confirm Password
                </span>
                <input
                  type={showConfirm ? "text" : "password"}
                  placeholder="Confirm password"
                  value={form.confirmPassword}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, confirmPassword: e.target.value }))
                  }
                  className="flex-1 text-xs outline-none bg-transparent text-gray-700 placeholder-gray-300 min-w-0"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  className="text-gray-400 hover:text-gray-600 flex-shrink-0"
                >
                  {showConfirm ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              {errors.confirmPassword && (
                <p className="text-[10px] text-red-500 mt-1 ml-1">
                  {errors.confirmPassword}
                </p>
              )}
            </div>

            {/* Terms */}
            <div>
              <label className="flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                  className="mt-0.5 w-3.5 h-3.5 accent-yellow-400 flex-shrink-0"
                />
                <span className="text-[11px] text-gray-500 leading-snug">
                  I agree to the{" "}
                  <button
                    type="button"
                    onClick={() => setLegalDoc(TERMS_OF_SERVICE)}
                    className="text-yellow-600 underline hover:text-yellow-700"
                  >
                    Terms of Service
                  </button>{" "}
                  and{" "}
                  <button
                    type="button"
                    onClick={() => setLegalDoc(PRIVACY_POLICY)}
                    className="text-yellow-600 underline hover:text-yellow-700"
                  >
                    Privacy Policy
                  </button>
                </span>
              </label>
              {errors.agreed && (
                <p className="text-[10px] text-red-500 mt-1 ml-1">
                  {errors.agreed}
                </p>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="mt-2 w-full bg-yellow-400 hover:bg-yellow-500 active:scale-[0.98] text-white font-bold text-sm rounded-xl py-3 transition-all disabled:opacity-60"
            >
              {loading ? "Creating…" : "Sign Up"}
            </button>
          </form>

          {/* <div className="p-5">
                        <hr/>
                        <p className="pt-5 text-center text-xs text-black">Already have an account?
                            <span className="pl-2">
                                <Link
                                    to="/"
                                    className="text-blue-600 underline hover:text-blue-700 underline"
                                >
                                    Login
                                </Link>
                            </span>
                        </p>
                    </div> */}
        </div>
      ) : (
        /* ── SUCCESS STEP ──────────────────────────────────────────── */
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 px-8 py-10 flex flex-col items-center text-center">
          {/* Animated check circle */}
          <div className="relative flex items-center justify-center mb-6">
            <svg width="90" height="90" viewBox="0 0 90 90" fill="none">
              <circle
                cx="45"
                cy="45"
                r="40"
                stroke="#FBBF24"
                strokeWidth="4"
                strokeDasharray="251"
                strokeDashoffset="0"
                strokeLinecap="round"
                style={{ animation: "dash 0.6s ease forwards" }}
              />
              <polyline
                points="28,46 40,58 62,34"
                stroke="#FBBF24"
                strokeWidth="4"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray="60"
                strokeDashoffset="0"
                style={{ animation: "dash2 0.4s 0.4s ease forwards" }}
              />
            </svg>
            <style>{`
              @keyframes dash  { from { stroke-dashoffset: 251; } to { stroke-dashoffset: 0; } }
              @keyframes dash2 { from { stroke-dashoffset: 60;  } to { stroke-dashoffset: 0; } }
            `}</style>
          </div>

          <h2 className="text-2xl font-black text-black mb-2">
            Account Created!
          </h2>
          <p className="text-sm text-gray-500 mb-7 leading-snug">
            Your account has been successfully created.
          </p>

          {recoveryCode && (
            <div className="w-full flex flex-col gap-3 mb-6 text-left">
              <SecretBox label="Recovery code for this account" value={recoveryCode} />
              <p className="text-xs text-gray-700 leading-snug">
                Give this code to the user together with the password. It is shown only once and lets them
                reset a forgotten password from the login page.
              </p>
              <SavedCheckbox checked={codeSaved} onChange={setCodeSaved} />
            </div>
          )}

          <button
            onClick={handleClose}
            disabled={!!recoveryCode && !codeSaved}
            className="w-full bg-yellow-400 hover:bg-yellow-500 active:scale-[0.98] text-black font-bold text-sm rounded-xl py-3 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Continue
          </button>
        </div>
      )}
      {legalDoc && (
        <LegalModal doc={legalDoc} onClose={() => setLegalDoc(null)} />
      )}
    </div>
  );
}
