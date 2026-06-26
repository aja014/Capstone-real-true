import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { useState } from 'react'
import MaagapLogin from "./pages/login";
import Overview from "./pages/overview";
import QuotationsProposal from "./pages/proposal";
import Claims from "./pages/claims";
import RenewalRatioMonitoring from "./pages/renewnal";
import PolicyHolderInformation from "./pages/policy";
import PolicyDistribution from "./pages/distribution";


function App() {

  return (
    <Router>
      <Routes>
        <Route path="/" element={<MaagapLogin />} />
        <Route path="/overview" element={<Overview />} />
        <Route path="/proposal" element={<QuotationsProposal />} />
        <Route path="/claims" element={<Claims />} />
        <Route path="/distribution" element={<PolicyDistribution />} />
        <Route path="/policy" element={<PolicyHolderInformation />} />
        <Route path="/renewal" element={<RenewalRatioMonitoring />} />

      </Routes>
    </Router>
  )
}

export default App