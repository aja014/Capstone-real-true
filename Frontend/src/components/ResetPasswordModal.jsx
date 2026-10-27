import { useEffect, useState } from "react";
import api from "../api/api";
import { requestErrorMessage } from "../lib/recoveryCode";
import { ModalCard, PrimaryButton, SaveRecoveryCodeModal, SubmitError, TextButton } from "./RecoveryShared";

// Settings -> Reset a Password (Manager only; the backend checks the role on every request).
// Lists Admin & Finance accounts only. A reset gives a temporary password and a new recovery code,
// both shown once; the user must set a new password at the next login.
export default function ResetPasswordModal({ isOpen, onClose }) {
  const [staff, setStaff] = useState(null); // [{ id, username }] | null while loading
  const [selectedId, setSelectedId] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null); // { username, temporary_password, recovery_code }

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    api.get("/users/staff")
      .then((r) => { if (!cancelled) setStaff(r.data); })
      .catch((e) => { if (!cancelled) setError(requestErrorMessage(e, "Could not load the accounts.")); });
    return () => { cancelled = true; };
  }, [isOpen]);

  if (!isOpen) return null;

  const selected = staff?.find((s) => String(s.id) === selectedId);

  const close = () => {
    setStaff(null);
    setSelectedId("");
    setConfirming(false);
    setError(null);
    setResult(null);
    onClose();
  };

  const reset = async () => {
    setError(null);
    setLoading(true);
    try {
      const response = await api.post(`/users/${selected.id}/reset-password`);
      setResult(response.data);
    } catch (e) {
      setError(requestErrorMessage(e, "Could not reset the password."));
      setConfirming(false);
    } finally {
      setLoading(false);
    }
  };

  if (result) {
    return (
      <SaveRecoveryCodeModal
        title="Password reset"
        username={result.username}
        intro={`Give ${result.username} the temporary password and the new recovery code in person. They must set a new password the next time they log in. Their old password and old code no longer work.`}
        temporaryPassword={result.temporary_password}
        code={result.recovery_code}
        checkboxLabel="I saved the temporary password and the code"
        onDone={close}
      />
    );
  }

  return (
    <ModalCard title="Reset a Password" subtitle="Admin & Finance accounts" onClose={close}>
      <div className="flex flex-col gap-3">
        <SubmitError message={error} />
        {!confirming ? (
          <>
            <p className="text-sm text-gray-800 leading-snug">
              For a user who forgot the password and has no recovery code. Choose the account:
            </p>
            {staff && staff.length === 0 && (
              <p className="text-xs text-gray-700">There are no Admin & Finance accounts yet.</p>
            )}
            {staff && staff.length > 0 && (
              <select
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                aria-label="Account"
                className="w-full text-sm text-gray-800 bg-white border border-gray-300 rounded-xl px-3 py-3 outline-none focus:border-yellow-500"
              >
                <option value="">Select an account</option>
                {staff.map((s) => (
                  <option key={s.id} value={s.id}>{s.username}</option>
                ))}
              </select>
            )}
            <PrimaryButton type="button" disabled={!selected} onClick={() => setConfirming(true)}>
              Reset Password
            </PrimaryButton>
            <TextButton onClick={close}>Cancel</TextButton>
          </>
        ) : (
          <>
            <p className="text-sm text-gray-800 leading-snug">
              Reset the password of <span className="font-bold">{selected.username}</span>? Their current password
              and recovery code will stop working, and you will get a temporary password and a new code to give them.
            </p>
            <PrimaryButton type="button" disabled={loading} onClick={reset}>
              {loading ? "Resetting…" : "Yes, reset the password"}
            </PrimaryButton>
            <TextButton onClick={() => setConfirming(false)}>Back</TextButton>
          </>
        )}
      </div>
    </ModalCard>
  );
}
