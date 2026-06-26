import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  Shield,
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
    allowedRoles: ["admin"],
  },
  {
    icon: FileText,
    label: "Quotations/ Proposal",
    path: "/proposal",
    allowedRoles: ["admin"],
  },
  {
    icon: BarChart2,
    label: "Policy Distribution",
    path: "/distribution",
    allowedRoles: ["admin"],
  },
  {
    icon: RefreshCw,
    label: "Renewal Ratio Monitoring",
    path: "/renewal",
    allowedRoles: ["admin"],
  },
  {
    icon: AlertCircle,
    label: "Claims",
    path: "/claims",
    allowedRoles: ["admin"],
  },
  {
    icon: Users,
    label: "Policy Holder Information",
    path: "/policy",
    allowedRoles: ["admin", "user"],
  },
];

export default function Sidebar() {

  const [openModal, setOpenModal] = useState(false);

  const role = localStorage.getItem("role") || "user";

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

              if (!hasAccess) {
                return (
                  <div
                    key={path}
                    className="flex items-start gap-2.5 px-3 py-2.5 rounded-xl text-gray-400 opacity-50 cursor-not-allowed"
                  >
                    <Icon
                      className="w-4 h-4 mt-0.5 flex-shrink-0"
                      strokeWidth={1.8}
                    />

                    <span className="text-xs leading-tight">
                      {label}
                    </span>
                  </div>
                );
              }

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