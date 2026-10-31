import { useState, useEffect } from "react";
import { User, Lock, ArrowRight, Eye, EyeOff } from "lucide-react";
import Background_Cars from "../img/Background_Cars.jpg";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { API_BASE_URL } from "../api/config";
import { usernameFromToken } from "../lib/session";
import { loginErrorMessage } from "../lib/loginErrors";
import { forgetIdleLogout, forgetLoginNotice, readLoginNotice } from "../lib/logoutReason";
import { markActivity } from "../lib/idleTimeout";
import { LAST_LOGIN_KEY, storedLastLogin } from "../lib/lastLogin";

import Logo from "../img/MAAGAP_LOGO.png";
import ForgotPasswordModal from "../components/ForgotPasswordModal";

export default function MaagapLogin() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [forgotOpen, setForgotOpen] = useState(false); // Forgot password window
  // Shown in red above the Login button (was a browser alert()); cleared on the next try.
  const [loginError, setLoginError] = useState(null);
  // Why the user is here: session expired / password changed elsewhere (shared 401 handler,
  // api/api.js) or the idle logout (lib/idleTimeout.js). Read once, then forgotten.
  const [sessionNotice] = useState(() => readLoginNotice());
  useEffect(() => { forgetLoginNotice(); }, []);

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
      markActivity(); // the idle timer starts from this login
      forgetIdleLogout();
      // "Last login" notice (shown by SessionGuards), only when the backend sends last_login.
      const lastLogin = storedLastLogin(response.data);
      if (lastLogin) sessionStorage.setItem(LAST_LOGIN_KEY, lastLogin);
      else sessionStorage.removeItem(LAST_LOGIN_KEY);

      if (role === "manager") {
        navigate("/overview");
      } else {
        navigate("/policy");
      }
    } catch (error) {
      setLoginError(loginErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col overflow-x-hidden font-sans">
      <div className="flex flex-1">
        {/* Left Panel */}
        <div className="relative w-full md:w-[55%] lg:w-[48%] bg-[#F5C800] flex flex-col px-10 sm:px-14 lg:pl-[100px] lg:pr-10 pt-[56px] pb-6 z-10">
          {/* Diagonal clip on right side — desktop only */}
          <div
            className="hidden md:block absolute top-0 right-0 h-full w-24 bg-[#F5C800] z-20"
            style={{ clipPath: "polygon(0 0, 100% 0, 100% 100%, 60% 100%)" }}
          />

          {/* Logo (the image has transparent padding, so the text overlaps it slightly) */}
          <div className="flex items-center -ml-[28px]">
            <img className="h-[88px] lg:h-[127px] w-auto" src={Logo} alt="MAAGAP logo" />
            <div className="-ml-[16px] flex flex-col">
              <p className="font-black text-black text-[34px] sm:text-[42px] lg:text-[55px] leading-none tracking-[-0.45px]">
                MAAGAP
              </p>
              <p className="ml-[2px] text-black text-[20px] sm:text-[25px] lg:text-[33px] leading-none font-semibold tracking-[1.1px] uppercase">
                Insurance, Inc.
              </p>
            </div>
          </div>

          {/* Hero Text */}
          <div className="mt-[67px]">
            <h1
              className="text-7xl text-black font-black leading-[0.81] mb-4"
              style={{
                fontSize: "clamp(2.4rem, 4.3vw, 4.6875rem)",
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
              className="text-black/70 text-sm sm:text-base lg:text-[20px] leading-relaxed lg:leading-[26px] max-w-[498px]"
              style={{ textAlign: "justify" }}
            >
              Protect your vehicle and your future with coverage designed for real
              life.
            </p>
          </div>

          {/* Form */}
          <div className="flex flex-col gap-4 max-w-[470px] w-full mt-[36px] z-30 relative">
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

            {/* Login Button and Forgot password? on one row */}
            <div className="mt-[10px] flex items-center justify-between">
              <button
                onClick={handleLogin}
                disabled={isLoading}
                className="w-[168px] flex items-center justify-center gap-2 border border-black text-black bg-transparent hover:bg-black hover:text-[#F5C800] py-3.5 rounded-full font-bold text-sm transition-all duration-200 group"
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
              <button
                type="button"
                onClick={() => setForgotOpen(true)}
                className="mr-[10px] text-xs font-semibold text-black/75 underline underline-offset-2 hover:text-black transition"
              >
                Forgot password?
              </button>
            </div>
          </div>
          <ForgotPasswordModal isOpen={forgotOpen} onClose={() => setForgotOpen(false)} />
        </div>

        {/* Right Panel — Photo */}
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
        </div>
      </div>

      {/* Footer band */}
      <footer className="relative z-30 bg-[#484E52] flex flex-col sm:flex-row items-center justify-between gap-1 px-6 sm:pl-[37px] sm:pr-6 py-3 sm:py-0 sm:h-20">
        <p className="text-[10px] font-bold text-[rgba(255,248,248,0.88)]">
          © 2026 MAAGAP Insurance, Inc. All rights reserved.
        </p>
        <p className="text-xs font-bold tracking-[1.2px] uppercase text-white/80">
          Your journey, covered.
        </p>
      </footer>
    </div>
  );
}
