import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  FileSpreadsheet,
  History,
  ListTree,
  LockKeyhole,
  Plus,
  Timer,
  Trash2,
  Workflow,
} from "lucide-react";
import { ApiError, deleteRun, getRun, getRuns } from "../api/client";
import { SimulationResultView } from "../components/SimulationResultView";
import { DisclaimerBanner } from "../components/DisclaimerBanner";
import type { SavedRun } from "../types/api";
import "./history.css";

const PAGE_SIZE = 10;

function historyPath(page: number, id?: string) {
  return `/history${id ? `/${encodeURIComponent(id)}` : ""}${page > 1 ? `?page=${page}` : ""}`;
}

function formatDuration(milliseconds: number | null) {
  if (milliseconds == null) return "Unrecorded";
  if (milliseconds < 1000) return `${milliseconds} ms`;
  if (milliseconds < 60000) return `${(milliseconds / 1000).toFixed(1)} s`;
  const seconds = Math.floor(milliseconds / 1000);
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function messageOf(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

function RunRow({
  run,
  details,
  onToggle,
  onDelete,
}: {
  run: SavedRun;
  details?: ReactNode;
  onToggle: () => void;
  onDelete: (run: SavedRun) => void;
}) {
  const expanded = details != null;
  const { n_services, n_steps, target_violation, seed, mode } = run.params;
  const SourceIcon = run.source === "csv" ? FileSpreadsheet : Workflow;
  const date = new Date(run.created_at);
  const summary = [
    n_services != null && `${n_services} services`,
    n_steps != null && `${n_steps.toLocaleString()} steps`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <li className="history-run">
      <div className="history-row">
        <button
          type="button"
          className="history-expand"
          onClick={onToggle}
          aria-label={`${expanded ? "Collapse" : "Expand"} run ${run.id}`}
          aria-describedby={`identity-${run.id} status-${run.id} duration-${run.id} created-${run.id}`}
          aria-expanded={expanded}
          aria-controls={expanded ? `details-${run.id}` : undefined}
        >
          <span className="history-identity" id={`identity-${run.id}`}>
            <span className="history-source-icon">
              <SourceIcon size={18} aria-hidden="true" />
            </span>
            <span>
              <strong>
                {mode === "extended-v1"
                  ? run.source === "csv"
                    ? "Extended CSV workload"
                    : "Extended synthetic workload"
                  : run.source === "csv"
                    ? "CSV workload"
                    : "Synthetic workload"}
              </strong>
              <span className="history-run-id">
                {run.id.slice(0, 8)}
                {summary && <span> · {summary}</span>}
              </span>
            </span>
          </span>
          <span className="history-status" id={`status-${run.id}`}>
            {run.status === "ok" ? (
              <>
                <CheckCircle2 size={14} aria-hidden="true" /> Completed
              </>
            ) : (
              <>
                <CircleAlert size={14} aria-hidden="true" /> Failed
              </>
            )}
          </span>
          <span
            className="history-duration"
            title="Execution duration"
            id={`duration-${run.id}`}
          >
            <Timer size={14} aria-hidden="true" />{" "}
            {formatDuration(run.duration_ms)}
          </span>
          <time
            dateTime={run.created_at}
            title={date.toLocaleString()}
            className="history-time"
            id={`created-${run.id}`}
          >
            <span>
              {date.toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </span>
            <span>
              {date.toLocaleTimeString(undefined, {
                hour: "numeric",
                minute: "2-digit",
              })}
            </span>
          </time>
          <ChevronDown
            size={15}
            className="history-chevron"
            aria-hidden="true"
          />
        </button>
        <button
          className="history-trash"
          type="button"
          aria-label={`Delete run ${run.id}`}
          title="Delete run"
          onClick={() => onDelete(run)}
        >
          <Trash2 size={15} aria-hidden="true" />
        </button>
      </div>
      {expanded && (
        <section
          className="history-details"
          id={`details-${run.id}`}
          aria-label={`Details for run ${run.id}`}
        >
          <dl className="history-metadata">
            <div>
              <dt>Run ID</dt>
              <dd>{run.id}</dd>
            </div>
            {target_violation != null && (
              <div>
                <dt>Violation target</dt>
                <dd>{Number((target_violation * 100).toFixed(2))}%</dd>
              </div>
            )}
            {seed != null && (
              <div>
                <dt>Random seed</dt>
                <dd>{seed}</dd>
              </div>
            )}
          </dl>
          {details}
        </section>
      )}
    </li>
  );
}

function DeleteDialog({
  run,
  onCancel,
  onDeleted,
}: {
  run: SavedRun;
  onCancel: () => void;
  onDeleted: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useLayoutEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);

  async function confirmDelete() {
    setBusy(true);
    setError("");
    try {
      await deleteRun(run.id);
      onDeleted();
    } catch (err) {
      setError(messageOf(err, "Could not delete this run. Try again."));
      setBusy(false);
    }
  }

  return (
    <dialog
      ref={dialog}
      className="history-dialog"
      aria-labelledby="history-delete-title"
      aria-describedby="history-delete-description"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onCancel();
      }}
    >
      <div className="history-dialog-body">
        <h2 id="history-delete-title">Delete this run?</h2>
        <p id="history-delete-description">
          This permanently removes run <code>{run.id.slice(0, 8)}</code> and its
          results from your history.
        </p>
        {error && <p role="alert">{error}</p>}
      </div>
      <div className="history-dialog-actions">
        <button
          autoFocus
          className="btn btn-secondary"
          type="button"
          disabled={busy}
          onClick={onCancel}
        >
          Cancel
        </button>
        <button
          className="btn btn-primary"
          type="button"
          disabled={busy}
          onClick={confirmDelete}
        >
          {busy ? "Deleting…" : "Delete run"}
        </button>
      </div>
    </dialog>
  );
}

type RunDetailState =
  | { status: "loading" }
  | { status: "ready"; run: SavedRun }
  | { status: "error"; message: string };

function useRunDetails(id: string) {
  const [state, setState] = useState<RunDetailState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    getRun(id, controller.signal)
      .then((run) => {
        if (!controller.signal.aborted) setState({ status: "ready", run });
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setState({
            status: "error",
            message: messageOf(err, "Could not load this run."),
          });
        }
      });
    return () => controller.abort();
  }, [id, attempt]);

  function retry() {
    setState({ status: "loading" });
    setAttempt((value) => value + 1);
  }

  return { state, retry };
}

