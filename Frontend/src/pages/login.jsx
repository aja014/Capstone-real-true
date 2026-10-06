import { useState, useEffect } from "react";
import { Shield, User, Lock, ArrowRight, Eye, EyeOff } from "lucide-react";
import Background_Cars from "../img/Background_Cars.jpg";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { SESSION_EXPIRED_KEY } from "../api/api";
import { API_BASE_URL } from "../api/config";
import { usernameFromToken } from "../lib/session";

import Logo from "../img/MAAGAP_LOGO.png";

export default function MaagapLogin() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  // Shown in red above the Login button (was a browser alert()); cleared on the next try.
  const [loginError, setLoginError] = useState(null);
  // Set by the shared 401 handler (api/api.js) when a login expired or became invalid.
  const [sessionNotice] = useState(() =>
    sessionStorage.getItem(SESSION_EXPIRED_KEY) ? "Your session has expired. Please log in again." : null
  );
  useEffect(() => { sessionStorage.removeItem(SESSION_EXPIRED_KEY); }, []);

  const navigate = useNavigate();

  const handleLogin = async () => {
    setIsLoading(true);
    setLoginError(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/login`, {
        username: username.trim(),
        password,
      });

      const role = response.data.role;
      const token = response.data.access_token;

      localStorage.setItem("role", role);
      localStorage.setItem("token", token);
      // Settings shows the stored spelling (token "sub"), not what was typed.
      localStorage.setItem("username", usernameFromToken(token, username.trim()));

      if (role === "manager") {
        navigate("/overview");
      } else {
        navigate("/policy");
      }
    } catch (error) {
      if (!error.response) {
        setLoginError("Can't reach the server. Please try again.");
      } else if (error.response.status === 401) {
        setLoginError("Invalid username or password");
      } else {
        setLoginError("Something went wrong on the server. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex overflow-hidden font-sans">
      {/* Left Panel */}
      <div className="relative w-full md:w-[55%] lg:w-[48%] bg-[#F5C800] flex flex-col px-10 sm:px-14 py-10 z-10">
        {/* Diagonal clip on right side — desktop only */}
        <div
          className="hidden md:block absolute top-0 right-0 h-full w-24 bg-[#F5C800] z-20"
          style={{ clipPath: "polygon(0 0, 100% 0, 100% 100%, 60% 100%)" }}
        />

        {/* Logo */}
        <div className="flex items-center mb-auto">
          <div className="rounded-md">
            <img className="w-full h-12" src={Logo} alt="Logo" />
          </div>

          <div className="leading-tight">
            <p className="font-black text-black text-lg tracking-tight leading-none">
              MAAGAP
            </p>
            <p className="text-black text-[11px] font-medium tracking-widest uppercase">
              Insurance, Inc.
            </p>
          </div>
        </div>

        {/* Hero Text */}
        <div className="mt-16 mb-10">
          <h1
            className="text-7xl text-black font-black leading-[1.05] mb-4"
            style={{
              fontSize: "clamp(2.4rem, 5vw, 3.6rem)",
              fontFamily: "'Inter', 'Times New Roman', serif",
              textAlign: "justify",
              textAlignLast: "left",
            }}
          >
            Be Ready.
            <br />
            Be Protected.
          </h1>
          <p
            className="text-black/70 text-sm sm:text-base leading-relaxed max-w-sm"
            style={{ textAlign: "justify" }}
          >
            Protect your vehicle and your future with coverage designed for real
            life.
          </p>
        </div>

        {/* Form */}
        <div className="flex flex-col gap-4 max-w-sm w-full mb-10 z-30 relative">
          {sessionNotice && (
            <p className="text-xs font-semibold text-black bg-white/70 rounded-lg px-3 py-2">
              {sessionNotice}
            </p>
          )}

          {/* Username */}
          <div className="relative">
            <User className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full pl-11 pr-4 py-3.5 rounded-full bg-white text-sm text-gray-700 placeholder-gray-400 outline-none focus:ring-2 focus:ring-black/20 transition shadow-sm"
            />
          </div>

          {/* Password */}
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type={showPassword ? "text" : "password"}
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full pl-11 pr-11 py-3.5 rounded-full bg-white text-sm text-gray-700 placeholder-gray-400 outline-none focus:ring-2 focus:ring-black/20 transition shadow-sm"
            />
            <button
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition"
            >
              {showPassword ? (
                <EyeOff className="w-4 h-4" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
            </button>
          </div>

          {loginError && (
            <p role="alert" className="text-xs font-semibold text-red-700 bg-white/70 rounded-lg px-3 py-2">
              {loginError}
            </p>
          )}

          {/* Login Button */}
          <div className="mt-2">
            <button
              onClick={handleLogin}
              disabled={isLoading}
              className="mb-10 flex items-center gap-2 border-2 border-black text-black bg-transparent hover:bg-black hover:text-[#F5C800] px-7 py-3 rounded-full font-bold text-sm transition-all duration-200 group"
            >
              {isLoading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                  Logging in...
                </span>
              ) : (
                <>
                  Login
                  <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
                </>
              )}
            </button>
          </div>

          {/* <p className="text-xs text-black/50 mt-1">
            Forgot your password?{" "}
            <span className="underline cursor-pointer hover:text-black transition">Reset here</span>
          </p> */}
        </div>

        {/* Footer */}
        <p className="text-[10px] text-black/40 relative z-30">
          © 2026 MAAGAP Insurance, Inc. All rights reserved.
        </p>
      </div>

      {/* Right Panel — Photo ---------------------------------------------------------------------------------------------*/}
      <div className="hidden md:block md:flex-1 relative overflow-hidden">
        {/* Diagonal overlay matching left panel */}
        <div
          className="absolute top-0 left-0 h-full w-28 bg-[#F5C800] z-10"
          style={{ clipPath: "polygon(0 0, 55% 0, 0 100%)" }}
        />
        <img
          src={Background_Cars}
          alt="Cars on a road"
          className="absolute inset-0 w-full h-full object-cover opacity-85 blur-[.3px]"
        />
        {/* Road background via CSS gradient + pattern (no external image) */}
        {/* <div className="absolute inset-0 bg-gradient-to-br from-slate-500 via-slate-600 to-slate-800" /> */}

        {/* Simulated road scene overlay */}
        {/* <div className="absolute inset-0 opacity-30"
          style={{
            backgroundImage: `repeating-linear-gradient(
              180deg,
              transparent 0px,
              transparent 60px,
              rgba(255,255,255,0.15) 60px,
              rgba(255,255,255,0.15) 75px
            )`,
          }}
        /> */}

        {/* Green canopy top */}
        {/* <div className="absolute top-0 left-0 right-0 h-40 bg-gradient-to-b from-green-800/60 to-transparent" /> */}

        {/* Color tint matching original photo mood */}
        {/* <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-green-900/20" /> */}

        {/* Tagline overlay */}
        <div className="absolute bottom-10 right-10 text-right z-20">
          <p className="text-white/60 text-xs tracking-widest uppercase font-light">
            Your journey, covered.
          </p>
        </div>
      </div>
    </div>
  );
}
