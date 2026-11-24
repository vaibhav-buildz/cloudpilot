import React from "react";

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
      <div className="disclaimer-title">Simulator Disclaimer</div>
      <div>
        {customText ||
          "Simulated results. Does not reflect real cloud workloads. All CPU demands, arrival patterns, and resource limits are generated or synthetic unless uploaded."}
      </div>
    </aside>
  );
};
