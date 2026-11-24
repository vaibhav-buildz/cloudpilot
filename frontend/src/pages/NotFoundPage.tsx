import React from "react";
import { Link } from "react-router-dom";

export const NotFoundPage: React.FC = () => {
  return (
    <div className="card" style={{ margin: "3rem auto", maxWidth: 500, textAlign: "center" }}>
      <h1 className="card-title" style={{ fontSize: "1.5rem" }}>
        404 - Page Not Found
      </h1>
      <p style={{ color: "var(--text-muted)", marginBottom: "1.25rem" }}>
        The requested page does not exist or has been moved.
      </p>
      <Link to="/" className="btn btn-primary">
        Return to Overview
      </Link>
    </div>
  );
};
