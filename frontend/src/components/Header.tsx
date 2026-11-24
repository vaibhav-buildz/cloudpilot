import React from "react";
import { NavLink } from "react-router-dom";

export const Header: React.FC = () => {
  return (
    <header className="site-header">
      <div className="header-content">
        <NavLink to="/" className="brand-title">
          CloudPilot
        </NavLink>
        <nav className="nav-links" aria-label="Main Navigation">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `nav-link ${isActive ? "active" : ""}`
            }
          >
            Overview
          </NavLink>
          <NavLink
            to="/study"
            className={({ isActive }) =>
              `nav-link ${isActive ? "active" : ""}`
            }
          >
            Study Findings
          </NavLink>
          <NavLink
            to="/simulate"
            className={({ isActive }) =>
              `nav-link ${isActive ? "active" : ""}`
            }
          >
            Simulate
          </NavLink>
          <NavLink
            to="/upload"
            className={({ isActive }) =>
              `nav-link ${isActive ? "active" : ""}`
            }
          >
            Upload CSV
          </NavLink>
          <NavLink
            to="/history"
            className={({ isActive }) =>
              `nav-link ${isActive ? "active" : ""}`
            }
          >
            History
          </NavLink>
        </nav>
      </div>
    </header>
  );
};
