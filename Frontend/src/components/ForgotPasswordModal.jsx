import { useState } from "react";
import axios from "axios";
import { API_BASE_URL } from "../api/config";
import { PASSWORD_HINT, passwordRuleError } from "../lib/passwordRule";
import { NO_CODE_HELP, looksLikeCode, requestErrorMessage } from "../lib/recoveryCode";
import { Field, ModalCard, PrimaryButton, SaveRecoveryCodeModal, SubmitError, TextButton } from "./RecoveryShared";

const EMPTY_FORM = { username: "", code: "", newPassword: "", confirmPassword: "" };

// Login page: Forgot password? (POST /auth/forgot-password, no login needed). Right username and
// recovery code: the password changes and the used code is replaced by a new one, shown once.
export default function ForgotPasswordModal({ isOpen, onClose }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [newCode, setNewCode] = useState(null);

  if (!isOpen) return null;

  const setField = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));

  const close = () => {
    setForm(EMPTY_FORM);
    setErrors({});
    setNewCode(null);
    onClose();
  };

  const validate = () => {
    const e = {};
    if (!form.username.trim()) e.username = "Username is required";
    if (!looksLikeCode(form.code)) e.code = "Enter the 12-character code, for example ABCD-EFGH-JKMN";
    const ruleError = passwordRuleError(form.newPassword, form.username.trim());
    if (ruleError) e.newPassword = ruleError;
    if (form.newPassword !== form.confirmPassword) e.confirmPassword = "Passwords do not match";
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
      const response = await axios.post(`${API_BASE_URL}/auth/forgot-password`, {
        username: form.username.trim(),
        recovery_code: form.code,
        new_password: form.newPassword,
      });
      setForm(EMPTY_FORM);
      setNewCode(response.data.recovery_code);
    } catch (error) {
      setErrors({ submit: requestErrorMessage(error, "Could not reset the password. Please try again.") });
    } finally {
      setLoading(false);
    }
  };

  if (newCode) {
    return (
      <SaveRecoveryCodeModal
        title="Password reset"
        intro="Your password was changed. You can now log in with your new password. The code you used no longer works; this is your new recovery code."
        code={newCode}
        onDone={close}
      />
    );
  }

  return (
    <ModalCard title="Forgot password" subtitle="Reset it with your recovery code" onClose={close}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <SubmitError message={errors.submit} />
        <Field label="Username" icon="user" placeholder="Your username" value={form.username}
               onChange={setField("username")} error={errors.username} autoFocus />
        <Field label="Recovery Code" icon="key" placeholder="XXXX-XXXX-XXXX" value={form.code}
               onChange={setField("code")} error={errors.code} />
        <Field label="New Password" type="password" placeholder="Create a new password" value={form.newPassword}
               onChange={setField("newPassword")} error={errors.newPassword} hint={PASSWORD_HINT} />
        <Field label="Confirm Password" type="password" placeholder="Confirm new password"
               value={form.confirmPassword} onChange={setField("confirmPassword")} error={errors.confirmPassword} />
        <PrimaryButton disabled={loading}>{loading ? "Resetting…" : "Reset Password"}</PrimaryButton>
        <TextButton onClick={close}>Back to Login</TextButton>
        <p className="text-[11px] text-gray-700 leading-snug text-center border-t border-gray-200 pt-3">
          {NO_CODE_HELP}
        </p>
      </form>
    </ModalCard>
  );
}
