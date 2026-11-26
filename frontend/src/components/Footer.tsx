import { BrandMark } from "./BrandMark";

const docs = "https://github.com/vaibhav-buildz/cloudpilot/blob/main/docs";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-inner shell-width">
        <span className="footer-brand">
          <BrandMark />
          CloudPilot
        </span>
        <nav aria-label="Research documentation">
          <a href={`${docs}/hypotheses.md`} target="_blank" rel="noreferrer">
            Hypotheses
          </a>
          <a href={`${docs}/study_plan.md`} target="_blank" rel="noreferrer">
            Study plan
          </a>
          <a href={`${docs}/deviations.md`} target="_blank" rel="noreferrer">
            Deviations log
          </a>
        </nav>
      </div>
    </footer>
  );
}
