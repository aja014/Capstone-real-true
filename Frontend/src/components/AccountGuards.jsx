import { useEffect, useState } from "react";
import { ShieldAlert } from "lucide-react";
import api from "../api/api";
import { PASSWORD_HINT, passwordRuleError } from "../lib/passwordRule";
import { noticeText, requestErrorMessage } from "../lib/recoveryCode";
import ChangePasswordModal from "./ChangePasswordModal";
import { Field, ModalCard, PrimaryButton, SubmitError, TextButton } from "./RecoveryShared";

const EMPTY_FORM = { currentPassword: "", newPassword: "", confirmPassword: "" };

// Mounted on every logged-in page (ProtectedRoute in App.jsx). Reads GET /users/me/account-status:
// - must_change_password (after a Manager or system administrator reset): a blocking "Set a new password" window. Until it
//   is done the backend answers every other request with 403 "Password change required" (not 401,
//   so the session is kept);
// - an unseen code change / reset: the "Not you?" notice, shown once (marked seen when shown).
export default function AccountGuards() {
  const [status, setStatus] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [noticeClosed, setNoticeClosed] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.get("/users/me/account-status")
      .then((r) => { if (!cancelled) setStatus(r.data); })
      .catch(() => {}); // a 401 is handled by api.js; anything else: the page works as before
    return () => { cancelled = true; };
  }, []);

  const notice = status && !status.must_change_password ? status.notice : null;

  useEffect(() => {
    if (notice) api.post("/users/me/account-status/seen", { id: notice.id }).catch(() => {});
  }, [notice]);

  const setField = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    const e = {};
    if (!form.currentPassword) e.currentPassword = "Temporary password is required";
    const ruleError = passwordRuleError(form.newPassword);
    if (ruleError) e.newPassword = ruleError;
    else if (form.newPassword === form.currentPassword)
      e.newPassword = "New password must be different from the temporary password.";
    if (form.newPassword !== form.confirmPassword) e.confirmPassword = "Passwords do not match";
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
      // A hosted copy that ends older sessions on a password change sends a new token.
      const newToken = response.data?.access_token;
      if (newToken) localStorage.setItem("token", newToken);
      window.location.reload(); // the page reloads its data, which was refused until now
    } catch (error) {
      setErrors({ submit: requestErrorMessage(error, "Could not change the password.") });
      setLoading(false);
    }
  };

  const logOut = () => {
    localStorage.clear();
    window.location.href = "/";
  };

  if (status?.must_change_password) {
    return (
      <ModalCard title="Set a new password" subtitle={localStorage.getItem("username") || undefined} onClose={null} z="z-[70]">
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <p className="text-sm text-gray-800 leading-snug">
            Your password was reset. Set a new password before you continue.
          </p>
          <SubmitError message={errors.submit} />
          <Field label="Temporary Password" type="password" placeholder="Your temporary password"
                 value={form.currentPassword} onChange={setField("currentPassword")} error={errors.currentPassword} autoFocus />
          <Field label="New Password" type="password" placeholder="Create a new password"
                 value={form.newPassword} onChange={setField("newPassword")} error={errors.newPassword} hint={PASSWORD_HINT} />
          <Field label="Confirm Password" type="password" placeholder="Confirm new password"
                 value={form.confirmPassword} onChange={setField("confirmPassword")} error={errors.confirmPassword} />
          <PrimaryButton disabled={loading}>{loading ? "Saving…" : "Set New Password"}</PrimaryButton>
          <TextButton onClick={logOut}>Log out</TextButton>
        </form>
      </ModalCard>
    );
  }

  if (passwordOpen) {
    return <ChangePasswordModal isOpen onClose={() => setPasswordOpen(false)} />;
  }

  if (notice && !noticeClosed) {
    return (
      <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/30 backdrop-blur-[1px]">
        <div role="alertdialog" aria-labelledby="account-notice-title" className="bg-white rounded-2xl shadow-xl w-[440px] max-w-[92vw] p-5">
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 id="account-notice-title" className="text-sm font-bold text-gray-900">Recovery code changed</h3>
              <p className="mt-1 text-sm text-gray-800 break-words">
                {noticeText(notice)} Not you? Change your password now.
              </p>
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button type="button" onClick={() => setNoticeClosed(true)}
              className="text-xs font-semibold text-gray-800 px-4 py-1.5 rounded-lg border border-gray-400 hover:bg-gray-100 transition">
              It was me
            </button>
            <button type="button" autoFocus onClick={() => { setNoticeClosed(true); setPasswordOpen(true); }}
              className="bg-black text-white text-xs font-semibold px-4 py-1.5 rounded-lg hover:bg-gray-800 transition">
              Change Password
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
