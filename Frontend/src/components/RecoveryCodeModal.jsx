import { useEffect, useState } from "react";
import api from "../api/api";
import { looksLikeCode, requestErrorMessage } from "../lib/recoveryCode";
import { Field, ModalCard, PrimaryButton, SaveRecoveryCodeModal, SubmitError, TextButton } from "./RecoveryShared";

const EMPTY_FORM = { currentPassword: "", currentCode: "" };

// Settings -> Recovery Code. The first code needs only the current password; changing a code needs
// the current password AND the current code (a stolen password alone cannot replace it).
export default function RecoveryCodeModal({ isOpen, onClose }) {
  const [status, setStatus] = useState(null); // { has_code, set_at } | null while loading
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [newCode, setNewCode] = useState(null);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    api.get("/users/me/recovery-code")
      .then((r) => { if (!cancelled) setStatus(r.data); })
      .catch((error) => { if (!cancelled) setErrors({ submit: requestErrorMessage(error, "Could not load the recovery code status.") }); });
    return () => { cancelled = true; };
  }, [isOpen]);

  if (!isOpen) return null;

  const hasCode = !!status?.has_code;
  const setField = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));

  const close = () => {
    setStatus(null);
    setForm(EMPTY_FORM);
    setErrors({});
    setNewCode(null);
    onClose();
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    const e = {};
    if (!form.currentPassword) e.currentPassword = "Current password is required";
    if (hasCode && !looksLikeCode(form.currentCode)) e.currentCode = "Enter your current 12-character recovery code";
    if (Object.keys(e).length > 0) {
      setErrors(e);
      return;
    }
    setErrors({});
    setLoading(true);
    try {
      const response = await api.post("/users/me/recovery-code", {
        current_password: form.currentPassword,
        ...(hasCode ? { current_code: form.currentCode } : {}),
      });
      setForm(EMPTY_FORM);
      setNewCode(response.data.recovery_code);
    } catch (error) {
      setErrors({ submit: requestErrorMessage(error, "Could not create the recovery code.") });
    } finally {
      setLoading(false);
    }
  };

  if (newCode) {
    return (
      <SaveRecoveryCodeModal
        username={localStorage.getItem("username") || undefined}
        intro={hasCode
          ? "Your recovery code was changed. The old code no longer works."
          : "Your first recovery code. Use it on the login page (Forgot password?) if you forget your password."}
        code={newCode}
        onDone={close}
      />
    );
  }

  const setAt = status?.set_at
    ? new Date(`${status.set_at}Z`).toLocaleString("en-US", { year: "numeric", month: "short", day: "numeric" })
    : null;

  return (
    <ModalCard title="Recovery Code" subtitle={localStorage.getItem("username") || "Your account"} onClose={close}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <SubmitError message={errors.submit} />
        {status && (
          <p className="text-sm text-gray-800 leading-snug">
            {hasCode
              ? `You have a recovery code${setAt ? ` (set on ${setAt})` : ""}. To change it, enter your current password and your current recovery code.`
              : "No recovery code yet. A recovery code lets you reset your password from the login page if you forget it. Enter your current password to generate one."}
          </p>
        )}
        <Field label="Current Password" type="password" placeholder="Enter current password"
               value={form.currentPassword} onChange={setField("currentPassword")} error={errors.currentPassword} />
        {hasCode && (
          <Field label="Current Code" icon="key" placeholder="XXXX-XXXX-XXXX" value={form.currentCode}
                 onChange={setField("currentCode")} error={errors.currentCode} />
        )}
        {hasCode && (
          <p className="text-[11px] text-gray-700 leading-snug">
            Lost your current code? Admin & Finance: ask the Manager to reset your password. Manager: contact the
            system administrator.
          </p>
        )}
        <PrimaryButton disabled={loading || !status}>
          {loading ? "Saving…" : hasCode ? "Change Code" : "Generate Code"}
        </PrimaryButton>
        <TextButton onClick={close}>Cancel</TextButton>
      </form>
    </ModalCard>
  );
}
