import React from "react";

export const Footer: React.FC = () => {
  return (
    <footer className="site-footer">
      <div>CloudPilot - ML-Based CPU Resource Allocation Research Prototype</div>
      <div className="footer-links">
        <a
          href="https://github.com/vy979/cloudpilot/blob/main/docs/hypotheses.md"
          target="_blank"
          rel="noreferrer"
        >
          Hypotheses
        </a>
        <a
          href="https://github.com/vy979/cloudpilot/blob/main/docs/study_plan.md"
          target="_blank"
          rel="noreferrer"
        >
          Study Plan
        </a>
        <a
          href="https://github.com/vy979/cloudpilot/blob/main/docs/deviations.md"
          target="_blank"
          rel="noreferrer"
        >
          Deviations Log
        </a>
      </div>
    </footer>
  );
};
