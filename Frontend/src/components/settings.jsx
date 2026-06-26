import { Shield, X, LogOut, UserCircle2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import CreateAccountModal from "./CreateAccountModal";

import Logo from "../img/MAAGAP_LOGO.png";

export default function ProfileModal({ isOpen, onClose, maxHeight = "min(700px, calc(100vh - 24px))" }) {
  const navigate = useNavigate();

  const userRole = localStorage.getItem("role");

  const displayRole =
    userRole === "admin"
      ? "Manager"
      : "Admin & Finance";

  const accountName = userRole === "admin" ? "Juan Dela Cruz" : "Mario Lopez";

  const [openAccountModal, setOpenAccountModal] = useState(false);

  const handleLogout = () => {
    localStorage.clear();
    navigate("/");
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-start"
          style={{ backgroundColor: "rgba(0,0,0,0.35)" }}
          onClick={onClose}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
        >
            <motion.div
            className="m-5 relative flex flex-col rounded-3xl shadow-2xl overflow-hidden"
            style={{
              width: "min(90vw, 320px)", // responsive: shrinks with viewport (zoom)
              minHeight: maxHeight, // configurable via prop
              maxHeight: "calc(100vh - 48px)", // keeps it inside viewport
              background: "#f5f5f0",
              fontFamily: "'Georgia', serif",
            }}
            onClick={(e) => e.stopPropagation()}
            initial={{ x: -400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -400, opacity: 0 }}
            transition={{
              duration: 0.55,
              ease: [0.34, 1.56, 0.64, 1],
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 pt-5 pb-3">
              <div className="flex items-center">

                <img
                  className="w-12 h-12"
                  src={Logo}
                  alt="Logo"
                />

                <div>
                  <p
                    style={{
                      fontSize: 15,
                      fontWeight: 800,
                      letterSpacing: "-0.3px",
                      lineHeight: 1.1,
                    }}
                  >
                    MAAGAP
                  </p>

                  <p
                    style={{
                      fontSize: 10,
                      color: "#555",
                      letterSpacing: "0.2px",
                    }}
                  >
                    Insurance, Inc.
                  </p>
                </div>
              </div>

              <button
                onClick={onClose}
                className="flex items-center justify-center rounded-full transition-colors"
                style={{
                  width: 30,
                  height: 30,
                  background: "#e5e5e0",
                  color: "#555",
                }}
              >
                <X size={15} strokeWidth={2.5} />
              </button>
            </div>

            {/* Divider */}
            <div
              style={{
                height: 1,
                background: "#e0e0da",
                margin: "0 20px",
              }}
            />

            {/* Body */}
            <div className="flex flex-col items-center flex-1 px-6 pt-6 pb-4">
              <p
                style={{
                  fontSize: 12,
                  color: "#888",
                  letterSpacing: "0.5px",
                  marginBottom: 16,
                }}
              >
                Malolos Branch
              </p>

              {/* Avatar */}
              <div
                className="flex items-center justify-center rounded-full mb-5"
                style={{
                  width: 110,
                  height: 110,
                  background:
                    "linear-gradient(145deg, #8a8a8a, #666)",
                  boxShadow: "0 6px 24px rgba(0,0,0,0.18)",
                }}
              >
                <UserCircle2
                  size={72}
                  color="white"
                  strokeWidth={1.2}
                />
              </div>

              {/* Name */}
              <p
                style={{
                  fontSize: 24,
                  fontWeight: 800,
                  color: "#1a1a1a",
                  letterSpacing: "-0.5px",
                  marginBottom: 4,
                }}
              >
                {accountName} 
              </p>

              {/* Role */}
              <p
                style={{
                  fontSize: 13,
                  color: "#888",
                  marginBottom: 8,
                }}
              >
                {displayRole}
              </p>

              {/* Email */}
              <p
                style={{
                  fontSize: 12.5,
                  color: "#555",
                  marginBottom: 28,
                }}
              >
                youremail@example.com
              </p>

              {userRole === "admin" && (
                <button
                  style={{
                    fontSize: 13,
                    color: "#4a7fc1",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    textDecoration: "underline",
                    textUnderlineOffset: 3,
                  }}
                  onClick={() => setOpenAccountModal(true)}
                >
                  Create an Account
                </button>
              )}
            </div>

            {/* Footer */}
            <div>
              <button
                className="flex items-center justify-center gap-2 p-5 cursor-pointer w-full transition-colors hover:bg-[#eeeee8]"
                onClick={handleLogout}
              >
                <LogOut size={18} strokeWidth={2} />
                Log out
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
      <CreateAccountModal
        key="create-account-modal"
        isOpen={openAccountModal}
        onClose={() => { setOpenAccountModal(false) }}
      />
    </AnimatePresence>
  );
}