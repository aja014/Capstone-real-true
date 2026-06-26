import { useState } from "react";
import Sidebar from "../components/sidebar";
import { Dropdown } from "../components/PolicyDistributionShared";
import DailyView from "../components/DailyView";
import MTDView from "../components/MTDView";
import YTDView from "../components/YTDView";

const PERIODS = ["Daily", "MTD", "YTD"];

export default function PolicyDistribution() {
  const [period, setPeriod] = useState("Daily");

  return (
    <div className="min-h-screen bg-yellow-400 p-4 sm:p-6 flex gap-4">
      <div className="hidden md:flex flex-shrink-0">
        <Sidebar activeItem="Policy Distribution" />
      </div>

      <div className="flex-1 flex flex-col gap-4 min-w-0">
        {/* Period Switcher */}
        <div>
          <Dropdown
            label={period}
            options={PERIODS}
            value={period}
            onChange={setPeriod}
          />
        </div>

        {/* Conditional View */}
        {period === "Daily" && <DailyView />}
        {period === "MTD"   && <MTDView />}
        {period === "YTD"   && <YTDView />}
      </div>
    </div>
  );
}