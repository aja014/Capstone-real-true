import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { ShieldCheck, X } from "lucide-react";
import ChangePasswordModal from "./ChangePasswordModal";
import { IDLE_TIMEOUT_MINUTES } from "../lib/securityConfig";
import { startIdleWatch } from "../lib/idleTimeout";
import { CHANGE_NOW_TEXT, LAST_LOGIN_KEY, NOT_YOU_TEXT, lastLoginText } from "../lib/lastLogin";

function readLastLogin() {
  try {
    const raw = sessionStorage.getItem(LAST_LOGIN_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

// Mounted once in App.jsx, on every page (IAS2 stolen-password controls):
// - idle logout after VITE_IDLE_TIMEOUT_MINUTES (0 = off, today's behaviour);
// - the "Last login" notice after a login, when the backend sent one (LOGIN_AUDIT=true).
export default function SessionGuards() {
  const { pathname } = useLocation();
  const [, setClosed] = useState(0); // re-render after the notice is closed
  const [passwordOpen, setPasswordOpen] = useState(false);

  useEffect(
    () => startIdleWatch(IDLE_TIMEOUT_MINUTES, () => {
      // Full reload, like the 401 handler: no page keeps showing data after the logout.
      if (window.location.pathname !== "/") window.location.href = "/";
    }),
    []
  );

  const loggedIn = pathname !== "/" && !!localStorage.getItem("token");
  const lastLogin = loggedIn ? readLastLogin() : null;

  const close = () => {
    sessionStorage.removeItem(LAST_LOGIN_KEY);
    setClosed((n) => n + 1);
  };

  return (
    <>
      {lastLogin && (
        <div
          role="status"
          className="fixed bottom-4 right-4 z-40 w-[360px] max-w-[calc(100vw-32px)] bg-white rounded-2xl shadow-xl border border-gray-200 p-4 flex items-start gap-3"
        >
          <ShieldCheck className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1 text-xs text-gray-700">
            <p className="font-semibold text-gray-800">{lastLoginText(lastLogin)}</p>
            <p className="mt-1">
              {NOT_YOU_TEXT}{" "}
              <button
                type="button"
                onClick={() => { close(); setPasswordOpen(true); }}
                className="text-[#4a7fc1] underline underline-offset-2 hover:text-black"
              >
                {CHANGE_NOW_TEXT}
              </button>
            </p>
          </div>
          <button type="button" onClick={close} aria-label="Close" className="text-gray-400 hover:text-black">
            <X size={16} />
          </button>
        </div>
      )}
      <ChangePasswordModal isOpen={passwordOpen && loggedIn} onClose={() => setPasswordOpen(false)} />
    </>
  );
}
