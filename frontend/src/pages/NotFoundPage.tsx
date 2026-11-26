import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <section className="missing-page">
      <small>HTTP 404</small>
      <h1>Page not found</h1>
      <p>This workspace page has moved or the address is incorrect.</p>
      <Link to="/" className="btn btn-primary">
        Return to overview
      </Link>
    </section>
  );
}