function RunDetailStatus({
  state,
  onRetry,
}: {
  state: Exclude<RunDetailState, { status: "ready" }>;
  onRetry: () => void;
}) {
  if (state.status === "loading") {
    return <p role="status">Loading run details…</p>;
  }
  return (
    <>
      <p role="alert">{state.message}</p>
      <button type="button" className="btn btn-secondary" onClick={onRetry}>
        Retry loading run
      </button>
    </>
  );
}

function RunEvaluation({ run }: { run: SavedRun }) {
  if (run.result && run.status === "ok") {
    return (
      <SimulationResultView result={run.result} source={run.source} persisted />
    );
  }
  return (
    <p className="history-detail-message">
      {run.error || "No evaluation results were recorded for this run."}
    </p>
  );
}

function InlineRunDetails({ id }: { id: string }) {
  const { state, retry } = useRunDetails(id);
  return state.status === "ready" ? (
    <RunEvaluation run={state.run} />
  ) : (
    <RunDetailStatus state={state} onRetry={retry} />
  );
}

function LinkedRun({
  id,
  onClose,
  onDelete,
}: {
  id: string;
  onClose: () => void;
  onDelete: (run: SavedRun) => void;
}) {
  const { state, retry } = useRunDetails(id);
  if (state.status === "ready") {
    return (
      <RunRow
        run={state.run}
        details={<RunEvaluation run={state.run} />}
        onToggle={onClose}
        onDelete={onDelete}
      />
    );
  }
  return (
    <li className="history-linked-state">
      <RunDetailStatus state={state} onRetry={retry} />
      {state.status === "error" && (
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          Close details
        </button>
      )}
    </li>
  );
}

