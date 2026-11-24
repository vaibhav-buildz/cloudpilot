import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { getRuns, getRun, deleteRun, ApiError } from "../api/client";
import { RunSummary, SimulationResponse } from "../types/api";
import { DisclaimerBanner } from "../components/DisclaimerBanner";
import { SimulationResultView } from "../components/SimulationResultView";

export const HistoryPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [limit] = useState(10);
  const [offset, setOffset] = useState(0);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Detail view
  const [selectedRun, setSelectedRun] = useState<SimulationResponse | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Delete modal confirmation
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchRuns = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await getRuns(limit, offset);
      setRuns(data.runs);
      setTotal(data.total);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Failed to load past simulation runs.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [limit, offset]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  // Load single run detail when URL parameter id is present
  useEffect(() => {
    if (id) {
      setLoadingDetail(true);
      getRun(id)
        .then((data) => setSelectedRun(data))
        .catch((err) => {
          setErrorMsg(err.message || "Failed to load run detail.");
        })
        .finally(() => setLoadingDetail(false));
    } else {
      setSelectedRun(null);
    }
  }, [id]);

  const confirmDelete = async () => {
    if (!deleteId) return;
    setIsDeleting(true);
    try {
      await deleteRun(deleteId);
      setDeleteId(null);
      if (selectedRun?.id === deleteId) {
        setSelectedRun(null);
        navigate("/history", { replace: true });
      }
      await fetchRuns();
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Failed to delete run.");
      }
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="history-page">
      <DisclaimerBanner />

      <section className="card">
        <h1 className="card-title" style={{ fontSize: "1.4rem" }}>
          Visitor Simulation History
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
          Simulation runs are saved to your visitor session (scoped via HttpOnly
          secure cookie).
        </p>

        {errorMsg && (
          <div className="alert alert-error" style={{ marginTop: "1rem" }} role="alert">
            {errorMsg}
          </div>
        )}

        {isLoading ? (
          <div style={{ padding: "2rem 0", textAlign: "center" }}>
            Loading runs...
          </div>
        ) : runs.length === 0 ? (
          <div style={{ padding: "2rem 0", textAlign: "center", color: "var(--text-muted)" }}>
            No simulation runs saved yet.{" "}
            <Link to="/simulate">Run a simulation</Link> to generate history.
          </div>
        ) : (
          <>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Services</th>
                    <th>Steps</th>
                    <th>Target Viol</th>
                    <th>Comparator</th>
                    <th>H1 Verdict</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr
                      key={r.id}
                      style={{ cursor: "pointer" }}
                      onClick={() => navigate(`/history/${r.id}`)}
                    >
                      <td>
                        {new Date(r.created_at).toLocaleString(undefined, {
                          dateStyle: "short",
                          timeStyle: "short",
                        })}
                      </td>
                      <td>{r.n_services}</td>
                      <td>{r.n_steps}</td>
                      <td>{(r.target_violation * 100).toFixed(1)}%</td>
                      <td>{r.time_comparator}</td>
                      <td>
                        <span
                          className={`badge ${
                            r.time_h1_verdict
                              ? "badge-supported"
                              : "badge-not-supported"
                          }`}
                        >
                          {r.time_h1_verdict ? "SUPPORTED" : "NOT SUPPORTED"}
                        </span>
                      </td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <div style={{ display: "flex", gap: "0.5rem" }}>
                          <Link
                            to={`/history/${r.id}`}
                            className="btn btn-secondary"
                            style={{ padding: "0.2rem 0.5rem", fontSize: "0.75rem" }}
                          >
                            View
                          </Link>
                          <button
                            type="button"
                            className="btn btn-danger"
                            style={{ padding: "0.2rem 0.5rem", fontSize: "0.75rem" }}
                            onClick={() => setDeleteId(r.id)}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginTop: "1rem",
              }}
            >
              <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                Showing {runs.length > 0 ? offset + 1 : 0} -{" "}
                {Math.min(offset + limit, total)} of {total} runs
              </div>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={offset + limit >= total}
                  onClick={() => setOffset(offset + limit)}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      {/* Selected Run Detail */}
      {loadingDetail && (
        <div className="card" style={{ textAlign: "center", padding: "2rem" }}>
          Loading run details...
        </div>
      )}

      {selectedRun && (
        <div style={{ marginTop: "1.5rem" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "0.5rem",
            }}
          >
            <h2 className="card-title" style={{ margin: 0 }}>
              Run Detail: {selectedRun.id}
            </h2>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setSelectedRun(null);
                navigate("/history", { replace: true });
              }}
            >
              Close Detail
            </button>
          </div>
          <SimulationResultView result={selectedRun} />
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteId && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-content">
            <h3 style={{ marginBottom: "0.75rem" }}>Delete Run</h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
              Are you sure you want to permanently delete this simulation run? This
              action cannot be undone.
            </p>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                disabled={isDeleting}
                onClick={() => setDeleteId(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={isDeleting}
                onClick={confirmDelete}
              >
                {isDeleting ? "Deleting..." : "Confirm Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
