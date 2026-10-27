import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { useState } from 'react'
import AccountGuards from "./components/AccountGuards";
import MaagapLogin from "./pages/login";
import Overview from "./pages/overview";
import QuotationsProposal from "./pages/proposal";
import Claims from "./pages/claims";
import RenewalRatioMonitoring from "./pages/renewal";
import PolicyHolderInformation from "./pages/policy";
import PolicyDistribution from "./pages/distribution";
import SessionGuards from "./components/SessionGuards";

// Sidebar links merely grey out pages a role can't use — they never stopped
// direct URL navigation. This is the actual enforcement.
function ProtectedRoute({ allowedRoles, children }) {
  const token = localStorage.getItem("token");
  const role = localStorage.getItem("role");

  if (!token) return <Navigate to="/" replace />;
  if (!allowedRoles.includes(role)) return <Navigate to="/policy" replace />;

  // AccountGuards: the forced password change and the "Not you?" notice, on every logged-in page.
  return (
    <>
      <AccountGuards />
      {children}
    </>
  );
}

function App() {

  return (
    <Router>
      <SessionGuards />
      <Routes>
        <Route path="/" element={<MaagapLogin />} />
        <Route path="/overview" element={<ProtectedRoute allowedRoles={["manager"]}><Overview /></ProtectedRoute>} />
        <Route path="/proposal" element={<ProtectedRoute allowedRoles={["manager"]}><QuotationsProposal /></ProtectedRoute>} />
        <Route path="/claims" element={<ProtectedRoute allowedRoles={["manager"]}><Claims /></ProtectedRoute>} />
        <Route path="/distribution" element={<ProtectedRoute allowedRoles={["manager"]}><PolicyDistribution /></ProtectedRoute>} />
        <Route path="/policy" element={<ProtectedRoute allowedRoles={["manager", "admin"]}><PolicyHolderInformation /></ProtectedRoute>} />
        <Route path="/renewal" element={<ProtectedRoute allowedRoles={["manager"]}><RenewalRatioMonitoring /></ProtectedRoute>} />

      </Routes>
    </Router>
  )
}

export default App