function RunHistory({ page }: { page: number }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [records, setRecords] = useState<SavedRun[] | null>(null);
  const [listError, setListError] = useState("");
  const [revision, setRevision] = useState(0);
  const [deleting, setDeleting] = useState<SavedRun | null>(null);
  const [notice, setNotice] = useState("");
  const listHeading = useRef<HTMLHeadingElement>(null);
  const offset = (page - 1) * PAGE_SIZE;

  useEffect(() => {
    let active = true;
    setListError("");
    setRecords(null);
    // The API returns rows without a total. One extra row establishes whether another page exists.
    getRuns(PAGE_SIZE + 1, offset)
      .then((data) => {
        if (active) setRecords(data);
      })
      .catch((err) => {
        if (active) setListError(messageOf(err, "Could not load saved runs."));
      });
    return () => {
      active = false;
    };
  }, [offset, revision]);

  const visible = records?.slice(0, PAGE_SIZE) ?? [];
  const hasNext = (records?.length ?? 0) > PAGE_SIZE;
  const showLinked =
    id &&
    (records !== null || listError) &&
    !visible.some((run) => run.id === id);
  const closeDetails = () => navigate(historyPath(page));
  const onDeleted = () => {
    if (!deleting) return;
    setDeleting(null);
    setNotice(`Deleted run ${deleting.id.slice(0, 8)}.`);
    if (page > 1 && visible.length === 1 && visible[0].id === deleting.id) {
      navigate(historyPath(page - 1), { replace: true });
    } else {
      if (id === deleting.id) navigate(historyPath(page), { replace: true });
      setRevision((value) => value + 1);
    }
    listHeading.current?.focus();
  };

  return (
    <div className="history-page">
      <header className="history-heading">
        <div>
          <h1>Experiment history</h1>
          <p>
            Review allocation results from runs saved to this browser’s visitor
            session.
          </p>
        </div>
        <Link className="btn btn-primary" to="/simulate">
          <Plus size={16} aria-hidden="true" /> New simulation
        </Link>
      </header>

      {showLinked && (
        <section className="history-panel" aria-label="Selected experiment">
          <div className="history-toolbar">
            <h2>Selected experiment</h2>
          </div>
          <ul className="history-list">
            <LinkedRun
              key={id}
              id={id}
              onClose={closeDetails}
              onDelete={setDeleting}
            />
          </ul>
        </section>
      )}
      <section className="history-panel" aria-labelledby="saved-runs-title">
        <div className="history-toolbar">
          <h2 ref={listHeading} tabIndex={-1} id="saved-runs-title">
            <ListTree size={17} aria-hidden="true" /> Saved runs
          </h2>
          <span className="history-scope">
            <LockKeyhole size={13} aria-hidden="true" /> Visitor session
          </span>
        </div>
        {listError ? (
          <div className="history-state">
            <CircleAlert size={24} aria-hidden="true" />
            <h3>History unavailable</h3>
            <p role="alert">{listError}</p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setRevision((value) => value + 1)}
            >
              Try again
            </button>
          </div>
        ) : records === null ? (
          <div className="history-state" role="status">
            <History size={24} aria-hidden="true" /> Loading saved runs…
          </div>
        ) : !visible.length ? (
          <div className="history-state">
            <span className="history-empty-icon">
              <History size={24} aria-hidden="true" />
            </span>
            <h3>
              {page === 1
                ? "No simulation runs saved yet"
                : "No runs on this page"}
            </h3>
            <p>
              {page === 1
                ? "Run a simulation or upload a workload to see its results here."
                : "Return to the first page to see your latest runs."}
            </p>
            {page > 1 && (
              <Link className="btn btn-secondary" to="/history">
                First page
              </Link>
            )}
          </div>
        ) : null}
        {visible.length > 0 && (
          <>
            <div className="history-columns" aria-hidden="true">
              <span>Experiment</span>
              <span>Status</span>
              <span>Duration</span>
              <span>Created</span>
            </div>
            <ul className="history-list">
              {visible.map((run) => (
                <RunRow
                  key={run.id}
                  run={run}
                  details={id === run.id ? <InlineRunDetails id={run.id} /> : undefined}
                  onDelete={setDeleting}
                  onToggle={() =>
                    navigate(
                      historyPath(page, id === run.id ? undefined : run.id),
                    )
                  }
                />
              ))}
            </ul>
          </>
        )}
        {visible.length > 0 && (
          <nav className="history-pagination" aria-label="History pagination">
            <span>
              Showing {offset + 1}–{offset + visible.length}
            </span>
            <div>
              <button
                type="button"
                disabled={page === 1}
                onClick={() => navigate(historyPath(page - 1))}
                aria-label="Previous page"
              >
                <ChevronLeft size={16} aria-hidden="true" />
              </button>
              <span>Page {page}</span>
              <button
                type="button"
                disabled={!hasNext}
                onClick={() => navigate(historyPath(page + 1))}
                aria-label="Next page"
              >
                <ChevronRight size={16} aria-hidden="true" />
              </button>
            </div>
          </nav>
        )}
      </section>
      {notice && (
        <p className="history-notice" role="status">
          {notice}
        </p>
      )}
      <DisclaimerBanner />
      {deleting && (
        <DeleteDialog
          run={deleting}
          onCancel={() => setDeleting(null)}
          onDeleted={onDeleted}
        />
      )}
    </div>
  );
}

export function HistoryPage() {
  const [search] = useSearchParams();
  const requested = Number(search.get("page"));
  const page =
    Number.isSafeInteger(requested) &&
    requested > 0 &&
    Number.isSafeInteger(requested * PAGE_SIZE)
      ? requested
      : 1;
  return <RunHistory key={page} page={page} />;
}
