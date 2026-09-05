import { useState } from "react";
import Sidebar from "../components/sidebar";
import { Dropdown } from "../components/PolicyDistributionShared";
import RenewalDailyView from "../components/RenewalDailyView";
import RenewalMTDView from "../components/RenewalMTDView";
import RenewalYTDView from "../components/RenewalYTDView";

const PERIODS = ["Daily", "MTD", "YTD"];

export default function RenewalRatioMonitoring() {
  const [period, setPeriod] = useState("Daily");

  return (
    <div className="min-h-screen bg-yellow-400 p-4 sm:p-6 flex gap-4">
      <div className="hidden md:flex flex-shrink-0">
        <Sidebar activeItem="Renewal Ratio Monitoring" />
      </div>

      <div className="flex-1 flex flex-col gap-4 min-w-0">
        <div>
          <Dropdown label={period} options={PERIODS} value={period} onChange={setPeriod} />
        </div>

        {period === "Daily" && <RenewalDailyView />}
        {period === "MTD" && <RenewalMTDView />}
        {period === "YTD" && <RenewalYTDView />}
      </div>
    </div>
  );
}
