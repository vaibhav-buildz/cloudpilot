import React from "react";
import { Info } from "lucide-react";

interface DisclaimerBannerProps {
  customText?: string;
}

export const DisclaimerBanner: React.FC<DisclaimerBannerProps> = ({
  customText,
}) => {
  return (
    <aside
      className="disclaimer-banner"
      role="region"
      aria-label="Simulation disclaimer"
    >
      <Info size={16} aria-hidden="true" />
      <div>
        <strong className="disclaimer-title">Simulator disclaimer. </strong>
        {customText ||
          "Simulated results. Does not reflect real cloud workloads. All CPU demands, arrival patterns, and resource limits are generated or synthetic unless uploaded."}
      </div>
    </aside>
  );
};
