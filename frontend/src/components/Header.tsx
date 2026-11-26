import { useEffect, useState } from "react";
import {
  BookOpen,
  FlaskConical,
  GitFork,
  History,
  LayoutGrid,
  Moon,
  Sun,
  Upload,
} from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { BrandMark } from "./BrandMark";

const pages = [
  { to: "/", label: "Overview", short: "Overview", icon: LayoutGrid },
  { to: "/study", label: "Research study", short: "Study", icon: BookOpen },
  {
    to: "/simulate",
    label: "Simulation",
    short: "Simulate",
    icon: FlaskConical,
  },
  { to: "/upload", label: "CSV upload", short: "Upload", icon: Upload },
  { to: "/history", label: "History", short: "History", icon: History },
];

export function Header() {
  const [light, setLight] = useState(
    () => document.documentElement.dataset.theme === "light",
  );
  useEffect(() => {
    function syncTheme(event: StorageEvent) {
      if (event.key === "cloudpilot-theme" || event.key === null) {
        const next = event.newValue === "light";
        document.documentElement.dataset.theme = next ? "light" : "dark";
        setLight(next);
      }
    }
    window.addEventListener("storage", syncTheme);
    return () => window.removeEventListener("storage", syncTheme);
  }, []);
  function switchTheme() {
    const theme = light ? "dark" : "light";
    document.documentElement.dataset.theme = theme;
    setLight(!light);
    try {
      localStorage.setItem("cloudpilot-theme", theme);
    } catch {
      /* In-memory theme still works. */
    }
  }
  return (
    <header className="site-header">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <div className="topbar shell-width">
        <div className="wordmark-group">
          <Link to="/" className="wordmark" aria-label="CloudPilot home">
            <BrandMark />
            CloudPilot
          </Link>
          <span className="brand-separator" aria-hidden="true" />
          <span className="workspace-name">Research workspace</span>
        </div>
        <div className="header-tools">
          <a
            className="repository-link"
            href="https://github.com/vaibhav-buildz/cloudpilot"
            target="_blank"
            rel="noreferrer"
            aria-label="CloudPilot GitHub repository"
          >
            <GitFork size={16} aria-hidden="true" />
            <span>GitHub</span>
          </a>
          <span className="tool-divider" />
          <button
            className="theme-button"
            type="button"
            onClick={switchTheme}
            aria-label={`Switch to ${light ? "dark" : "light"} theme`}
            title={`Switch to ${light ? "dark" : "light"} theme`}
          >
            {light ? <Moon size={17} /> : <Sun size={17} />}
          </button>
        </div>
      </div>
      <nav className="workspace-nav shell-width" aria-label="Main navigation">
        {pages.map(({ to, label, short, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className="workspace-link"
            aria-label={label}
          >
            <Icon size={15} aria-hidden="true" />
            <span className="wide-label">{label}</span>
            <span className="compact-label">{short}</span>
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
