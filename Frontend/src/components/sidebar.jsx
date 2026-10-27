import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  FileText,
  BarChart2,
  RefreshCw,
  AlertCircle,
  Users,
  Settings,
} from "lucide-react";

import Logo from "../img/MAAGAP_LOGO.png";

import ProfileModal from "./settings";

const navItems = [
  {
    icon: LayoutDashboard,
    label: "Overview",
    path: "/overview",
    allowedRoles: ["manager"],
  },
  {
    icon: FileText,
    label: "Quotations/ Proposal",
    path: "/proposal",
    allowedRoles: ["manager"],
  },
  {
    icon: BarChart2,
    label: "Policy Distribution",
    path: "/distribution",
    allowedRoles: ["manager"],
  },
  {
    icon: RefreshCw,
    label: "Renewal Ratio Monitoring",
    path: "/renewal",
    allowedRoles: ["manager"],
  },
  {
    icon: AlertCircle,
    label: "Claims",
    path: "/claims",
    allowedRoles: ["manager"],
  },
  {
    icon: Users,
    label: "Policy Holder Information",
    path: "/policy",
    allowedRoles: ["manager", "admin"],
  },
];

export default function Sidebar() {

  const [openModal, setOpenModal] = useState(false);

  const role = localStorage.getItem("role") || "admin";

  return (
    <>
      <aside className="w-48 min-h-full bg-white flex flex-col py-6 px-4 rounded-2xl shadow-sm">

        {/* Logo */}
        <div className="flex items-center mb-6">
          <div className="rounded-md">
            <img
              className="w-fit h-12"
              src={Logo}
              alt="Logo"
            />
          </div>

          <div className="leading-tight">
            <p className="text-black font-black text-sm tracking-wide uppercase">
              MAAGAP
            </p>

            <p className="text-gray-500 text-[10px] tracking-wider uppercase">
              Insurance, Inc.
            </p>
          </div>
        </div>

        <hr className="border-gray-200 mb-4" />

        {/* Navigation */}
        <nav className="flex flex-col gap-1 flex-1">
          {navItems.map(
            ({ icon: Icon, label, path, allowedRoles }) => {
              const hasAccess =
                allowedRoles.includes(role);

              // Admin & Finance sees only the pages it can open (no greyed-out items).
              if (!hasAccess) return null;

              return (
                <NavLink
                  key={path}
                  to={path}
                  className={({ isActive }) =>
                    `flex items-start gap-2.5 px-3 py-2.5 rounded-xl text-left transition-all duration-150 group ${isActive
                      ? "bg-yellow-400 text-black font-semibold"
                      : "text-gray-600 hover:bg-yellow-50 hover:text-black"
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon
                        className={`w-4 h-4 mt-0.5 flex-shrink-0 ${isActive
                            ? "text-black"
                            : "text-gray-400 group-hover:text-yellow-500"
                          }`}
                        strokeWidth={1.8}
                      />

                      <span className="text-xs leading-tight">
                        {label}
                      </span>
                    </>
                  )}
                </NavLink>
              );
            }
          )}
        </nav>

        {/* Settings */}
        <button
          className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-gray-500 hover:bg-yellow-50 hover:text-black transition-all duration-150 group mt-4"
          onClick={() => setOpenModal(true)}
        >
          <Settings
            className="w-4 h-4 text-gray-400 group-hover:text-yellow-500"
            strokeWidth={1.8}
          />

          <span className="text-xs font-medium">
            Settings
          </span>
        </button>
      </aside>

      <ProfileModal
        isOpen={openModal}
        onClose={() => setOpenModal(false)}
      />
    </>
  );
}